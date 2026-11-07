"""Owned analysis/task/export/version endpoints. No paid call occurs on creation."""
from __future__ import annotations

import json
import threading
import time
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from .auth import current_user, owned
from .db import get_db
from .mimo import MiMoClient
from .models import (AgentRun, AgentStep, AuditLog, ContentAnalysis, ContentItem,
                     ContentVersion, CostEvent, User, serialize, stamp)
from .workflow import STAGES, cache_key, create_run, execute_run, take_snapshot

router = APIRouter(prefix="/api", tags=["分析与任务"])
_start_lock = threading.Lock()
_status_lock = threading.Lock()
_status_cache = {"expires": 0, "result": None, "config": None}


class AnalysisRequest(BaseModel):
    content_id: str
    mode: Literal["local", "ai"] = "local"


class StartRequest(BaseModel):
    confirm_paid: bool = False
    budget: float = Field(default=1, gt=0, le=1000)


class RetryRequest(BaseModel):
    budget: float | None = Field(default=None, gt=0, le=1000)


class VersionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    script: str = Field(min_length=1, max_length=100_000)


def _error(code, message, status=400):
    raise HTTPException(status, detail={"code": code, "message": message})


def _steps(db, run_id):
    rows = db.scalars(select(AgentStep).where(AgentStep.run_id == run_id)).all()
    return [serialize(row) for row in sorted(rows, key=lambda s: STAGES.index(s.name) if s.name in STAGES else 99)]


def _task(db, run):
    result = serialize(run)
    # The snapshot is stored durably for cache/retry but excluded from routine task responses.
    result.pop("snapshot", None)
    result["data"] = {key: value for key, value in result.get("data", {}).items() if key != "snapshot"}
    result["steps"] = _steps(db, run.id)
    result["progress"] = round(sum(s["status"] == "SUCCEEDED" for s in result["steps"]) / len(STAGES) * 100)
    result["cost_events"] = [serialize(e) for e in db.scalars(select(CostEvent).where(CostEvent.run_id == run.id).order_by(CostEvent.created_at))]
    return result


def _detail(db, analysis):
    result = serialize(analysis)
    result["steps"] = []
    if analysis.task_id:
        run = db.get(AgentRun, analysis.task_id)
        if run and run.organization_id == analysis.organization_id:
            result["task"] = _task(db, run)
            result["steps"] = result["task"]["steps"]
    return result


def _schedule(background, db, run):
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    background.add_task(execute_run, run.id, factory)


@router.get("/system/ai-status")
def ai_status():
    client = MiMoClient()
    # Avoid a network probe on every UI render; no key or header ever enters the cache result.
    config = (bool(client.api_key), client.base_url, client.fast_model, client.reasoning_model)
    with _status_lock:
        if _status_cache["config"] != config or time.monotonic() >= _status_cache["expires"]:
            _status_cache.update(result=client.status(), expires=time.monotonic() + 60, config=config)
        return _status_cache["result"]


@router.post("/analyses")
def create_analysis(body: AnalysisRequest, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    content = owned(db, ContentItem, body.content_id, user)
    snapshot = take_snapshot(db, content, body.mode)
    key = cache_key(snapshot)
    prior = db.scalar(select(ContentAnalysis).where(ContentAnalysis.organization_id == user.organization_id,
                                                   ContentAnalysis.content_id == content.id, ContentAnalysis.mode == body.mode,
                                                   ContentAnalysis.cache_key == key, ContentAnalysis.status == "SUCCEEDED")
                      .order_by(ContentAnalysis.created_at.desc()))
    if prior:
        return {**_detail(db, prior), "cached": True}
    analysis = ContentAnalysis(organization_id=user.organization_id, content_id=content.id, mode=body.mode,
                               status="QUEUED", cache_key=key, report={}, data={"created_by": user.id})
    db.add(analysis)
    db.commit()
    if body.mode == "local":
        run = create_run(db, analysis, snapshot, 0, False)
        _schedule(background, db, run)
    return _detail(db, analysis)


@router.post("/analyses/{analysis_id}/start")
def start_analysis(analysis_id: str, body: StartRequest, background: BackgroundTasks,
                   db: Session = Depends(get_db), user: User = Depends(current_user)):
    with _start_lock:
        analysis = owned(db, ContentAnalysis, analysis_id, user)
        if analysis.task_id:
            return _detail(db, analysis)
        if analysis.mode == "ai":
            if not body.confirm_paid:
                _error("PAID_CONSENT_REQUIRED", "请明确确认开始付费 AI 分析。")
            client = MiMoClient()
            if not client.api_key:
                _error("AI_NOT_CONFIGURED", "未配置 MiMo；请使用本地分析或由管理员配置。", 503)
            if body.budget > client.max_task_cost:
                _error("BUDGET_LIMIT", f"预算不能超过服务端任务上限 {client.max_task_cost} CNY（估算）。")
        content = owned(db, ContentItem, analysis.content_id, user)
        snapshot = take_snapshot(db, content, analysis.mode)
        run = create_run(db, analysis, snapshot, body.budget if analysis.mode == "ai" else 0,
                         body.confirm_paid and analysis.mode == "ai")
        _schedule(background, db, run)
        return _detail(db, analysis)


@router.get("/analyses")
def analyses(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
             db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ContentAnalysis).where(ContentAnalysis.organization_id == user.organization_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(ContentAnalysis.created_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [serialize(item) for item in items], "total": total}


@router.get("/analyses/{analysis_id}")
def analysis_detail(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _detail(db, owned(db, ContentAnalysis, analysis_id, user))


@router.get("/tasks/{task_id}")
def task_detail(task_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _task(db, owned(db, AgentRun, task_id, user))


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    run = owned(db, AgentRun, task_id, user)
    if run.status == "SUCCEEDED":
        _error("TASK_FINISHED", "任务已完成。", 409)
    if run.status != "CANCELED":
        # Conditional mutation protects the completion/cancellation race beyond this request's identity map.
        changed = db.execute(update(AgentRun).where(AgentRun.id == run.id,
                                                    AgentRun.status.not_in(["SUCCEEDED", "CANCELED"]))
                             .values(status="CANCELED", error="CANCELED: 用户取消；在途模型请求仍可能产生费用，后续节点停止。"))
        if not changed.rowcount:
            db.refresh(run)
            if run.status == "SUCCEEDED":
                _error("TASK_FINISHED", "任务已完成。", 409)
            return _task(db, run)
        analysis = owned(db, ContentAnalysis, run.analysis_id, user)
        analysis.status = "CANCELED"
        for step in db.scalars(select(AgentStep).where(AgentStep.run_id == run.id, AgentStep.status == "QUEUED")):
            step.status = "CANCELED"
        db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="analysis.canceled", target_id=run.id))
        db.commit()
    return _task(db, run)


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str, background: BackgroundTasks, body: RetryRequest | None = None,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    with _start_lock:
        run = owned(db, AgentRun, task_id, user)
        if run.status != "FAILED":
            _error("TASK_NOT_FAILED", "只能重试失败任务；取消的任务请重新创建分析。", 409)
        analysis = owned(db, ContentAnalysis, run.analysis_id, user)
        if analysis.mode == "ai":
            client = MiMoClient()
            if not run.data.get("paid_consent") or not client.api_key:
                _error("AI_NOT_CONFIGURED", "付费授权或服务端模型配置缺失。", 503)
            if body and body.budget is not None:
                if body.budget > client.max_task_cost or body.budget <= run.cost:
                    _error("BUDGET_LIMIT", "新预算需高于已估算费用且不超过服务端任务上限。")
                run.budget = body.budget
        run.status, run.error, analysis.status = "QUEUED", "", "QUEUED"
        for step in db.scalars(select(AgentStep).where(AgentStep.run_id == run.id, AgentStep.status == "FAILED")):
            step.status, step.error = "QUEUED", ""
        db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="analysis.retry", target_id=run.id,
                        data={"reuse_successful_steps": True, "budget": run.budget}))
        db.commit()
        _schedule(background, db, run)
        return _task(db, run)


@router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str, format: Literal["json", "markdown"] = "json",
                    db: Session = Depends(get_db), user: User = Depends(current_user)):
    analysis = owned(db, ContentAnalysis, analysis_id, user)
    if analysis.status != "SUCCEEDED":
        _error("REPORT_NOT_READY", "分析尚未成功，暂不能导出报告。", 409)
    if format == "json":
        text = json.dumps(_detail(db, analysis), ensure_ascii=False, indent=2)
        return Response(text, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="analysis-{analysis.id}.json"'})
    report = analysis.report
    lines = ["# CreatorOS 内容诊断报告", "", f"来源：{report.get('source')}｜费用为估算，非实际账单", "", report.get("summary", ""), "", "## 证据"]
    for finding in report.get("findings", []):
        lines += [f"- [{finding.get('kind', '直接观察')}] {finding.get('label')}：{finding.get('evidence')} "
                  f"（{finding.get('location')}；置信度 {finding.get('confidence')}）"]
    for heading, key in [("标题候选", "titles"), ("开头方案", "hooks"), ("改进任务", "tasks"), ("图文结构", "image_structure"), ("实验假设", "experiments")]:
        lines += ["", "## " + heading] + ["- " + item for item in report.get(key, [])]
    lines += ["", "## 脚本草案", "", report.get("script", ""), "", "## 局限"] + ["- " + item for item in report.get("limitations", [])]
    return Response("\n".join(lines), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="analysis-{analysis.id}.md"'})


@router.post("/analyses/{analysis_id}/versions")
def save_version(analysis_id: str, body: VersionRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    analysis = owned(db, ContentAnalysis, analysis_id, user)
    content = owned(db, ContentItem, analysis.content_id, user)
    number = (db.scalar(select(func.max(ContentVersion.version)).where(ContentVersion.content_id == content.id,
                                                                      ContentVersion.organization_id == user.organization_id)) or 0) + 1
    version = ContentVersion(organization_id=user.organization_id, content_id=content.id, analysis_id=analysis.id,
                             version=number, data={"title": body.title, "script": body.script,
                                                   "created_by": user.id, "saved_at": stamp()})
    db.add(version)
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="content.version_saved", target_id=content.id,
                    data={"version": number, "analysis_id": analysis.id}))
    db.commit()
    return serialize(version)


@router.get("/contents/{content_id}/versions")
def versions(content_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, ContentItem, content_id, user)
    items = db.scalars(select(ContentVersion).where(ContentVersion.content_id == content_id,
                                                   ContentVersion.organization_id == user.organization_id)
                       .order_by(ContentVersion.version.desc())).all()
    return {"items": [serialize(v) for v in items], "total": len(items)}
