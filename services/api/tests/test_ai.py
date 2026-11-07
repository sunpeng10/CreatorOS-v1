"""Offline tests: no provider request is sent outside MockTransport."""
import importlib
import json
import sys
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Answer(BaseModel):
    summary: str


def adapter():
    assert importlib.util.find_spec("app.mimo") is not None, "MiMo adapter must be implemented"
    return importlib.import_module("app.mimo")


def completion(text='{"summary":"done"}'):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


def test_official_request_format_and_429_exponential_retry():
    mod = adapter()
    requests, sleeps, events = [], [], []
    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={"error": {"message": "slow"}}) if len(requests) < 3 else completion()
    client = mod.MiMoClient(api_key="test-only", transport=httpx.MockTransport(handler), sleep=sleeps.append)
    result = client.complete_json(Answer, [{"role": "user", "content": "Return JSON"}],
                                  budget=1, on_usage=events.append)
    assert result.summary == "done"
    assert sleeps == [1, 2]
    assert len(events) == 3
    assert [e["status"] for e in events] == ["rate_limited", "rate_limited", "received"]
    body = json.loads(requests[-1].content)
    assert requests[-1].url == "https://api.xiaomimimo.com/v1/chat/completions"
    assert body["max_completion_tokens"] == 4096
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}


def test_invalid_json_is_repaired_and_every_billable_response_recorded():
    mod = adapter()
    calls, events = [], []
    def handler(request):
        calls.append(request)
        return completion("not json" if len(calls) == 1 else '{"summary":"repaired"}')
    client = mod.MiMoClient(api_key="test-only", transport=httpx.MockTransport(handler))
    result = client.complete_json(Answer, [{"role": "user", "content": "JSON"}], budget=1, on_usage=events.append)
    assert result.summary == "repaired"
    assert len(events) == 2
    assert all(e["estimated_cost"] > 0 for e in events)


def test_json_repair_is_limited_to_two_extra_requests():
    mod = adapter()
    events = []
    client = mod.MiMoClient(api_key="test-only", transport=httpx.MockTransport(lambda r: completion("{}")))
    with pytest.raises(mod.MiMoError) as error:
        client.complete_json(Answer, [{"role": "user", "content": "JSON"}], budget=1, on_usage=events.append)
    assert error.value.code == "INVALID_MODEL_OUTPUT"
    assert len(events) == 3


def test_budget_blocks_request_before_network_and_counts_prior_spend():
    mod = adapter()
    calls = []
    client = mod.MiMoClient(api_key="test-only", transport=httpx.MockTransport(lambda r: calls.append(r) or completion()))
    with pytest.raises(mod.MiMoError) as error:
        client.complete_json(Answer, [{"role": "user", "content": "JSON"}], budget=0.001, spent=lambda: 0)
    assert error.value.code == "BUDGET_EXCEEDED"
    assert calls == []


def test_safe_status_only_lists_models_and_hides_key():
    mod = adapter()
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-flash"}]})
    client = mod.MiMoClient(api_key="sensitive-test-value", transport=httpx.MockTransport(handler))
    result = client.status()
    assert calls[0].method == "GET" and calls[0].url.path == "/v1/models"
    assert result["connectivity"] == "connected"
    assert "sensitive-test-value" not in json.dumps(result)


def test_missing_key_has_no_network_activity():
    mod = adapter()
    client = mod.MiMoClient(api_key="", transport=httpx.MockTransport(lambda r: pytest.fail("unexpected request")))
    assert client.status()["connectivity"] == "not_configured"
    with pytest.raises(mod.MiMoError) as error:
        client.complete_json(Answer, [], budget=1)
    assert error.value.code == "AI_NOT_CONFIGURED"


def test_request_is_reserved_before_transport_and_timeout_keeps_cost():
    mod = adapter()
    reservations, events = [], []
    def handler(request):
        assert len(reservations) == 1, "persist reservation before making a billable request"
        raise httpx.ReadTimeout("test timeout")
    client = mod.MiMoClient(api_key="test-only", transport=httpx.MockTransport(handler))
    with pytest.raises(mod.MiMoError) as error:
        client.complete_json(Answer, [{"role": "user", "content": "JSON"}], budget=1,
                             on_request=reservations.append, on_usage=events.append)
    assert error.value.code == "PROVIDER_NETWORK_ERROR"
    assert reservations[0]["estimated_cost"] == events[0]["estimated_cost"] > 0


def test_provider_cancel_check_prevents_transport():
    mod = adapter()
    client = mod.MiMoClient(api_key="test-only", transport=httpx.MockTransport(lambda r: pytest.fail("canceled request")))
    with pytest.raises(mod.MiMoError) as error:
        client.complete_json(Answer, [], budget=1, check_cancel=lambda: True)
    assert error.value.code == "CANCELED"


def test_report_rejects_empty_script_and_findings():
    from app.schemas_ai import Report
    with pytest.raises(ValueError):
        Report(summary="测试", findings=[], titles=["一", "二", "三"], hooks=["一", "二", "三"], script="",
               tasks=["测试"], limitations=["测试"], source="mimo")


def test_local_report_declares_limits_and_does_not_invent_performance():
    assert importlib.util.find_spec("app.workflow") is not None, "durable workflow must be implemented"
    workflow = importlib.import_module("app.workflow")
    report = workflow.local_report({"title": "测试作品", "text": "先说明问题。再给一个例子。", "kind": "text", "data": {}})
    assert report.source == "local"
    assert len(report.hooks) == 3
    assert report.script
    assert any("未" in item for item in report.limitations)
    assert not any("播放" in item.evidence for item in report.findings)


def test_structured_evidence_rejects_invalid_confidence():
    assert importlib.util.find_spec("app.schemas_ai") is not None, "structured schemas must be implemented"
    schemas = importlib.import_module("app.schemas_ai")
    with pytest.raises(ValueError):
        schemas.Finding(label="观察", evidence="标题", location="title", confidence=1.5)


@pytest.fixture
def ai_database():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db import Base
    from app.models import ContentAnalysis, ContentItem, Organization, User
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        org = Organization(name="isolated test")
        db.add(org)
        db.flush()
        user = User(organization_id=org.id, email="ai@test.local", password_hash="not-a-real-login")
        content = ContentItem(organization_id=org.id, title="演示测试", text="一段明确标记的测试文稿。")
        db.add_all([user, content])
        db.flush()
        analysis = ContentAnalysis(organization_id=org.id, content_id=content.id, mode="local")
        db.add(analysis)
        db.commit()
        yield factory, db, user, content, analysis
    engine.dispose()


def test_workflow_persists_seven_stages_and_skips_successful_nodes_on_retry(ai_database, monkeypatch):
    from sqlalchemy import select
    from app import workflow
    from app.models import AgentRun, AgentStep
    factory, db, user, content, analysis = ai_database
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "local"), 0, False)
    original = workflow._execute_stage
    failed = []
    def fail_once(name, *args):
        if name == "strategy" and not failed:
            failed.append(True)
            raise workflow.MiMoError("SIMULATED_FAILURE", "可重试测试失败")
        return original(name, *args)
    monkeypatch.setattr(workflow, "_execute_stage", fail_once)
    workflow.execute_run(run.id, factory)
    db.expire_all()
    assert db.get(AgentRun, run.id).status == "FAILED"
    db.get(AgentRun, run.id).status = "QUEUED"
    db.commit()
    workflow.execute_run(run.id, factory)
    db.expire_all()
    steps = {s.name: s for s in db.scalars(select(AgentStep).where(AgentStep.run_id == run.id))}
    assert len(steps) == 7
    assert all(s.status == "SUCCEEDED" for s in steps.values())
    assert steps["COO"].attempts == 1
    assert steps["content"].attempts == 1
    assert steps["strategy"].attempts == 2
    assert db.get(AgentRun, run.id).cost == 0


def test_startup_marks_interrupted_tasks_failed_without_provider_call(ai_database):
    from app import workflow
    from app.models import AgentRun
    factory, db, user, content, analysis = ai_database
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "local"), 0, False)
    assert workflow.recover_interrupted_tasks(factory) == 1
    db.expire_all()
    assert db.get(AgentRun, run.id).status == "FAILED"
    assert "PROCESS_INTERRUPTED" in db.get(AgentRun, run.id).error


def test_strategy_draft_does_not_require_provider_to_repeat_observed_evidence(ai_database):
    from app import workflow
    from app.models import AgentRun, ContentAnalysis
    factory, db, user, content, analysis = ai_database
    analysis.mode = "ai"
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "ai"), 1, True)
    models = []
    def reply(request):
        payload = json.loads(request.content)
        models.append(payload["model"])
        if "flash" in payload["model"]:
            draft = {"topic": "编程教育", "audience": "入门者", "opening_hook": "重复代码的问题", "narrative": ["示例"], "visual_observations": [], "findings": [{"label": "文稿证据", "evidence": "测试文稿", "location": "全文", "confidence": 1}], "limitations": ["未转录"]}
        else:
            draft = {"titles": ["候选一", "候选二", "候选三"], "hooks": ["提问", "演示", "场景"], "script": "可编辑的完整脚本。", "tasks": ["缩短开头"], "experiments": ["保持内容长度，比较不同开头"]}
        return completion(json.dumps(draft))
    provider = adapter().MiMoClient(api_key="test-only", transport=httpx.MockTransport(reply))
    workflow.execute_run(run.id, factory, lambda: provider)
    db.expire_all()
    assert db.get(AgentRun, run.id).status == "SUCCEEDED"
    report = db.get(ContentAnalysis, analysis.id).report
    assert report["source"] == "mimo"
    assert report["findings"][0]["evidence"] == "测试文稿"
    assert report["script"] == "可编辑的完整脚本。"
    assert len(models) == 2


def test_invalid_ai_output_preserves_three_cost_events_and_repair_logs(ai_database):
    from sqlalchemy import select
    from app import workflow
    from app.models import AgentRun, AuditLog, CostEvent
    factory, db, user, content, analysis = ai_database
    analysis.mode = "ai"
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "ai"), 1, True)
    provider = adapter().MiMoClient(api_key="test-only", transport=httpx.MockTransport(lambda r: completion("{}")))
    workflow.execute_run(run.id, factory, lambda: provider)
    db.expire_all()
    persisted = db.get(AgentRun, run.id)
    events = db.scalars(select(CostEvent).where(CostEvent.run_id == run.id)).all()
    logs = db.scalars(select(AuditLog).where(AuditLog.action == "agent.output_invalid")).all()
    assert persisted.status == "FAILED" and "INVALID_MODEL_OUTPUT" in persisted.error
    assert len(events) == 3 and len(logs) == 3
    assert persisted.cost == pytest.approx(sum(e.estimated_cost for e in events))
    assert persisted.cost > 0


def test_process_interruption_preserves_in_flight_reservation(ai_database):
    from sqlalchemy import select
    from app import workflow
    from app.models import AgentRun, CostEvent
    factory, db, user, content, analysis = ai_database
    analysis.mode = "ai"
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "ai"), 1, True)
    def crash(request):
        raise SystemExit("simulate process termination after request reservation")
    provider = adapter().MiMoClient(api_key="test-only", transport=httpx.MockTransport(crash))
    with pytest.raises(SystemExit):
        workflow.execute_run(run.id, factory, lambda: provider)
    db.expire_all()
    event = db.scalar(select(CostEvent).where(CostEvent.run_id == run.id))
    assert event.data["status"] == "in_flight"
    assert db.get(AgentRun, run.id).cost == event.estimated_cost > 0
    assert workflow.recover_interrupted_tasks(factory) == 1


def test_compliance_review_pauses_and_approved_resume_does_not_repeat_stages(ai_database, monkeypatch):
    from sqlalchemy import select
    from app import workflow
    from app.models import AgentRun, AgentStep, Approval
    factory, db, user, content, analysis = ai_database
    user.role = "OWNER_ADMIN"
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "local"), 0, False)
    original = workflow._execute_stage
    def mark_review(name, *args):
        output = original(name, *args)
        if name == "strategy":
            output.requires_human_review = True
            output.review_reason = "TEST：重大合规问题需人工复核"
        return output
    monkeypatch.setattr(workflow, "_execute_stage", mark_review)
    workflow.execute_run(run.id, factory)
    db.expire_all()
    assert db.get(AgentRun, run.id).status == "WAITING_APPROVAL"
    approval = db.scalar(select(Approval).where(Approval.target_id == run.id))
    assert approval.kind == "COMPLIANCE_REVIEW"
    callback, args = workflow.apply_compliance_decision(db, approval, "APPROVED", user)
    approval.status = "APPROVED"
    db.commit()
    callback(*args)
    db.expire_all()
    assert db.get(AgentRun, run.id).status == "SUCCEEDED"
    steps = list(db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)))
    assert all(step.attempts == 1 for step in steps)


def test_quality_removes_unverified_urls_from_every_report_field(ai_database):
    from app import workflow
    factory, db, user, content, analysis = ai_database
    report = workflow.local_report({"title": "测试", "text": "正文"})
    report.titles[0] = "参考 https://unverified.invalid/fake"
    report.findings[0].evidence = "假引用 https://unverified.invalid/fake"
    result = workflow._execute_stage("quality", {"report": report.model_dump(), "allowed_urls": [], "media_received": False},
                                     db, None, None, {"mode": "local"}, None)
    assert "https://unverified.invalid" not in result.report.model_dump_json()


def test_private_video_uses_base64_content_level_fps_and_skips_generated_frames(ai_database, tmp_path):
    from app import workflow
    from app.models import ContentAsset
    factory, db, user, content, analysis = ai_database
    path = tmp_path / "test.mp4"
    path.write_bytes(b"TEST private video")
    video = ContentAsset(organization_id=user.organization_id, content_id=content.id, path=str(path),
                         original_name="test.mp4", mime="video/mp4", size=path.stat().st_size,
                         data={"role": "original", "metadata": {"duration": 60, "width": 1920, "height": 1080}})
    frame = ContentAsset(organization_id=user.organization_id, content_id=content.id, path=str(path),
                         original_name="keyframe.jpg", mime="image/jpeg", size=18, data={"role": "keyframe"})
    db.add_all([video, frame])
    db.commit()
    parts, limitations, tokens = workflow._media_parts(db, workflow.take_snapshot(db, content, "ai"))
    assert len(parts) == 1
    assert parts[0]["video_url"]["url"].startswith("data:video/mp4;base64,")
    assert parts[0]["fps"] == 2 and "fps" not in parts[0]["video_url"]
    assert parts[0]["media_resolution"] == "default"
    assert 18_000 < tokens < 30_000  # conservative default-resolution budget, not full-resolution frames


def test_cancel_does_not_overwrite_a_concurrently_completed_run(ai_database):
    from fastapi import HTTPException
    from app import workflow
    from app.analysis import cancel_task
    from app.models import AgentRun
    factory, db, user, content, analysis = ai_database
    run = workflow.create_run(db, analysis, workflow.take_snapshot(db, content, "local"), 0, False)
    run.status = "RUNNING"
    db.commit()
    with factory() as other:
        other.get(AgentRun, run.id).status = "SUCCEEDED"
        other.commit()
    # The request's identity map still sees RUNNING, as can happen at a race boundary.
    assert run.status == "RUNNING"
    with pytest.raises(HTTPException) as error:
        cancel_task(run.id, db, user)
    assert error.value.status_code == 409
    db.expire_all()
    assert db.get(AgentRun, run.id).status == "SUCCEEDED"


def test_api_local_analysis_cache_and_paid_consent_and_org_isolation(ai_database, monkeypatch):
    assert importlib.util.find_spec("app.analysis") is not None, "analysis API must be implemented"
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.analysis import router
    from app.auth import current_user
    from app.db import get_db
    from app.models import Organization, User
    factory, db, user, content, analysis = ai_database
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user] = lambda: user
    def test_db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = test_db
    monkeypatch.setenv("MIMO_API_KEY", "")
    with TestClient(app) as client:
        local = client.post("/api/analyses", json={"content_id": content.id, "mode": "local"})
        assert local.status_code == 200, local.text
        local_id = local.json()["id"]
        assert client.get("/api/analyses/" + local_id).json()["status"] == "SUCCEEDED"
        cached = client.post("/api/analyses", json={"content_id": content.id, "mode": "local"})
        assert cached.json()["id"] == local_id and cached.json()["cached"] is True
        paid = client.post("/api/analyses", json={"content_id": content.id, "mode": "ai"}).json()
        denied = client.post(f"/api/analyses/{paid['id']}/start", json={"confirm_paid": False, "budget": 1})
        assert denied.status_code == 400
        not_configured = client.post(f"/api/analyses/{paid['id']}/start", json={"confirm_paid": True, "budget": 1})
        assert not_configured.status_code == 503
        org2 = Organization(name="second org")
        db.add(org2)
        db.flush()
        other = User(organization_id=org2.id, email="other@test.local", password_hash="unused")
        db.add(other)
        db.commit()
        app.dependency_overrides[current_user] = lambda: other
        assert client.get("/api/analyses/" + local_id).status_code == 404
