"""Business acceptance tests: real database state, no external calls."""
import importlib.util
import io

import pytest


def test_business_module_exists():
    assert importlib.util.find_spec("app.business") is not None, "business router is not implemented"


def test_missing_metrics_stay_null_and_invalid_counts_rejected():
    from app.business_research import validate_metric_rows
    rows, errors = validate_metric_rows([{"title": "测试作品", "views": "100", "likes": "", "comments": "0"}], {})
    assert errors == []
    assert rows[0]["metrics"] == {"views": 100, "likes": None, "comments": 0, "shares": None, "favorites": None, "impressions": None, "followers": None}
    _, errors = validate_metric_rows([{"title": "负数", "views": "-5"}, {"title": "NaN", "views": "NaN"}], {})
    assert len(errors) == 2


def test_chinese_similarity_and_performance_are_separate():
    from app.business_research import rank_benchmarks
    rows = [
        {"id": "1", "title": "Python 编程入门", "author": "甲", "platform": "视频", "category": "编程", "views": 100},
        {"id": "2", "title": "Python 函数教学", "author": "甲", "platform": "视频", "category": "编程", "views": 200},
        {"id": "3", "title": "JavaScript 编程教学", "author": "甲", "platform": "视频", "category": "编程", "views": 300},
        {"id": "4", "title": "户外徒步露营", "author": "乙", "platform": "视频", "category": "生活", "views": 100000},
    ]
    result = rank_benchmarks("Python 编程入门", rows, 3)
    assert result[0]["id"] == "1"
    assert result[0]["relative_performance"] == 0.5
    assert result[0]["similarity"] > result[1]["similarity"]
    assert result[0]["reasons"]
    assert rank_benchmarks("户外", rows, 4)[0]["relative_performance"] is None


@pytest.fixture
def business_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.auth import current_user
    from app.db import get_db
    from app.models import Base, Organization, User
    from app.business import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        org = Organization(name="测试管理员组织")
        other = Organization(name="隔离组织")
        db.add_all([org, other]); db.flush()
        admin = User(email="business@example.test", name="测试管理员", password_hash="unused", organization_id=org.id, role="OWNER_ADMIN")
        client = User(email="client@example.test", name="测试客户", password_hash="unused", organization_id=other.id, role="CLIENT_USER")
        db.add_all([admin, client]); db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    active = {"user": admin}
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[current_user] = lambda: active["user"]
    # Preserve the real role check through its current_user dependency.
    with TestClient(app) as http:
        yield http, factory, active, admin, client
    engine.dispose()


def test_library_deduplication_and_org_isolation(business_client):
    http, _, active, admin, client = business_client
    payload = {"title": "Python 入门", "platform": "Bilibili", "url": "https://example.org/watch/1", "author": "作者", "category": "编程"}
    first = http.post("/api/library", json=payload)
    assert first.status_code == 200, first.text
    second = http.post("/api/library", json=payload)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert http.get("/api/library").json()["total"] == 1
    active["user"] = client
    assert http.get("/api/library").json()["total"] == 0
    assert http.get("/api/library/" + first.json()["id"]).status_code == 404
    assert http.get("/api/admin/finance").status_code == 403


def test_metrics_preview_import_dedupe_and_null(business_client):
    http, _, _, _, _ = business_client
    csv = "title,views,likes,comments,observed_at\n测试作品,100,,0,2026-11-01\n".encode("utf-8-sig")
    preview = http.post("/api/metrics/preview", files={"file": ("metrics.csv", csv, "text/csv")})
    assert preview.status_code == 200, preview.text
    assert preview.json()["items"][0]["metrics"]["likes"] is None
    first = http.post("/api/metrics/import", files={"file": ("metrics.csv", csv, "text/csv")})
    assert first.status_code == 200, first.text
    assert first.json()["imported"] == 1
    second = http.post("/api/metrics/import", files={"file": ("renamed.csv", csv, "text/csv")})
    assert second.json()["imported"] == 0
    overview = http.get("/api/analytics/overview?denominator=views").json()
    assert overview["items"][0]["likes"] is None
    assert overview["items"][0]["engagement_rate"] is None
    assert http.get("/api/analytics/overview?denominator=invalid").status_code == 422


def test_order_requires_approval_payment_and_successful_analysis(business_client):
    http, factory, _, admin, _ = business_client
    from app.models import ContentItem, ContentAnalysis
    service = http.post("/api/admin/services", json={"name": "测试诊断", "price": 49}).json()
    quote = http.post("/api/admin/quotes", json={"service_id": service["id"], "amount": 49}).json()
    assert http.post("/api/admin/orders", json={"quote_id": quote["id"]}).status_code == 409
    approval = http.get("/api/approvals").json()["items"][0]
    approved = http.post("/api/approvals/" + approval["id"] + "/decision", json={"decision": "APPROVED", "reason": "人工确认演示报价"})
    assert approved.status_code == 200, approved.text
    order = http.post("/api/admin/orders", json={"quote_id": quote["id"]}).json()
    assert order["status"] == "AWAITING_PAYMENT"
    duplicate = http.post("/api/admin/orders", json={"quote_id": quote["id"]}).json()
    assert duplicate["id"] == order["id"]
    with factory() as db:
        content = ContentItem(organization_id=admin.organization_id, title="演示内容", kind="text", text="测试")
        db.add(content); db.flush()
        analysis = ContentAnalysis(organization_id=admin.organization_id, content_id=content.id, status="SUCCEEDED", mode="local", report={"summary": "基础分析"})
        db.add(analysis); db.commit()
        analysis_id = analysis.id
    url = "/api/admin/orders/" + order["id"]
    assert http.post(url + "/deliver", json={"analysis_id": analysis_id}).status_code == 409
    assert http.post(url + "/simulate-payment").status_code == 200
    assert http.post(url + "/simulate-payment").status_code == 200
    assert http.post(url + "/deliver", json={"analysis_id": analysis_id}).status_code == 200
    assert http.post("/api/orders/" + order["id"] + "/accept").json()["status"] == "COMPLETED"
    assert http.post("/api/orders/" + order["id"] + "/accept").status_code == 200
    finance = http.get("/api/admin/finance").json()
    assert finance["demo_revenue"] == 49
    assert finance["real_revenue"] == 0


def test_public_lead_ignores_caller_org_and_refund_needs_approval(business_client):
    http, _, active, admin, client = business_client
    active["user"] = client
    lead = http.post("/api/leads", json={"contact": "演示联系人", "need": "账号诊断", "organization_id": client.organization_id})
    assert lead.status_code == 200
    assert "organization_id" not in lead.json()
    active["user"] = admin
    saved = http.get("/api/admin/leads").json()["items"][0]
    assert saved["organization_id"] == admin.organization_id
    ticket = http.post("/api/tickets", json={"subject": "申请退款", "kind": "REFUND"}).json()
    assert ticket["status"] == "WAITING_APPROVAL"
    assert http.patch("/api/tickets/" + ticket["id"], json={"status": "RESOLVED"}).status_code == 409


def test_experiment_cannot_attach_other_org_content(business_client):
    http, factory, _, _, client = business_client
    from app.models import ContentItem
    with factory() as db:
        content = ContentItem(organization_id=client.organization_id, title="私有内容", kind="text", text="secret")
        db.add(content); db.commit(); content_id = content.id
    assert http.post("/api/experiments", json={"title": "违规关联", "content_id": content_id}).status_code == 404


def test_explicit_demo_import_remains_labeled_and_recommendations_exclude_it(business_client):
    http, _, _, _, _ = business_client
    csv = "title,platform,author,is_demo,views\nDEMO Python 入门,DEMO,DEMO 作者,true,100\n".encode("utf-8-sig")
    response = http.post("/api/library/import", files={"file": ("DEMO-library.csv", csv, "text/csv")})
    assert response.status_code == 200, response.text
    assert http.get("/api/library").json()["items"][0]["is_demo"] is True
    assert http.post("/api/recommendations/search", json={"query": "Python", "limit": 3}).json()["total"] == 0
    assert http.post("/api/recommendations/search", json={"query": "Python", "limit": 3, "include_demo": True}).json()["total"] == 1


def test_xlsx_mapping_and_malformed_workbook_are_validated(business_client):
    from openpyxl import Workbook
    http, _, _, _, _ = business_client
    book = Workbook(); sheet = book.active
    sheet.append(["自定义标题", "次数", "观测日期"])
    sheet.append(["DEMO 自定义列", 90, "2026-11-02"])
    output = io.BytesIO(); book.save(output)
    preview = http.post("/api/metrics/preview", data={"mapping": '{"title":"自定义标题","views":"次数"}'}, files={"file": ("DEMO.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert preview.status_code == 200, preview.text
    assert preview.json()["items"][0]["metrics"]["views"] == 90
    malformed = http.post("/api/metrics/preview", files={"file": ("bad.xlsx", b"not a workbook", "application/octet-stream")})
    assert malformed.status_code == 422


def test_revised_quote_supersedes_old_approval_and_approved_quote_is_frozen(business_client):
    http, _, _, _, _ = business_client
    first = http.post("/api/admin/quotes", json={"amount": 99}).json()
    second = http.patch("/api/admin/quotes/" + first["id"], json={"amount": 149}).json()
    old = http.post("/api/approvals/" + first["approval_id"] + "/decision", json={"decision": "APPROVED", "reason": "旧报价"})
    assert old.status_code == 409
    assert http.post("/api/approvals/" + second["approval_id"] + "/decision", json={"decision": "APPROVED", "reason": "新报价"}).status_code == 200
    assert http.patch("/api/admin/quotes/" + first["id"], json={"amount": 1}).status_code == 409


def test_empty_import_and_unsafe_library_url_are_rejected(business_client):
    http, _, _, _, _ = business_client
    response = http.post("/api/metrics/import", files={"file": ("empty.csv", b"title,views\n", "text/csv")})
    assert response.status_code == 422
    response = http.post("/api/library", json={"title": "无效链接", "url": "https://[invalid"})
    assert response.status_code == 422


def test_authenticated_customer_order_delivery_acceptance_and_refund(business_client):
    import hashlib
    from datetime import datetime, timedelta, timezone
    from app.auth import COOKIE
    from app.models import Session as UserSession, ContentItem, ContentAnalysis, User
    http, factory, active, admin, client = business_client
    token = "business-test-session-token"
    with factory() as db:
        db.add(UserSession(organization_id=client.organization_id, user_id=client.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        content = ContentItem(organization_id=client.organization_id, title="客户的分析资料", kind="text", text="有权限的客户资料")
        db.add(content); db.flush()
        analysis = ContentAnalysis(organization_id=client.organization_id, content_id=content.id, status="SUCCEEDED", mode="local", report={"summary": "客户自有报告"})
        db.add(analysis); db.commit(); analysis_id = analysis.id
    http.cookies.set(COOKIE, token)
    active["user"] = client
    lead = http.post("/api/leads", json={"contact": "TEST 客户", "need": "诊断", "organization_id": "attacker"}).json()
    active["user"] = admin
    saved = http.get("/api/admin/leads/" + lead["id"]).json()
    assert saved["customer_organization_id"] == client.organization_id
    quote = http.post("/api/admin/quotes", json={"lead_id": lead["id"], "amount": 89}).json()
    http.post("/api/approvals/" + quote["approval_id"] + "/decision", json={"decision": "APPROVED", "reason": "人工审阅"})
    order = http.post("/api/admin/orders", json={"quote_id": quote["id"]}).json()
    assert http.post("/api/admin/orders/" + order["id"] + "/simulate-payment").status_code == 200
    assert http.post("/api/admin/orders/" + order["id"] + "/deliver", json={"analysis_id": analysis_id}).status_code == 200
    active["user"] = User(id="stranger", organization_id="unrelated", email="stranger@example.test", role="CLIENT_USER", password_hash="unused")
    assert http.get("/api/orders").json()["total"] == 0
    assert http.post("/api/orders/" + order["id"] + "/accept").status_code == 404
    active["user"] = client
    assert http.get("/api/orders").json()["items"][0]["id"] == order["id"]
    assert http.post("/api/orders/" + order["id"] + "/accept").status_code == 200
    ticket = http.post("/api/tickets", json={"subject": "DEMO 退款", "kind": "REFUND", "order_id": order["id"]}).json()
    active["user"] = admin
    approval = next(item for item in http.get("/api/approvals").json()["items"] if item["target_id"] == ticket["id"])
    result = http.post("/api/approvals/" + approval["id"] + "/decision", json={"decision": "APPROVED", "reason": "人工批准 DEMO 退款"})
    assert result.status_code == 200, result.text
    assert http.post("/api/admin/orders/" + order["id"] + "/simulate-payment").status_code == 409
    finance = http.get("/api/admin/finance").json()
    assert finance["demo_revenue"] == 0 and finance["demo_refunds"] == 89 and finance["real_revenue"] == 0


def test_demo_metrics_label_is_preserved(business_client):
    http, _, _, _, _ = business_client
    csv = "title,views,is_demo\nDEMO 指标,100,true\n".encode("utf-8-sig")
    result = http.post("/api/metrics/import", files={"file": ("DEMO.csv", csv, "text/csv")})
    assert result.status_code == 200
    item = http.get("/api/analytics/overview").json()["items"][0]
    assert item["is_demo"] is True


@pytest.mark.parametrize("decision,expected_status", [("REJECTED", "CANCELED"), ("APPROVED", "QUEUED")])
def test_compliance_decision_updates_analysis_and_schedules_only_after_commit(business_client, monkeypatch, decision, expected_status):
    from app.models import ContentItem, ContentAnalysis, AgentRun, AgentStep, Approval
    import app.workflow as workflow
    http, factory, _, admin, _ = business_client
    callbacks = []
    def observe_committed_state(run_id, factory):
        with factory() as db:
            found = db.query(Approval).filter_by(target_id=run_id).one()
            assert found.status == "APPROVED"
            assert db.get(AgentRun, run_id).status == "QUEUED"
        callbacks.append(run_id)
    monkeypatch.setattr(workflow, "execute_run", observe_committed_state)
    with factory() as db:
        content = ContentItem(organization_id=admin.organization_id, title="合规待审", kind="text", text="测试")
        db.add(content); db.flush()
        analysis = ContentAnalysis(organization_id=admin.organization_id, content_id=content.id, status="WAITING_APPROVAL", mode="local")
        db.add(analysis); db.flush()
        run = AgentRun(organization_id=admin.organization_id, analysis_id=analysis.id, status="WAITING_APPROVAL")
        db.add(run); db.flush()
        db.add(AgentStep(organization_id=admin.organization_id, run_id=run.id, name="quality", status="WAITING_APPROVAL", input={}, output={}))
        approval = Approval(organization_id=admin.organization_id, target_id=run.id, kind="COMPLIANCE_REVIEW", status="PENDING")
        db.add(approval); db.commit(); approval_id, analysis_id = approval.id, analysis.id
    response = http.post("/api/approvals/" + approval_id + "/decision", json={"decision": decision, "reason": "人工核验合规结论"})
    assert response.status_code == 200, response.text
    with factory() as db:
        assert db.get(ContentAnalysis, analysis_id).status == expected_status
    assert len(callbacks) == (1 if decision == "APPROVED" else 0)


def test_high_risk_requests_only_record_approval_and_require_owned_targets(business_client):
    from app.models import ContentItem, ContentAnalysis
    http, factory, _, admin, client = business_client
    with factory() as db:
        content = ContentItem(organization_id=admin.organization_id, title="待公开测试", kind="text", text="未公开")
        private = ContentItem(organization_id=client.organization_id, title="客户私有", kind="text", text="未授权")
        db.add_all([content, private]); db.flush()
        analysis = ContentAnalysis(organization_id=admin.organization_id, content_id=content.id, status="SUCCEEDED", mode="local", report={"summary": "测试报告"})
        other = ContentAnalysis(organization_id=client.organization_id, content_id=private.id, status="SUCCEEDED", mode="local", report={"summary": "私有报告"})
        db.add_all([analysis, other]); db.commit(); analysis_id, other_id = analysis.id, other.id
    request = {"kind": "PUBLISH_CONTENT", "target_id": analysis_id, "reason": "人工准备发布审批"}
    created = http.post("/api/approvals/requests", json=request)
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "PENDING"
    duplicate = http.post("/api/approvals/requests", json=request)
    assert duplicate.json()["id"] == created.json()["id"]
    decision = http.post("/api/approvals/" + created.json()["id"] + "/decision", json={"decision": "APPROVED", "reason": "批准准备，等待人工发布"}).json()
    assert decision["execution_status"] == "MANUAL_ACTION_REQUIRED"
    assert http.post("/api/approvals/requests", json={**request, "target_id": other_id}).status_code == 404
    quote = http.post("/api/admin/quotes", json={"amount": 100}).json()
    payment_request = {"kind": "REAL_PAYMENT", "target_id": quote["id"], "reason": "准备真实支付配置"}
    assert http.post("/api/approvals/requests", json=payment_request).status_code == 409
    http.post("/api/approvals/" + quote["approval_id"] + "/decision", json={"decision": "APPROVED", "reason": "人工核验报价"})
    assert http.post("/api/approvals/requests", json=payment_request).status_code == 200
    assert http.get("/api/admin/finance").json()["real_revenue"] == 0


def test_finance_includes_costs_only_for_explicit_customer_deliveries(business_client):
    from app.models import ContentItem, ContentAnalysis, AgentRun, CostEvent, Quote, Order, Delivery
    http, factory, _, admin, client = business_client
    with factory() as db:
        content = ContentItem(organization_id=client.organization_id, title="客户付费分析", kind="text", text="测试")
        db.add(content); db.flush()
        linked = ContentAnalysis(organization_id=client.organization_id, content_id=content.id, status="SUCCEEDED", mode="ai")
        private = ContentAnalysis(organization_id=client.organization_id, content_id=content.id, status="SUCCEEDED", mode="ai")
        db.add_all([linked, private]); db.flush()
        linked_run = AgentRun(organization_id=client.organization_id, analysis_id=linked.id)
        private_run = AgentRun(organization_id=client.organization_id, analysis_id=private.id)
        db.add_all([linked_run, private_run]); db.flush()
        db.add(CostEvent(organization_id=client.organization_id, run_id=linked_run.id, model="test-model", estimated_cost=0.05))
        db.add(CostEvent(organization_id=client.organization_id, run_id=private_run.id, model="test-model", estimated_cost=9))
        quote = Quote(organization_id=admin.organization_id, amount=100, status="APPROVED")
        db.add(quote); db.flush()
        order = Order(organization_id=admin.organization_id, quote_id=quote.id, status="DELIVERED", data={"customer_organization_id": client.organization_id})
        db.add(order); db.flush()
        db.add(Delivery(organization_id=admin.organization_id, order_id=order.id, analysis_id=linked.id))
        db.commit()
    result = http.get("/api/admin/finance").json()
    assert result["model_cost_estimate"] == 0.05
    assert result["linked_customer_model_cost_estimate"] == 0.05


def test_agent_snapshot_redacts_credentials_without_losing_usage():
    from app.business_commerce import safe_agent_snapshot
    snapshot = {"input": {"api_key": "private-value", "authorization": "Bearer fake-test-credential"}, "output": "provider rejected sk-DEMOSECRET12345", "input_tokens": 33, "steps": [{"mimo_api_key": "another-private-value"}]}
    safe = safe_agent_snapshot(snapshot)
    assert safe["input"]["api_key"] == "[REDACTED]"
    assert safe["input"]["authorization"] == "[REDACTED]"
    assert "DEMOSECRET" not in safe["output"]
    assert safe["steps"][0]["mimo_api_key"] == "[REDACTED]"
    assert safe["input_tokens"] == 33
