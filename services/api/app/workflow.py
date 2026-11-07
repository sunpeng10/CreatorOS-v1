"""Persisted, restart-safe seven-stage analysis workflow for a single local server."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from .db import SessionLocal
from .mimo import MiMoClient, MiMoError
from .models import (AgentRun, AgentStep, AnalysisEvidence, Approval, AuditLog, BenchmarkItem,
                     ContentAnalysis, ContentAsset, CostEvent, MetricSnapshot, serialize, stamp)
from .schemas_ai import (SCHEMAS, BusinessOutput, ContentOutput, COOOutput, DataOutput,
                         Finding, QualityOutput, Report, RetrievalOutput, StrategyDraft, StrategyOutput)

STAGES = ["COO", "content", "data", "retrieval", "strategy", "quality", "business"]
PIPELINE_VERSION = "creatoros-1.0"


def local_report(content: dict) -> Report:
    title = content.get("title") or "未命名作品"
    text = content.get("text") or ""
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    findings = [Finding(label="标题长度", evidence=f"当前标题共 {len(title)} 个字符：{title}", location="title", confidence=1),
                Finding(label="文稿结构", evidence=f"已提供 {len(text)} 个字符、{len(paragraphs)} 个非空段落。",
                        location="text", confidence=1)]
    if text:
        findings.append(Finding(label="开头原文", evidence=text[:180], location="text:开头", confidence=1))
    limitations = ["本地规则分析，未调用 MiMo；没有对图片或视频画面进行语义理解。",
                   "未自动进行语音转录；没有上传字幕或文稿的语音内容无法分析。",
                   "标题、脚本与改动方向为待验证建议，不能保证流量增长或证明因果关系。"]
    if not text:
        limitations.append("没有可用文稿；脚本仅为待补充的结构模板，请先填写实际内容。")
    return Report(summary=f"《{title}》的本地基础检查已完成。可核实标题和文稿结构，建议通过后续实验验证修改效果。",
                  findings=findings, titles=[title, f"关于{title}：从一个具体问题开始", f"{title}：案例与实践步骤"],
                  hooks=[f"问题式：关于{title}，你最想解决哪个具体问题？",
                         f"案例式：先展示一个与{title}相关的真实案例，再解释过程。",
                         f"结果式：先展示{title}的可验证结果，再交代条件与限制。"],
                  script=f"【可编辑脚本草案｜需人工核实】\n开头：用一句话说明《{title}》解决的问题。\n"
                         f"主体：{text or '[补充经核实的事实、案例与操作步骤]'}\n"
                         "证据：补充可以核查的来源，标注适用条件。\n结尾：邀请观众提出一个与主题相关的问题。",
                  tasks=["核实开头承诺与实际内容一致", "补充事实来源与适用边界", "只改变一个变量开展实验并记录观测窗口"],
                  limitations=limitations, source="local",
                  image_structure=["第 1 页：明确问题与主题", "中间页：每页一个要点并配对应证据", "末页：总结与具体行动"],
                  experiments=["在相同发布条件下比较两个开头，记录各自观测窗口与样本限制，不据一次变化推断因果。"])


def take_snapshot(db, content, mode):
    org = content.organization_id
    assets = db.scalars(select(ContentAsset).where(ContentAsset.content_id == content.id,
                                                 ContentAsset.organization_id == org).order_by(ContentAsset.created_at)).all()
    snapshots = db.scalars(select(MetricSnapshot).where(MetricSnapshot.content_id == content.id,
                                                       MetricSnapshot.organization_id == org).order_by(MetricSnapshot.observed_at)).all()
    benchmarks = db.scalars(select(BenchmarkItem).where(BenchmarkItem.organization_id == org,
                                                       BenchmarkItem.is_demo.is_(False)).order_by(BenchmarkItem.created_at).limit(200)).all()
    client = MiMoClient()
    return {"content": serialize(content), "assets": [serialize(a) for a in assets],
            "metrics": [serialize(s) for s in snapshots], "benchmarks": [serialize(b) for b in benchmarks],
            "mode": mode, "version": PIPELINE_VERSION,
            "models": [client.fast_model, client.reasoning_model] if mode == "ai" else []}


def cache_key(snapshot):
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def create_run(db, analysis, snapshot, budget, paid_consent):
    run = AgentRun(organization_id=analysis.organization_id, analysis_id=analysis.id, status="QUEUED",
                   budget=budget, cost=0, error="", data={"snapshot": snapshot, "paid_consent": paid_consent,
                                                        "currency": "CNY", "cost_is_estimate": True})
    db.add(run)
    db.flush()
    for index, name in enumerate(STAGES):
        db.add(AgentStep(organization_id=analysis.organization_id, run_id=run.id, name=name,
                         status="QUEUED", attempts=0, input={}, output={}, error="", data={"order": index}))
    analysis.task_id, analysis.status = run.id, "QUEUED"
    analysis.cache_key = cache_key(snapshot)
    db.add(AuditLog(organization_id=analysis.organization_id, action="analysis.queued", target_id=analysis.id,
                    data={"run_id": run.id, "mode": analysis.mode, "paid_consent": paid_consent}))
    db.commit()
    return run


def _content_breakdown(content):
    report = local_report(content)
    return ContentOutput(topic="未使用模型分类；以用户填写的标题和类别为准", audience="insufficient_data：需填写目标受众",
                         opening_hook=(content.get("text") or "")[:180] or "insufficient_data：未提供文稿",
                         narrative=[line for line in (content.get("text") or "").splitlines() if line.strip()][:20],
                         visual_observations=[], findings=report.findings, limitations=report.limitations[:2])


def _data_output(snapshots):
    if not snapshots:
        return DataOutput(sample_count=0, latest_metrics={}, source=[], findings=[],
                          limitations=["没有导入表现指标，无法计算互动率、相对表现或内容增长。"])
    latest = max(snapshots, key=lambda item: item.get("observed_at", ""))
    data = latest.get("data", {})
    values = data.get("metrics", data)
    metrics = {key: values.get(key) for key in ["views", "likes", "comments", "shares", "favorites"]}
    findings = [Finding(label="已导入的指标快照", evidence=json.dumps(metrics, ensure_ascii=False),
                        location=f"snapshot:{latest['id']} ({latest.get('observed_at', '')})", confidence=1, kind="数据支持")]
    return DataOutput(sample_count=len(snapshots), latest_metrics=metrics,
                      source=sorted({s.get("source", "手工导入") for s in snapshots}), findings=findings,
                      limitations=["缺失指标保留为空；指标由用户导入，未向平台独立核验。", "单个作品的快照不足以证明改动产生因果效果。"])


def _terms(text):
    words = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower()))
    words.update(text[index:index + 2] for index in range(len(text) - 1) if all("\u4e00" <= char <= "\u9fff" for char in text[index:index + 2]))
    return words


def _retrieval(query, candidates):
    terms = _terms(query)
    matches = []
    for item in candidates:
        candidate_terms = _terms(item.get("title", "") + " " + item.get("category", ""))
        score = len(terms & candidate_terms) / max(1, len(terms | candidate_terms))
        if score:
            matches.append({"id": item["id"], "title": item["title"], "url": item.get("url", ""),
                            "similarity": round(score, 4), "reason": "已有作品库中的标题/类别词项匹配",
                            "is_demo": False, "source": "用户录入的本地资料库"})
    return RetrievalOutput(matches=sorted(matches, key=lambda x: x["similarity"], reverse=True)[:5],
                           limitations=["只检索本工作区非 Demo 的已入库资料（最多 200 条）；未进行互联网搜索。",
                                        "使用词项相似度召回；没有足够同作者历史数据时不判断爆款程度。"])


def _media_parts(db, snapshot):
    parts, limitations, token_reserve = [], [], 0
    for item in snapshot["assets"]:
        # Generated keyframes are represented by the original video when it fits; do not bill duplicates.
        if item.get("data", {}).get("generated") or item.get("data", {}).get("is_keyframe") or item.get("data", {}).get("role") == "keyframe":
            continue
        mime = item.get("mime", "")
        if not (mime.startswith("image/") or mime.startswith("video/")):
            continue
        if len(parts) >= 8:
            limitations.append("超过 8 个媒体输入，其余媒体未发送模型。")
            break
        asset = db.get(ContentAsset, item["id"])
        if not asset or asset.organization_id != snapshot["content"]["organization_id"]:
            raise MiMoError("MISSING_ASSET", "分析快照中的私有素材不存在。")
        path = Path(asset.path)
        if not path.is_file():
            raise MiMoError("MISSING_ASSET", "素材文件不可读，请重新上传。")
        size = path.stat().st_size
        # 35 MiB raw gives < 50 MiB base64; also bound the complete request below.
        if size > (35 if mime.startswith("video/") else 12) * 1024 * 1024:
            limitations.append(f"{item.get('original_name', '素材')} 超出本地直传上限，未发送模型；请压缩、裁剪后重试。")
            continue
        if mime.startswith("video/"):
            duration = (item.get("data", {}).get("metadata") or {}).get("duration")
            if not duration:
                limitations.append("视频时长元数据缺失，无法估算输入成本；未发送此视频。")
                continue
            data_url = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
            parts.append({"type": "video_url", "video_url": {"url": data_url}, "fps": 2, "media_resolution": "default"})
            # Official default resolution caps each temporal grid at ~300 visual tokens;
            # two sampled frames per grid, plus timestamps/audio and a 25% reserve margin.
            grids = max(1, math.ceil(min(2048, math.ceil(float(duration) * 2)) / 2))
            token_reserve += math.ceil((grids * 305 + float(duration) * 6.25 + 4) * 1.25)
        else:
            data_url = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
            parts.append({"type": "image_url", "image_url": {"url": data_url}})
            token_reserve += 16384
    if sum(len(json.dumps(p)) for p in parts) > 49 * 1024 * 1024:
        raise MiMoError("MEDIA_TOO_LARGE", "媒体合计 Base64 超过本地请求上限，请缩减图集或裁剪视频。")
    return parts, limitations, token_reserve


def _stage_input(name, snapshot, outputs, run):
    content = snapshot["content"]
    if name == "COO":
        return {"content": content, "mode": snapshot["mode"], "budget": run.budget}
    if name == "content":
        return {"content": content, "assets": snapshot["assets"]}
    if name == "data":
        return {"snapshots": snapshot["metrics"]}
    if name == "retrieval":
        return {"query": content.get("title", "") + " " + content.get("text", "")[:500], "candidates": snapshot["benchmarks"]}
    if name == "strategy":
        return {"content": content, "breakdown": outputs["content"], "data": outputs["data"], "retrieval": outputs["retrieval"]}
    if name == "quality":
        return {"report": outputs["strategy"], "allowed_urls": [b.get("url", "") for b in snapshot["benchmarks"] if b.get("url")],
                "media_received": bool(outputs["content"].get("visual_observations"))}
    return {"analysis_id": run.analysis_id, "report": outputs["quality"]["report"]}


def _execute_stage(name, inputs, db, run, step, snapshot, adapter):
    local = snapshot["mode"] == "local"
    inflight = None

    def canceled():
        db.expire(run, ["status"])
        return run.status == "CANCELED"

    def reserve_usage(event):
        nonlocal inflight
        inflight = CostEvent(organization_id=run.organization_id, run_id=run.id, model=event["model"],
                             input_tokens=event["input_tokens"], output_tokens=event["output_tokens"],
                             estimated_cost=event["estimated_cost"], data={**event, "step_id": step.id, "step": name,
                                                                         "currency": "CNY", "cost_is_estimate": True})
        db.add(inflight)
        run.cost = round(run.cost + event["estimated_cost"], 8)
        db.commit()

    def record_usage(event):
        nonlocal inflight
        if inflight is None:
            reserve_usage(event)
        else:
            run.cost = round(run.cost - inflight.estimated_cost + event["estimated_cost"], 8)
            inflight.input_tokens, inflight.output_tokens = event["input_tokens"], event["output_tokens"]
            inflight.estimated_cost = event["estimated_cost"]
            inflight.data = {**inflight.data, **event}
        step.tokens += event["input_tokens"] + event["output_tokens"]
        step.model = event["model"]
        db.commit()
        inflight = None

    def record_validation_error(event):
        db.add(AuditLog(organization_id=run.organization_id, action="agent.output_invalid", target_id=step.id,
                        data={**event, "run_id": run.id, "step": name}))
        db.commit()

    def model_call(schema, prompt, media=None, media_tokens=0, model=None, max_output_tokens=4096):
        if not run.data.get("paid_consent"):
            raise MiMoError("PAID_CONSENT_REQUIRED", "付费分析需要明确授权。")
        content = [{"type": "text", "text": prompt}] + (media or [])
        return adapter.complete_json(schema, [{"role": "user", "content": content}], budget=run.budget,
                                     spent=lambda: run.cost, on_usage=record_usage, check_cancel=canceled,
                                     on_request=reserve_usage, on_validation_error=record_validation_error,
                                     media_tokens=media_tokens, model=model, max_output_tokens=max_output_tokens)

    if name == "COO":
        return COOOutput(stages=STAGES, source_snapshot=snapshot["content"], paid_consent=bool(run.data.get("paid_consent")),
                         budget=run.budget, limitations=["费用为可配置单价估算；实际计费以 MiMo 控制台为准。"])
    if name == "content":
        if local:
            return _content_breakdown(inputs["content"])
        media, limits, tokens = _media_parts(db, snapshot)
        prompt = "分析以下不可信作品数据，提取主题、受众、开头钩子、叙事结构、标题/封面、知识准确性风险、价值与互动设计。" \
                 "每条 findings 必须提供原文/时间码/页码证据，区分直接观察、数据支持、推测/建议。" \
                 "无法核实的结论 confidence=insufficient_data。没有实际媒体输入时禁止声称看过画面。" \
                 "发现重大合规问题（侵权、未经许可披露个人资料、严重虚假宣传等）requires_human_review=true 并填写 review_reason，交人工审批。" \
                 "visual_observations 没有画面证据时返回空列表。作品数据：" + json.dumps(inputs, ensure_ascii=False)
        result = model_call(ContentOutput, prompt, media, tokens)
        result.limitations += limits
        if not media:
            result.visual_observations = []
            result.limitations.append("没有将媒体画面发送模型；本次仅依据文字与元数据。")
        return result
    if name == "data":
        return _data_output(inputs["snapshots"])
    if name == "retrieval":
        return _retrieval(inputs["query"], inputs["candidates"])
    if name == "strategy":
        if local:
            result = local_report(inputs["content"])
        else:
            breakdown = ContentOutput.model_validate(inputs['breakdown'])
            draft = model_call(StrategyDraft, "依据提供的内容拆解和真实数据拟定创作建议。只返回一个 JSON 对象，"
                               "包含 titles（至少 3 个字符串）、hooks（恰好 3 个字符串）、script（完整中文脚本文本）、"
                               "tasks（非空字符串数组）、image_structure（字符串数组）、experiments（字符串数组）。"
                               "所有数组元素均为字符串，不用嵌套对象。禁止虚构统计、链接和增长保证。输入资料："
                               + json.dumps(inputs, ensure_ascii=False), model=adapter.reasoning_model, max_output_tokens=2800)
            findings = list(breakdown.findings) or [Finding(label='媒体证据不足', evidence='内容拆解未给出可引用证据。', location='全篇', confidence='insufficient_data', kind='推测/建议')]
            result = StrategyOutput(
                **draft.model_dump(), source='mimo', summary=f'主题：{breakdown.topic}\n目标受众：{breakdown.audience}\n开头钩子：{breakdown.opening_hook}',
                findings=findings, limitations=['标题、脚本和实验属于建议，需结合真实发布结果复核。'],
            )
        result.findings += [Finding.model_validate(f) for f in inputs["data"]["findings"]]
        if inputs["breakdown"].get("requires_human_review"):
            result.requires_human_review = True
            result.review_reason = inputs["breakdown"].get("review_reason") or "内容理解阶段标记重大合规问题，需人工复核。"
        result.limitations = list(dict.fromkeys(result.limitations + inputs["data"]["limitations"] +
                                                inputs["retrieval"]["limitations"] + inputs["breakdown"]["limitations"]))
        return StrategyOutput.model_validate(result.model_dump())
    if name == "quality":
        report = Report.model_validate(inputs["report"])
        allowed = set(inputs["allowed_urls"])
        removed = []
        def sanitize(value):
            if isinstance(value, dict):
                return {key: sanitize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [sanitize(item) for item in value]
            if isinstance(value, str):
                def replace(match):
                    url = match.group(0)
                    if url in allowed:
                        return url
                    removed.append(url)
                    return "[未核实链接已移除]"
                return re.sub(r"https?://[^\s\"<>\\\]\)。，；！？、]+", replace, value)
            return value
        # One bounded deterministic rework covers every report field, including nested evidence.
        report = Report.model_validate(sanitize(report.model_dump()))
        issues = ["报告包含未在本地资料库登记的外部链接，已移除；请人工核实来源。"] if removed else []
        report.limitations.extend(issues)
        return QualityOutput(passed=True, checks=["Pydantic 报告结构", "指标来源与缺失说明", "引用链接白名单", "三种开头与可编辑脚本"],
                             issues=issues, report=report, rework_count=1 if issues else 0)
    return BusinessOutput(delivery_ready=True, follow_up="发布后在相同观测窗口导入指标，并回访本次修改体验。",
                          quote_draft={"status": "DRAFT_ONLY", "amount": None, "scope": "内容诊断与改进报告；报价由管理员填写并审批"},
                          required_approvals=["对外发布", "报价与报价变更", "真实付款/退款", "重大合规问题", "删除用户数据"])


def execute_run(run_id, session_factory=None, adapter_factory=None):
    factory = session_factory or SessionLocal
    with factory() as db:
        # Atomic claim makes duplicate background submissions harmless, including across worker threads.
        claimed = db.execute(update(AgentRun).where(AgentRun.id == run_id, AgentRun.status == "QUEUED").values(status="RUNNING"))
        db.commit()
        if not claimed.rowcount:
            return
        run = db.get(AgentRun, run_id)
        analysis = db.get(ContentAnalysis, run.analysis_id)
        analysis.status, run.error = "RUNNING", ""
        db.commit()
        step = None
        try:
            snapshot = run.data["snapshot"]
            adapter = (adapter_factory or MiMoClient)()
            steps = db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()
            by_name, outputs = {s.name: s for s in steps}, {}
            for name in STAGES:
                db.expire(run, ["status"])
                if run.status == "CANCELED":
                    raise MiMoError("CANCELED", "任务已取消；已经在途的模型调用仍可能计费。")
                step = by_name[name]
                if step.status == "SUCCEEDED":
                    outputs[name] = step.output
                    continue
                input_schema, output_schema = SCHEMAS[name]
                inputs = input_schema.model_validate(_stage_input(name, snapshot, outputs, run)).model_dump()
                step.input, step.status, step.error = inputs, "RUNNING", ""
                step.attempts += 1
                step.data = {**step.data, "started_at": stamp()}
                db.commit()
                output = _execute_stage(name, inputs, db, run, step, snapshot, adapter)
                db.expire(run, ["status"])
                if run.status == "CANCELED":
                    raise MiMoError("CANCELED", "任务已取消；在途请求的费用已记录。")
                step.output = output_schema.model_validate(output.model_dump()).model_dump()
                step.status = "SUCCEEDED"
                step.data = {**step.data, "completed_at": stamp()}
                outputs[name] = step.output
                if name == "quality" and output.report.requires_human_review:
                    pending = db.scalar(select(Approval).where(Approval.target_id == run.id,
                                                               Approval.kind == "COMPLIANCE_REVIEW", Approval.status == "PENDING"))
                    if not pending:
                        db.add(Approval(organization_id=run.organization_id, kind="COMPLIANCE_REVIEW", target_id=run.id,
                                        status="PENDING", reason=output.report.review_reason or "报告需要人工合规复核。",
                                        data={"analysis_id": analysis.id, "step_id": step.id}))
                    run.status, analysis.status, step.status = "WAITING_APPROVAL", "WAITING_APPROVAL", "WAITING_APPROVAL"
                    db.commit()
                    return
                db.add(AuditLog(organization_id=run.organization_id, action="agent.step_succeeded", target_id=step.id,
                                data={"run_id": run.id, "name": name, "attempt": step.attempts}))
                db.commit()
            report = Report.model_validate(outputs["quality"]["report"])
            completed = db.execute(update(AgentRun).where(AgentRun.id == run.id, AgentRun.status == "RUNNING")
                                   .values(status="SUCCEEDED", data={**run.data, "completed_at": stamp()}))
            if not completed.rowcount:
                raise MiMoError("CANCELED", "任务在完成前被取消，未覆盖取消状态。")
            analysis.report, analysis.status = report.model_dump(), "SUCCEEDED"
            analysis.data = {**analysis.data, "source_snapshot": snapshot["content"], "completed_at": stamp(),
                             "estimated_cost": run.cost, "currency": "CNY", "cost_is_estimate": True}
            for finding in report.findings:
                db.add(AnalysisEvidence(organization_id=run.organization_id, analysis_id=analysis.id, data=finding.model_dump()))
            db.commit()
        except Exception as error:
            db.rollback()
            run = db.get(AgentRun, run_id)
            analysis = db.get(ContentAnalysis, run.analysis_id)
            code = error.code if isinstance(error, MiMoError) else "WORKFLOW_ERROR"
            message = str(error) if isinstance(error, MiMoError) else "步骤执行失败，请检查输入或联系管理员；可从失败节点重试。"
            status = "CANCELED" if run.status == "CANCELED" or code == "CANCELED" else "FAILED"
            run.status, analysis.status, run.error = status, status, f"{code}: {message}"
            if step and step.status != "SUCCEEDED":
                step.status, step.error = status, run.error
            db.add(AuditLog(organization_id=run.organization_id, action="agent.run_failed" if status == "FAILED" else "agent.run_canceled",
                            target_id=run.id, data={"code": code, "message": message, "stage": step.name if step else None,
                                                   "exception_type": type(error).__name__}))
            db.commit()


def recover_interrupted_tasks(session_factory=None):
    """On process startup, make interrupted jobs explicitly retryable; never resume paid calls silently."""
    with (session_factory or SessionLocal)() as db:
        runs = db.scalars(select(AgentRun).where(AgentRun.status.in_(["RUNNING", "QUEUED"]))).all()
        for run in runs:
            run.status = "FAILED"
            run.error = "PROCESS_INTERRUPTED: 服务重启中断了任务；已完成节点保留，请手动重试。"
            analysis = db.get(ContentAnalysis, run.analysis_id)
            if analysis:
                analysis.status = "FAILED"
            for step in db.scalars(select(AgentStep).where(AgentStep.run_id == run.id, AgentStep.status == "RUNNING")):
                step.status, step.error = "FAILED", run.error
            db.add(AuditLog(organization_id=run.organization_id, action="agent.recovered", target_id=run.id, data={"error": run.error}))
        db.commit()
        return len(runs)


def apply_compliance_decision(db, approval, decision, user):
    """Apply inside the commerce approval transaction; caller schedules returned callback AFTER commit."""
    if user.role != "OWNER_ADMIN":
        raise HTTPException(403, "仅老板管理员可审批合规问题。")
    run = db.get(AgentRun, approval.target_id)
    if not run or run.organization_id != user.organization_id or approval.organization_id != user.organization_id:
        raise HTTPException(404, "审批对应任务不存在。")
    if run.status != "WAITING_APPROVAL" or decision not in {"APPROVED", "REJECTED"}:
        raise HTTPException(409, "该任务已不处于待审批状态。")
    analysis = db.get(ContentAnalysis, run.analysis_id)
    if not analysis or analysis.organization_id != user.organization_id:
        raise HTTPException(404, "审批对应报告不存在。")
    quality = db.scalar(select(AgentStep).where(AgentStep.run_id == run.id, AgentStep.name == "quality"))
    if not quality or quality.status != "WAITING_APPROVAL":
        raise HTTPException(409, "报告质检节点不处于待审批状态。")
    if decision == "REJECTED":
        run.status, analysis.status, quality.status = "CANCELED", "CANCELED", "CANCELED"
        run.error = "COMPLIANCE_REJECTED: 管理员拒绝了报告交付。"
        return None
    quality.status = "SUCCEEDED"
    quality.data = {**quality.data, "approved_by": user.id, "approval_id": approval.id}
    run.status, analysis.status = "QUEUED", "QUEUED"
    return execute_run, (run.id, sessionmaker(bind=db.get_bind(), expire_on_commit=False))
