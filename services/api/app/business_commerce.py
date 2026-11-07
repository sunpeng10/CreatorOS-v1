"""Auditable sales and DEMO fulfilment; no payment provider or external sending."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .auth import current_user, optional_user, owned, require_admin
from .db import get_db
from .models import (AgentRun, AgentStep, Approval, AuditLog, BenchmarkItem,
                     ContentAnalysis, ContentItem, CostEvent, Delivery, Lead,
                     MetricSnapshot, Order, PaymentRecord, Quote, ServicePlan,
                     Ticket, User, serialize, stamp)
from .business_common import audit, extras, fail, listing, money, required, rows, save, update_data

router = APIRouter(tags=["business"])


def company_owner(db):
    user = db.scalar(select(User).where(User.role == "OWNER_ADMIN").order_by(User.created_at, User.id))
    if not user:
        fail("服务尚未初始化，请先通过本地初始化命令创建老板管理员", 503)
    return user


def customer_fields(source):
    return {key: (source.data or {})[key] for key in ["customer_user_id", "customer_organization_id"] if (source.data or {}).get(key)}


def accessible_order(db, order_id, user):
    order = db.get(Order, order_id)
    if not order or (order.organization_id != user.organization_id and (order.data or {}).get("customer_organization_id") != user.organization_id):
        fail("记录不存在或无权访问", 404)
    return order


def order_view(db, order):
    deliveries = db.scalars(select(Delivery).where(Delivery.organization_id == order.organization_id, Delivery.order_id == order.id).order_by(Delivery.created_at)).all()
    payment = db.scalar(select(PaymentRecord).where(PaymentRecord.organization_id == order.organization_id, PaymentRecord.order_id == order.id))
    ticket_count = len(list(db.scalars(select(Ticket.id).where(Ticket.organization_id == order.organization_id, Ticket.order_id == order.id))))
    return {**serialize(order), "deliveries": [serialize(item) for item in deliveries], "ticket_count": ticket_count, "payment": serialize(payment) if payment else None, "payment_notice": "DEMO 模拟交易，未收取真实款项" if order.is_demo else "真实支付未配置"}


@router.post("/leads")
def create_lead(request: Request, body: dict = Body(...), db: Session = Depends(get_db)):
    owner = company_owner(db)
    customer = optional_user(request, db)
    data = {"timeline": [{"at": stamp(), "event": "官网留资"}], "next_action": "人工联系并核实需求"}
    if customer:
        data.update({"customer_user_id": customer.id, "customer_organization_id": customer.organization_id})
    lead = Lead(organization_id=owner.organization_id, contact=required(body, "contact", 300), need=required(body, "need", 6000), campaign=str(body.get("campaign") or "官网")[:100], status="NEW", data=data)
    db.add(lead); db.flush()
    db.add(AuditLog(organization_id=owner.organization_id, actor_id=customer.id if customer else None, action="lead.created", target_id=lead.id))
    db.commit()
    return {"id": lead.id, "status": lead.status, "message": "需求已保存，等待人工跟进"}


@router.get("/services")
def public_services(db: Session = Depends(get_db)):
    owners = db.scalars(select(User).where(User.role == "OWNER_ADMIN").order_by(User.created_at, User.id)).all()
    if not owners:
        return {"items": [], "total": 0}
    services = [item for item in rows(db, ServicePlan, owners[0]) if item.active]
    return listing([{"id": item.id, "name": item.name, "price": item.price, "description": (item.data or {}).get("description", ""), "features": (item.data or {}).get("features", []), "notice": "试运营报价，实际订单须人工审批"} for item in services])


@router.get("/orders")
def client_orders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    candidates = list(db.scalars(select(Order).order_by(Order.created_at.desc())))
    items = [order_view(db, order) for order in candidates if order.organization_id == user.organization_id or (order.data or {}).get("customer_organization_id") == user.organization_id]
    return listing(items)


@router.post("/orders/{order_id}/accept")
def accept_order(order_id: str, body: dict = Body(default={}), db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = accessible_order(db, order_id, user)
    if order.status == "COMPLETED":
        return order_view(db, order)
    if order.status != "DELIVERED":
        fail("仅已交付的订单可以验收", 409)
    order.status = "COMPLETED"
    update_data(order, {"accepted_at": stamp(), "accepted_by": user.id, "feedback": str(body.get("feedback") or "")[:3000]})
    db.add(AuditLog(organization_id=order.organization_id, actor_id=user.id, action="order.accepted", target_id=order.id))
    db.commit()
    return order_view(db, order)


@router.get("/admin/leads")
def leads(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing(rows(db, Lead, user))


@router.get("/admin/leads/{lead_id}")
def get_lead(lead_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return serialize(owned(db, Lead, lead_id, user))


@router.patch("/admin/leads/{lead_id}")
def edit_lead(lead_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    lead = owned(db, Lead, lead_id, user)
    if body.get('customer_reply'):
        reply = required(body, 'customer_reply', 6000)
        recipient = db.get(User, (lead.data or {}).get('customer_user_id')) if (lead.data or {}).get('customer_user_id') else None
        if not recipient or recipient.organization_id != (lead.data or {}).get('customer_organization_id'):
            fail('此线索未关联登录客户，无法站内回复。请通过客户提供的联系方式人工联系。')
        ticket = db.scalar(select(Ticket).where(Ticket.organization_id == user.organization_id, Ticket.data['lead_id'].as_string() == lead.id))
        if ticket and (ticket.data or {}).get('customer_organization_id') != recipient.organization_id:
            fail('线索与工单客户不匹配', 409)
        if not ticket:
            ticket = Ticket(organization_id=user.organization_id, subject=f'需求跟进·{lead.need[:80]}', status='IN_PROGRESS', data={**customer_fields(lead), 'lead_id': lead.id, 'kind': 'QUESTION', 'description': lead.need, 'timeline': []})
            db.add(ticket)
            db.flush()
        update_data(ticket, {'reply': reply, 'timeline': [*(ticket.data or {}).get('timeline', []), {'at': stamp(), 'actor_id': user.id, 'role': 'OWNER_ADMIN', 'note': reply}][-100:]})
        update_data(lead, {'customer_ticket_id': ticket.id})
        audit(db, user, 'lead.customer_replied', ticket.id, {'lead_id': lead.id})
    if "status" in body:
        if body["status"] not in {"NEW", "QUALIFIED", "PROPOSAL", "WON", "LOST"}:
            fail("无效线索状态")
        lead.status = body["status"]
    for key in ["contact", "need", "campaign"]:
        if key in body:
            setattr(lead, key, required(body, key, 6000 if key == "need" else 300))
    changes = extras(body, ["notes", "next_action"])
    changes["timeline"] = [*(lead.data or {}).get("timeline", []), {"at": stamp(), "actor_id": user.id, "status": lead.status, "note": str(body.get("notes") or "更新线索")[:6000]}][-100:]
    update_data(lead, changes)
    return save(db, lead, user, "lead.updated")


@router.get("/admin/services")
def admin_services(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing(rows(db, ServicePlan, user))


@router.post("/admin/services")
def create_service(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    service = ServicePlan(organization_id=user.organization_id, name=required(body, "name", 200), price=money(body.get("price", 0), "price"), active=bool(body.get("active", True)), data=extras(body, ["description", "features", "delivery_days"]))
    return save(db, service, user, "service.created")


@router.get("/admin/services/{service_id}")
def get_service(service_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return serialize(owned(db, ServicePlan, service_id, user))


@router.patch("/admin/services/{service_id}")
def edit_service(service_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    service = owned(db, ServicePlan, service_id, user)
    if "name" in body:
        service.name = required(body, "name", 200)
    if "price" in body:
        service.price = money(body["price"], "price")
    if "active" in body:
        if not isinstance(body["active"], bool):
            fail("active 必须为布尔值")
        service.active = body["active"]
    update_data(service, extras(body, ["description", "features", "delivery_days"]))
    return save(db, service, user, "service.updated")


@router.get("/admin/quotes")
def quotes(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing(rows(db, Quote, user))


@router.post("/admin/quotes")
def create_quote(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    lead = owned(db, Lead, body["lead_id"], user) if body.get("lead_id") else None
    service = owned(db, ServicePlan, body["service_id"], user) if body.get("service_id") else None
    if service and not service.active:
        fail("停用的服务不能生成报价", 409)
    amount = money(body.get("amount", service.price if service else None))
    data = extras(body, ["description", "scope", "valid_until", "notes"])
    if lead:
        data.update(customer_fields(lead))
    if service:
        data["service_snapshot"] = {"name": service.name, "price": service.price, "description": (service.data or {}).get("description", "")}
    quote = Quote(organization_id=user.organization_id, lead_id=lead.id if lead else None, service_id=service.id if service else None, amount=amount, status="PENDING_APPROVAL", data=data)
    db.add(quote); db.flush()
    approval = Approval(organization_id=user.organization_id, kind="QUOTE", target_id=quote.id, status="PENDING", reason="报价需人工核对金额与交付范围", data={"amount": amount, "quote_snapshot": serialize(quote)})
    db.add(approval); db.flush()
    audit(db, user, "quote.created", quote.id, {"approval_id": approval.id})
    db.commit()
    return {**serialize(quote), "approval_id": approval.id}


@router.patch("/admin/quotes/{quote_id}")
def edit_quote(quote_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    quote = owned(db, Quote, quote_id, user)
    if quote.status == "APPROVED" or db.scalar(select(Order).where(Order.quote_id == quote.id)):
        fail("已审批报价不可修改；请创建新的报价并重新审批", 409)
    if "amount" in body:
        quote.amount = money(body["amount"])
    update_data(quote, extras(body, ["description", "scope", "valid_until", "notes"]))
    for approval in db.scalars(select(Approval).where(Approval.organization_id == user.organization_id, Approval.kind == "QUOTE", Approval.target_id == quote.id, Approval.status == "PENDING")):
        approval.status = "SUPERSEDED"
    quote.status = "PENDING_APPROVAL"
    approval = Approval(organization_id=user.organization_id, kind="QUOTE", target_id=quote.id, status="PENDING", reason="报价变更，需重新审批", data={"amount": quote.amount, "quote_snapshot": serialize(quote)})
    db.add(approval); db.flush()
    audit(db, user, "quote.revised", quote.id)
    db.commit()
    return {**serialize(quote), "approval_id": approval.id}


@router.get("/admin/orders")
def admin_orders(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing([order_view(db, order) for order in rows(db, Order, user)])


@router.post("/admin/orders")
def create_order(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    quote = owned(db, Quote, required(body, "quote_id", 36), user)
    existing = db.scalar(select(Order).where(Order.organization_id == user.organization_id, Order.quote_id == quote.id))
    if existing:
        return order_view(db, existing)
    if quote.status != "APPROVED":
        fail("报价必须经人工批准后才能生成订单", 409)
    if body.get("is_demo", True) is not True:
        fail("真实支付供应商未配置，本地仅支持明确标记的 DEMO 订单", 409)
    order = Order(organization_id=user.organization_id, quote_id=quote.id, amount=quote.amount, status="AWAITING_PAYMENT", is_demo=True, data={**customer_fields(quote), "quote_snapshot": serialize(quote), "label": "DEMO 模拟订单，无真实付款"})
    db.add(order); db.flush()
    audit(db, user, "order.created", order.id)
    db.commit()
    return order_view(db, order)


@router.post("/admin/orders/{order_id}/simulate-payment")
def simulate_payment(order_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    order = owned(db, Order, order_id, user)
    if not order.is_demo:
        fail("模拟支付仅能用于 DEMO 订单", 409)
    existing = db.scalar(select(PaymentRecord).where(PaymentRecord.order_id == order.id, PaymentRecord.organization_id == user.organization_id))
    if existing:
        if existing.status == "DEMO_PAID":
            return order_view(db, order)
        fail("该支付已退款或终止，不可再次支付", 409)
    if order.status != "AWAITING_PAYMENT":
        fail("当前订单状态不允许模拟支付", 409)
    payment = PaymentRecord(organization_id=user.organization_id, order_id=order.id, amount=order.amount, is_demo=True, status="DEMO_PAID", data={"label": "DEMO 模拟记录，不是收款凭证", "provider": "local_demo", "confirmed_by": user.id})
    db.add(payment)
    order.status = "PAID"
    update_data(order, {"paid_at": stamp()})
    quote = owned(db, Quote, order.quote_id, user)
    if quote.lead_id:
        owned(db, Lead, quote.lead_id, user).status = "WON"
    audit(db, user, "order.demo_paid", order.id)
    db.commit()
    return order_view(db, order)


@router.post("/admin/orders/{order_id}/deliver")
def deliver_order(order_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    order = owned(db, Order, order_id, user)
    analysis_id = required(body, "analysis_id", 36)
    analysis = db.get(ContentAnalysis, analysis_id)
    allowed_org = (order.data or {}).get("customer_organization_id", user.organization_id)
    # A linked customer receives their own report; an admin-only demo stays in the admin workspace.
    if not analysis or analysis.organization_id != allowed_org:
        fail("报告不存在或不属于订单客户工作区", 404)
    if analysis.status != "SUCCEEDED" or not analysis.report:
        fail("仅能交付成功且包含报告的分析", 409)
    existing = db.scalar(select(Delivery).where(Delivery.organization_id == user.organization_id, Delivery.order_id == order.id, Delivery.analysis_id == analysis.id))
    if existing and order.status in {"DELIVERED", "COMPLETED"}:
        return order_view(db, order)
    if order.status not in {"PAID", "DELIVERED"}:
        fail("订单须先完成支付，才能交付报告", 409)
    delivery = Delivery(organization_id=user.organization_id, order_id=order.id, analysis_id=analysis.id, status="DELIVERED", data={"report_summary": analysis.report.get("summary", ""), "report_mode": analysis.mode, "report_owner_organization_id": analysis.organization_id, "delivered_by": user.id})
    db.add(delivery)
    order.status = "DELIVERED"
    update_data(order, {"delivered_at": stamp()})
    audit(db, user, "order.delivered", order.id, {"analysis_id": analysis.id})
    db.commit()
    return order_view(db, order)


def accessible_ticket(db, ticket_id, user):
    ticket = db.get(Ticket, ticket_id)
    if ticket and ticket.order_id:
        order = db.get(Order, ticket.order_id)
        if order and ticket.organization_id == order.organization_id and (order.data or {}).get('customer_organization_id') == user.organization_id:
            return ticket
    if not ticket or (ticket.organization_id != user.organization_id and (ticket.data or {}).get("customer_organization_id") != user.organization_id):
        fail("记录不存在或无权访问", 404)
    return ticket


@router.get("/tickets")
def tickets(db: Session = Depends(get_db), user: User = Depends(current_user)):
    items = list(db.scalars(select(Ticket).outerjoin(Order, and_(Ticket.order_id == Order.id, Ticket.organization_id == Order.organization_id))
                           .where(or_(Ticket.organization_id == user.organization_id, Ticket.data['customer_organization_id'].as_string() == user.organization_id,
                                      Order.data['customer_organization_id'].as_string() == user.organization_id)).order_by(Ticket.created_at.desc())))
    return listing(items)


@router.post("/tickets")
def create_ticket(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = accessible_order(db, body["order_id"], user) if body.get("order_id") else None
    kind = str(body.get("kind") or "QUESTION").upper()
    if kind not in {"QUESTION", "REVISION", "COMPLAINT", "REFUND"}:
        fail("工单类型无效")
    owner = company_owner(db) if user.role != "OWNER_ADMIN" and not order else user
    organization_id = order.organization_id if order else owner.organization_id
    recipient = customer_fields(order) if order and user.role == 'OWNER_ADMIN' else {'customer_user_id': user.id, 'customer_organization_id': user.organization_id}
    data = {"kind": kind, "description": str(body.get("description") or "")[:6000], **recipient, "timeline": [{"at": stamp(), "actor_id": user.id, "role": user.role, "event": "创建工单"}]}
    ticket = Ticket(organization_id=organization_id, order_id=order.id if order else None, subject=required(body, "subject", 300), status="WAITING_APPROVAL" if kind == "REFUND" else "OPEN", data=data)
    db.add(ticket); db.flush()
    if kind == "REFUND":
        approval = Approval(organization_id=organization_id, kind="REFUND", target_id=ticket.id, status="PENDING", reason="退款需人工批准；真实退款须另行配置支付供应商", data={"order_id": order.id if order else None, "amount": order.amount if order else None, "is_demo": order.is_demo if order else None})
        db.add(approval)
    db.add(AuditLog(organization_id=organization_id, actor_id=user.id, action="ticket.created", target_id=ticket.id))
    db.commit()
    return serialize(ticket)


@router.patch("/tickets/{ticket_id}")
def edit_ticket(ticket_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    ticket = accessible_ticket(db, ticket_id, user)
    if "status" in body:
        if ticket.status == "WAITING_APPROVAL":
            fail("审批中的工单不能直接变更状态，请使用人工审批入口", 409)
        if body["status"] not in {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}:
            fail("无效工单状态")
        if user.role != "OWNER_ADMIN" and body["status"] not in {"OPEN", "CLOSED"}:
            fail("客户只能重开或关闭自己的工单", 403)
        ticket.status = body["status"]
    reply = str(body.get('note') or body.get('reply') or '')[:6000]
    timeline = [*(ticket.data or {}).get("timeline", []), {"at": stamp(), "actor_id": user.id, "role": user.role, "status": ticket.status, "note": reply or '更新状态'}][-100:]
    changes = {'timeline': timeline}
    if user.role == 'OWNER_ADMIN' and reply:
        changes['reply'] = reply
    update_data(ticket, changes)
    db.add(AuditLog(organization_id=ticket.organization_id, actor_id=user.id, action="ticket.updated", target_id=ticket.id))
    db.commit()
    return serialize(ticket)


@router.get("/admin/tickets")
def admin_tickets(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing(rows(db, Ticket, user))


@router.get("/approvals")
def approvals(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing([approval_view(db, item) for item in rows(db, Approval, user)])


def approval_view(db, approval):
    result = serialize(approval)
    analysis = None
    organization_id = approval.organization_id
    if approval.kind == 'COMPLIANCE_REVIEW':
        run = db.get(AgentRun, approval.target_id)
        if run and (run.organization_id == organization_id or (
            approval.data.get('requester_org') == run.organization_id
            and approval.data.get('analysis_id') == run.analysis_id
        )):
            organization_id = run.organization_id
            analysis = db.get(ContentAnalysis, run.analysis_id)
    elif approval.kind == 'PUBLISH_CONTENT':
        analysis = db.get(ContentAnalysis, approval.target_id)
    if analysis and analysis.organization_id == organization_id:
        content = db.get(ContentItem, analysis.content_id)
        if content and content.organization_id == organization_id:
            result.update(content_title=content.title, target_name=content.title)
    if approval.kind == 'QUOTE':
        quote = db.get(Quote, approval.target_id)
        if quote and quote.organization_id == organization_id:
            service = db.get(ServicePlan, quote.service_id) if quote.service_id else None
            name = service.name if service and service.organization_id == organization_id else '服务报价'
            result['target_name'] = f'{name} · ¥{quote.amount:.2f}'
    return result


@router.post("/approvals/requests")
def request_manual_approval(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    kind = body.get("kind")
    if kind not in {"PUBLISH_CONTENT", "REAL_PAYMENT"}:
        fail("只支持 PUBLISH_CONTENT 或 REAL_PAYMENT 人工审批准备")
    target_id = required(body, "target_id", 36)
    reason = required(body, "reason", 3000)
    if kind == "PUBLISH_CONTENT":
        target = owned(db, ContentAnalysis, target_id, user)
        if target.status != "SUCCEEDED" or not target.report:
            fail("只有本组织已成功生成的报告可准备公开发布审批", 409)
        snapshot = {"type": "analysis", "id": target.id, "content_id": target.content_id, "status": target.status, "summary": target.report.get("summary", "")}
    else:
        target = db.get(Order, target_id)
        if target is not None:
            target = owned(db, Order, target_id, user)
            if target.status != "AWAITING_PAYMENT":
                fail("仅待支付订单可以准备真实付款审批", 409)
            snapshot = {"type": "order", "id": target.id, "amount": target.amount, "is_demo": target.is_demo, "status": target.status}
        else:
            target = owned(db, Quote, target_id, user)
            if target.status != "APPROVED":
                fail("报价需先经人工批准，才能准备真实付款审批", 409)
            snapshot = {"type": "quote", "id": target.id, "amount": target.amount, "status": target.status}
    existing = db.scalar(select(Approval).where(Approval.organization_id == user.organization_id, Approval.kind == kind, Approval.target_id == target_id, Approval.status == "PENDING"))
    if existing:
        return serialize(existing)
    approval = Approval(organization_id=user.organization_id, kind=kind, target_id=target_id, status="PENDING", reason=reason, data={"target_snapshot": snapshot, "requested_by": user.id, "execution_status": "NOT_EXECUTED", "execution_note": "仅准备人工审批。系统未连接发布或真实支付供应商，批准后仍需人工在授权渠道执行。"})
    return save(db, approval, user, "approval.requested")


@router.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: str, background: BackgroundTasks, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    approval = owned(db, Approval, approval_id, user)
    decision = body.get("decision")
    if decision not in {"APPROVED", "REJECTED"}:
        fail("decision 必须是 APPROVED 或 REJECTED")
    if approval.status != "PENDING":
        if approval.status == decision:
            return serialize(approval)
        fail("审批已处理或已失效，不能重复更改", 409)
    reason = required(body, "reason", 3000)
    resume = None
    if approval.kind == "QUOTE":
        quote = owned(db, Quote, approval.target_id, user)
        if quote.status != "PENDING_APPROVAL":
            fail("报价当前状态不允许审批", 409)
        if (approval.data or {}).get("amount") != quote.amount:
            fail("报价已变化，审批快照失效，请重新提交", 409)
        quote.status = decision
    elif approval.kind == "REFUND":
        ticket = owned(db, Ticket, approval.target_id, user)
        if decision == "APPROVED":
            order = owned(db, Order, ticket.order_id, user) if ticket.order_id else None
            payment = db.scalar(select(PaymentRecord).where(PaymentRecord.order_id == order.id, PaymentRecord.organization_id == user.organization_id)) if order else None
            if order and order.is_demo and payment and payment.is_demo and payment.status == "DEMO_PAID":
                payment.status = "DEMO_REFUNDED"
                order.status = "REFUNDED"
                ticket.status = "RESOLVED"
                update_data(ticket, {"resolution": "人工批准的 DEMO 模拟退款；无真实资金流动"})
            else:
                ticket.status = "IN_PROGRESS"
                update_data(ticket, {"resolution": "审批通过，等待人工核对并在授权支付渠道处理；系统未执行真实退款"})
        else:
            ticket.status = "RESOLVED"
            update_data(ticket, {"resolution": "人工拒绝退款请求"})
        update_data(ticket, {"timeline": [*(ticket.data or {}).get("timeline", []), {"at": stamp(), "actor_id": user.id, "event": decision, "note": reason}]})
    elif approval.kind == "COMPLIANCE_REVIEW":
        from .workflow import apply_compliance_decision
        resume = apply_compliance_decision(db, approval, decision, user)
    else:
        # Publication, real payments and data erasure remain explicit manual operations.
        update_data(approval, {"execution_status": "MANUAL_ACTION_REQUIRED" if decision == "APPROVED" else "NOT_EXECUTED", "execution_note": "仅记录人工审批；未自动外发、扣款或删除用户数据"})
    approval.status = decision
    approval.reason = reason
    update_data(approval, {"decided_by": user.id, "decided_at": stamp()})
    result = save(db, approval, user, "approval.decided")
    if resume:
        callback, arguments = resume
        background.add_task(callback, *arguments)
    return result


def total_amount(values):
    return float(sum((Decimal(str(value)) for value in values), Decimal("0")).quantize(Decimal("0.000001")))


def finance_summary(db, user, since=None):
    payments = [item for item in rows(db, PaymentRecord, user) if not since or item.created_at >= since]
    costs = [item for item in rows(db, CostEvent, user) if not since or item.created_at >= since]
    own_cost_ids = {item.id for item in costs}
    linked_analysis_ids = set()
    for delivery in rows(db, Delivery, user):
        order = db.get(Order, delivery.order_id)
        analysis = db.get(ContentAnalysis, delivery.analysis_id)
        if order and analysis and order.organization_id == user.organization_id and (order.data or {}).get("customer_organization_id") == analysis.organization_id:
            linked_analysis_ids.add(analysis.id)
    linked_costs = []
    if linked_analysis_ids:
        linked_runs = list(db.scalars(select(AgentRun).where(AgentRun.analysis_id.in_(linked_analysis_ids))))
        valid_runs = {run.id: run.organization_id for run in linked_runs if (db.get(ContentAnalysis, run.analysis_id).organization_id == run.organization_id)}
        if valid_runs:
            linked_costs = [item for item in db.scalars(select(CostEvent).where(CostEvent.run_id.in_(valid_runs))) if item.organization_id == valid_runs[item.run_id] and item.id not in own_cost_ids and (not since or item.created_at >= since)]
    costs.extend(linked_costs)
    orders = [item for item in rows(db, Order, user) if not since or item.created_at >= since]
    leads = [item for item in rows(db, Lead, user) if not since or item.created_at >= since]
    demo_paid = [item for item in payments if item.is_demo and item.status == "DEMO_PAID"]
    demo_refunds = [item for item in payments if item.is_demo and item.status == "DEMO_REFUNDED"]
    # Only a real provider's settled records could be included; no endpoint creates these.
    real_paid = [item for item in payments if not item.is_demo and item.status in {"PAID", "SUCCEEDED"}]
    demo_revenue = total_amount(item.amount for item in demo_paid)
    real_revenue = total_amount(item.amount for item in real_paid)
    cost = total_amount(item.estimated_cost for item in costs)
    won = sum(item.status == "WON" for item in leads)
    cost_rows = [{"id": item.id, "run_id": item.run_id, "model": item.model, "input_tokens": item.input_tokens, "output_tokens": item.output_tokens, "estimated_cost": item.estimated_cost, "created_at": item.created_at, "source": "本组织" if item.id in own_cost_ids else "明确关联的客户报告交付"} for item in costs]
    return {"currency": "CNY", "demo_revenue": demo_revenue, "demo_refunds": total_amount(item.amount for item in demo_refunds), "real_revenue": real_revenue, "model_cost_estimate": cost, "linked_customer_model_cost_estimate": total_amount(item.estimated_cost for item in linked_costs), "estimated_real_margin": round(real_revenue - cost, 6), "demo_order_count": sum(item.is_demo for item in orders), "real_order_count": sum(not item.is_demo for item in orders), "paid_order_count": len(demo_paid) + len(real_paid), "completed_order_count": sum(item.status == "COMPLETED" for item in orders), "funnel": {"leads": len(leads), "qualified": sum(item.status in {"QUALIFIED", "PROPOSAL", "WON"} for item in leads), "proposals": sum(item.status in {"PROPOSAL", "WON"} for item in leads), "won": won, "conversion_rate": round(won / len(leads), 4) if leads else None}, "cost_events": cost_rows, "payments": [serialize(item) for item in payments], "limitations": ["DEMO 收入与真实收入严格分开，模拟交易不属于实际经营收入。", "模型费用依据配置单价与用量估算，以供应商账单为准；仅纳入本组织及已明确关联交付的客户报告费用。", "真实毛利估算仅扣除已记录模型成本，未包含人工、税费、渠道和其他经营成本。"], "source": "本组织付款/CRM，以及本组织和明确关联客户交付的模型费用事件"}


@router.get("/admin/finance")
def finance(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return finance_summary(db, user)


@router.get("/admin/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    financial = finance_summary(db, user)
    orders = rows(db, Order, user)
    analyses = rows(db, ContentAnalysis, user)
    return {"leads": len(rows(db, Lead, user)), "trials": len(analyses), "customers": len({(lead.data or {}).get("customer_organization_id") for lead in rows(db, Lead, user) if (lead.data or {}).get("customer_organization_id")}), "orders": len(orders), "deals": sum(order.status in {"PAID", "DELIVERED", "COMPLETED"} for order in orders), "pending_approvals": sum(item.status == "PENDING" for item in rows(db, Approval, user)), "pending_deliveries": sum(item.status == "PAID" for item in orders), **financial}


@router.get("/admin/weekly-report")
def weekly_report(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    summary = finance_summary(db, user, start.isoformat())
    text = (f"# CreatorOS 经营周报\n\n统计窗口：{start.date()} 至 {end.date()}（UTC，最近 7 天）\n\n"
            f"新增线索：{summary['funnel']['leads']}；新增 DEMO 订单：{summary['demo_order_count']}；完成订单：{summary['completed_order_count']}。\n\n"
            f"DEMO 模拟收入：¥{summary['demo_revenue']:.2f}；真实收入：¥{summary['real_revenue']:.2f}；模型费用估算：¥{summary['model_cost_estimate']:.6f}。\n\n"
            "## 待办\n\n核对待审批报价、已付款未交付订单与工单；补充可验证的指标快照，再复盘实验。\n\n"
            "## 口径与限制\n\n仅统计本组织、创建时间在窗口内的记录。模拟收入不是真实营收；费用未含人工和税费；不从一次增长推断因果。")
    return {"generated_at": end.isoformat(), "period": {"from": start.isoformat(), "to": end.isoformat()}, "summary": summary, "markdown": text, "source": "确定性数据库统计，未调用付费模型"}


@router.get("/admin/agents")
def agent_runs(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    items = []
    for run in rows(db, AgentRun, user):
        steps = db.scalars(select(AgentStep).where(AgentStep.organization_id == user.organization_id, AgentStep.run_id == run.id).order_by(AgentStep.created_at, AgentStep.id)).all()
        items.append(safe_agent_snapshot({**serialize(run), "steps": [serialize(step) for step in steps]}))
    return listing(items)


def safe_agent_snapshot(value):
    if isinstance(value, dict):
        sensitive = {"api_key", "authorization", "password", "password_hash", "cookie", "set-cookie", "secret", "token", "access_token", "refresh_token", "token_hash"}
        return {key: "[REDACTED]" if key.lower() in sensitive or key.lower().endswith("_api_key") else safe_agent_snapshot(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_agent_snapshot(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?i)\b(?:sk-[a-z0-9_-]{8,}|Bearer\s+[a-z0-9._~-]+)", "[REDACTED]", value)
    return value


@router.get("/admin/data")
def admin_data(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    snapshots = rows(db, MetricSnapshot, user)
    imports = {}
    for item in snapshots:
        digest = (item.data or {}).get("file_sha256", item.import_hash)
        record = imports.setdefault(digest, {"source": item.source, "file_sha256": digest, "snapshots": 0, "created_at": item.created_at, "status": "IMPORTED"})
        record["snapshots"] += 1
    return {"counts": {"contents": len(rows(db, ContentItem, user)), "benchmarks": len(rows(db, BenchmarkItem, user)), "metric_snapshots": len(snapshots)}, "imports": list(imports.values()), "audit_logs": [serialize(item) for item in rows(db, AuditLog, user)[:200]], "backup_instructions": "先停止本项目服务，再复制 data/creatoros.db、data/uploads 与配置到受控私有备份；恢复前备份当前目录。SQLite 文件与上传文件必须保持同一时点。恢复为本机人工操作，接口不接受任意文件路径。", "privacy": "仅返回当前管理员组织的数据；删除用户数据须在审批中记录人工决定。"}
