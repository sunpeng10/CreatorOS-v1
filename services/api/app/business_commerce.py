"""Customer requests, service fulfilment and order-based revenue; no payment gateway."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .auth import current_user, owned, require_admin
from .db import get_db
from .models import (AgentRun, AgentStep, Approval, AuditLog, BenchmarkItem,
                     ContentAnalysis, ContentItem, CostEvent, Delivery, Lead,
                     MetricSnapshot, Order, PaymentRecord, Quote, ServicePlan,
                     Ticket, User, serialize, stamp)
from .business_common import audit, extras, fail, listing, money, required, rows, save, update_data
from .customer_links import customer_for, customer_fields as identity_fields, ensure_lead_ticket, is_demo_record

router = APIRouter(tags=["business"])


def company_owner(db):
    user = db.scalar(select(User).where(User.role == "OWNER_ADMIN").order_by(User.created_at, User.id))
    if not user:
        fail("服务尚未初始化，请先通过本地初始化命令创建老板管理员", 503)
    return user


def customer_fields(source):
    return {key: (source.data or {})[key] for key in ["customer_user_id", "customer_organization_id"] if (source.data or {}).get(key)}


def customer_records(db, model, user):
    items = []
    for record in rows(db, model, user):
        if is_demo_record(record):
            continue
        order = db.get(Order, record.order_id) if isinstance(record, Ticket) and record.order_id else None
        if order and is_demo_record(order):
            continue
        if customer_for(db, order or record):
            items.append(record)
    return items


def accessible_order(db, order_id, user):
    order = db.get(Order, order_id)
    customer = customer_for(db, order) if order else None
    if not order or is_demo_record(order) or not (user.role == 'OWNER_ADMIN' and order.organization_id == user.organization_id or customer and customer.id == user.id):
        fail("记录不存在或无权访问", 404)
    return order


def order_view(db, order):
    deliveries = db.scalars(select(Delivery).where(Delivery.organization_id == order.organization_id, Delivery.order_id == order.id).order_by(Delivery.created_at)).all()
    payment = db.scalar(select(PaymentRecord).where(PaymentRecord.organization_id == order.organization_id, PaymentRecord.order_id == order.id))
    ticket_count = len(list(db.scalars(select(Ticket.id).where(Ticket.organization_id == order.organization_id, Ticket.order_id == order.id))))
    return {**serialize(order), 'title': (order.data or {}).get('title') or (order.data or {}).get('quote_snapshot', {}).get('service_snapshot', {}).get('name') or '定制服务', "deliveries": [serialize(item) for item in deliveries], "ticket_count": ticket_count, "payment": serialize(payment) if payment else None, "payment_notice": "按已接单金额记账，尚未接入资金支付"}


@router.post("/leads")
def create_lead(body: dict = Body(...), db: Session = Depends(get_db), customer: User = Depends(current_user)):
    owner = company_owner(db)
    if customer.role != 'CLIENT_USER':
        fail('请使用客户账号提交需求', 403)
    contact = required(body, 'contact', 300)
    if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', contact) and contact.lower() != customer.email.lower():
        fail('联系邮箱与当前登录账号不一致，请切换到对应账号后提交。')
    data = {**identity_fields(customer), 'origin': 'customer_submission', "timeline": [{"at": stamp(), "event": "客户提交需求"}], "next_action": "人工联系并核实需求"}
    lead = Lead(organization_id=owner.organization_id, contact=contact, need=required(body, "need", 6000), campaign=str(body.get("campaign") or "官网")[:100], status="NEW", data=data)
    db.add(lead); db.flush()
    ensure_lead_ticket(db, lead)
    db.add(AuditLog(organization_id=owner.organization_id, actor_id=customer.id if customer else None, action="lead.created", target_id=lead.id))
    db.commit()
    return {"id": lead.id, "status": lead.status, "message": "需求已保存，等待人工跟进"}


@router.get("/services")
def public_services(db: Session = Depends(get_db)):
    owners = db.scalars(select(User).where(User.role == "OWNER_ADMIN").order_by(User.created_at, User.id)).all()
    if not owners:
        return {"items": [], "total": 0}
    services = sorted([item for item in rows(db, ServicePlan, owners[0]) if item.active], key=lambda item: (item.price, item.name, item.id))
    return listing([{"id": item.id, "name": item.name, "price": item.price, "description": (item.data or {}).get("description", ""), "features": (item.data or {}).get("features", []), "notice": "客户确认下单后，由老板接单处理"} for item in services])


@router.get("/orders")
def client_orders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    candidates = list(db.scalars(select(Order).order_by(Order.created_at.desc())))
    items = [order_view(db, order) for order in candidates if not is_demo_record(order) and (user.role == 'OWNER_ADMIN' and order.organization_id == user.organization_id or customer_for(db, order) and customer_for(db, order).id == user.id)]
    return listing(items)


@router.post('/orders')
def purchase_service(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != 'CLIENT_USER':
        fail('请使用客户账号下单', 403)
    owner = company_owner(db)
    service = owned(db, ServicePlan, required(body, 'service_id', 36), owner)
    if not service.active:
        fail('此服务已停用，请重新选择', 409)
    request_id = required(body, 'request_id', 100)
    quote_id = str(uuid5(NAMESPACE_URL, f'creatoros:checkout:{user.id}:{request_id}'))
    existing = db.scalar(select(Order).where(Order.quote_id == quote_id))
    if existing:
        return order_view(db, accessible_order(db, existing.id, user))
    need = required(body, 'need', 6000)
    link = identity_fields(user)
    lead = Lead(organization_id=owner.organization_id, contact=user.email, need=need, campaign='服务下单', status='PROPOSAL', data={**link, 'origin': 'customer_order'})
    db.add(lead); db.flush()
    quote = Quote(id=quote_id, organization_id=owner.organization_id, lead_id=lead.id, service_id=service.id, amount=service.price, status='APPROVED',
                  data={**link, 'origin': 'published_service', 'scope': need, 'service_snapshot': {'name': service.name, 'price': service.price}})
    try:
        db.add(quote); db.flush()
        order = Order(organization_id=owner.organization_id, quote_id=quote.id, amount=service.price, status='REQUESTED', is_demo=False,
                      data={**link, 'origin': 'customer_order', 'title': service.name, 'need': need, 'customer_confirmed_at': stamp(), 'quote_snapshot': serialize(quote)})
        db.add(order); db.flush()
        ticket = ensure_lead_ticket(db, lead)
        ticket.order_id = order.id
        audit(db, user, 'order.customer_created', order.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Order).where(Order.quote_id == quote_id))
        if not existing:
            raise
        order = accessible_order(db, existing.id, user)
    return order_view(db, order)


@router.post('/orders/{order_id}/confirm')
def confirm_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = accessible_order(db, order_id, user)
    if user.role != 'CLIENT_USER':
        fail('仅订单客户可确认下单', 403)
    if order.status == 'AWAITING_CUSTOMER':
        order.status = 'REQUESTED'
        update_data(order, {'customer_confirmed_at': stamp()})
        audit(db, user, 'order.customer_confirmed', order.id)
        db.commit()
    elif order.status != 'REQUESTED':
        fail('订单当前不能确认', 409)
    return order_view(db, order)


@router.post("/orders/{order_id}/accept")
def accept_order(order_id: str, body: dict = Body(default={}), db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = accessible_order(db, order_id, user)
    if user.role != 'CLIENT_USER':
        fail('仅订单客户可确认验收', 403)
    if order.status == "COMPLETED":
        return order_view(db, order)
    if order.status != "DELIVERED":
        fail("仅已交付的订单可以验收", 409)
    if body.get('confirm_acceptance') is not True:
        fail('请阅读验收提示并明确确认后再验收。', 422)
    order.status = "COMPLETED"
    update_data(order, {"completed_at": stamp(), "completed_by": user.id, 'acceptance_policy_version': '2026-11-08', 'acceptance_confirmed': True, "feedback": str(body.get("feedback") or "")[:3000]})
    db.add(AuditLog(organization_id=order.organization_id, actor_id=user.id, action="order.accepted", target_id=order.id))
    db.commit()
    return order_view(db, order)


@router.get("/admin/leads")
def leads(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing(customer_records(db, Lead, user))


@router.get("/admin/leads/{lead_id}")
def get_lead(lead_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return serialize(owned(db, Lead, lead_id, user))


@router.patch("/admin/leads/{lead_id}")
def edit_lead(lead_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    lead = owned(db, Lead, lead_id, user)
    ticket = ensure_lead_ticket(db, lead)
    if body.get('customer_reply'):
        reply = required(body, 'customer_reply', 6000)
        if not ticket:
            fail('此线索未关联登录客户，无法站内回复。请通过客户提供的联系方式人工联系。')
        update_data(ticket, {'reply': reply, 'timeline': [*(ticket.data or {}).get('timeline', []), {'at': stamp(), 'actor_id': user.id, 'role': 'OWNER_ADMIN', 'note': reply}][-100:]})
        update_data(lead, {'customer_ticket_id': ticket.id})
        audit(db, user, 'lead.customer_replied', ticket.id, {'lead_id': lead.id})
    if "status" in body:
        if body["status"] not in {"NEW", "QUALIFIED", "PROPOSAL", "WON", "LOST"}:
            fail("无效线索状态")
        lead.status = body["status"]
        if ticket:
            ticket.status = {'NEW': 'OPEN', 'QUALIFIED': 'IN_PROGRESS', 'PROPOSAL': 'IN_PROGRESS', 'WON': 'RESOLVED', 'LOST': 'CLOSED'}[lead.status]
    if ticket:
        update_data(ticket, {'lead_status': lead.status})
    for key in ["contact", "need", "campaign"]:
        if key in body:
            setattr(lead, key, required(body, key, 6000 if key == "need" else 300))
    changes = extras(body, ["notes", "next_action"])
    changes["timeline"] = [*(lead.data or {}).get("timeline", []), {"at": stamp(), "actor_id": user.id, "status": lead.status, "note": str(body.get("notes") or "更新线索")[:6000]}][-100:]
    update_data(lead, changes)
    return save(db, lead, user, "lead.updated")


@router.get("/admin/services")
def admin_services(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing(sorted(rows(db, ServicePlan, user), key=lambda item: (item.price, item.name, item.id)))


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
    return listing([quote for quote in rows(db, Quote, user) if not is_demo_record(quote)])


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
    return listing([order_view(db, order) for order in customer_records(db, Order, user)])


@router.post("/admin/orders")
def create_order(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    quote = owned(db, Quote, required(body, "quote_id", 36), user)
    existing = db.scalar(select(Order).where(Order.organization_id == user.organization_id, Order.quote_id == quote.id))
    if existing:
        return order_view(db, existing)
    if quote.status != "APPROVED":
        fail("报价必须经人工批准后才能生成订单", 409)
    if not customer_for(db, quote) or is_demo_record(quote):
        fail('报价必须关联已注册的客户', 409)
    order = Order(organization_id=user.organization_id, quote_id=quote.id, amount=quote.amount, status="AWAITING_CUSTOMER", is_demo=False, data={**customer_fields(quote), 'origin': 'customer_quote', "quote_snapshot": serialize(quote)})
    db.add(order); db.flush()
    audit(db, user, "order.created", order.id)
    db.commit()
    return order_view(db, order)


@router.post("/admin/orders/{order_id}/simulate-payment")
def simulate_payment(order_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    fail('模拟支付入口已停用，请在客户确认下单后接单。', 410)


def order_message(db, order, user, note):
    ticket = db.scalar(select(Ticket).where(Ticket.organization_id == order.organization_id, Ticket.order_id == order.id))
    if not ticket:
        ticket = Ticket(organization_id=order.organization_id, order_id=order.id, subject=f'服务沟通·{order_view(db, order)["title"]}',
                        status='OPEN', data={**customer_fields(order), 'kind': 'QUESTION', 'description': (order.data or {}).get('need', ''), 'timeline': []})
        db.add(ticket); db.flush()
    ticket.status = 'RESOLVED' if order.status in {'DELIVERED', 'COMPLETED'} else 'IN_PROGRESS'
    update_data(ticket, {'reply': note, 'timeline': [*ticket.data.get('timeline', []), {'at': stamp(), 'actor_id': user.id, 'role': user.role, 'note': note, 'status': ticket.status}]})


@router.post('/admin/orders/{order_id}/accept')
def accept_customer_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    order = accessible_order(db, order_id, user)
    if order.organization_id != user.organization_id or not customer_for(db, order):
        fail('订单未关联有效客户', 404)
    if order.status in {'IN_PROGRESS', 'DELIVERED', 'COMPLETED'} and (order.data or {}).get('accepted_at'):
        return order_view(db, order)
    if order.status != 'REQUESTED' or not (order.data or {}).get('customer_confirmed_at'):
        fail('需客户确认下单后才能接单', 409)
    order.status = 'IN_PROGRESS'
    update_data(order, {'accepted_at': stamp(), 'accepted_by': user.id})
    quote = owned(db, Quote, order.quote_id, user)
    if quote.lead_id:
        lead = owned(db, Lead, quote.lead_id, user)
        lead.status = 'WON'
        ticket = ensure_lead_ticket(db, lead)
        if ticket:
            update_data(ticket, {'lead_status': lead.status})
    order_message(db, order, user, '已接单，服务开始处理。')
    audit(db, user, 'order.owner_accepted', order.id)
    db.commit()
    return order_view(db, order)


@router.post('/admin/orders/{order_id}/complete')
def complete_service(order_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    order = accessible_order(db, order_id, user)
    if order.organization_id != user.organization_id:
        fail('订单不存在', 404)
    if order.status in {'DELIVERED', 'COMPLETED'}:
        return order_view(db, order)
    if order.status != 'IN_PROGRESS':
        fail('仅已接单的服务可以交付', 409)
    note = required(body, 'note', 6000)
    order.status = 'DELIVERED'
    update_data(order, {'delivery_note': note, 'delivered_at': stamp()})
    order_message(db, order, user, note)
    audit(db, user, 'order.service_completed', order.id)
    db.commit()
    return order_view(db, order)


@router.post("/admin/orders/{order_id}/deliver")
def deliver_order(order_id: str, body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(require_admin)):
    order = accessible_order(db, order_id, user)
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
    if order.status not in {"IN_PROGRESS", "DELIVERED"}:
        fail("订单须先接单，才能交付报告", 409)
    delivery = Delivery(organization_id=user.organization_id, order_id=order.id, analysis_id=analysis.id, status="DELIVERED", data={"report_summary": analysis.report.get("summary", ""), "report_mode": analysis.mode, "report_owner_organization_id": analysis.organization_id, "delivered_by": user.id})
    db.add(delivery)
    order.status = "DELIVERED"
    update_data(order, {"delivered_at": stamp()})
    order_message(db, order, user, '分析报告已交付，请前往“我的订单”查看并验收。')
    audit(db, user, "order.delivered", order.id, {"analysis_id": analysis.id})
    db.commit()
    return order_view(db, order)


def accessible_ticket(db, ticket_id, user):
    ticket = db.get(Ticket, ticket_id)
    if not ticket or is_demo_record(ticket):
        fail('记录不存在或无权访问', 404)
    if ticket and ticket.order_id:
        order = db.get(Order, ticket.order_id)
        if order and is_demo_record(order):
            fail('记录不存在或无权访问', 404)
        if order and ticket.organization_id == order.organization_id and customer_for(db, order) and customer_for(db, order).id == user.id:
            return ticket
    if not (user.role == 'OWNER_ADMIN' and ticket.organization_id == user.organization_id or customer_for(db, ticket) and customer_for(db, ticket).id == user.id):
        fail("记录不存在或无权访问", 404)
    return ticket


@router.get("/tickets")
def tickets(db: Session = Depends(get_db), user: User = Depends(current_user)):
    items = list(db.scalars(select(Ticket).outerjoin(Order, and_(Ticket.order_id == Order.id, Ticket.organization_id == Order.organization_id))
                           .where(or_(Ticket.organization_id == user.organization_id, Ticket.data['customer_organization_id'].as_string() == user.organization_id,
                                      Order.data['customer_organization_id'].as_string() == user.organization_id)).order_by(Ticket.created_at.desc())))
    return listing([item for item in items if not is_demo_record(item) and (not item.order_id or not is_demo_record(db.get(Order, item.order_id))) and
                    (user.role == 'OWNER_ADMIN' and item.organization_id == user.organization_id or
                     customer_for(db, item) and customer_for(db, item).id == user.id or
                     item.order_id and customer_for(db, db.get(Order, item.order_id)) and customer_for(db, db.get(Order, item.order_id)).id == user.id)])


@router.post("/tickets")
def create_ticket(body: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = accessible_order(db, body["order_id"], user) if body.get("order_id") else None
    kind = str(body.get("kind") or "QUESTION").upper()
    if kind not in {"QUESTION", "REVISION", "COMPLAINT", "REFUND"}:
        fail("工单类型无效")
    owner = company_owner(db) if user.role != "OWNER_ADMIN" and not order else user
    organization_id = order.organization_id if order else owner.organization_id
    if user.role == 'OWNER_ADMIN':
        recipient = customer_fields(order) if order else {}
        if not order and body.get('customer_user_id'):
            candidate = db.get(User, str(body['customer_user_id']))
            known = db.scalar(select(Lead).where(Lead.organization_id == user.organization_id, Lead.data['customer_user_id'].as_string() == str(body['customer_user_id'])))
            if candidate and candidate.role == 'CLIENT_USER' and known:
                recipient = identity_fields(candidate)
        if not recipient:
            fail('请选择对应客户或客户订单，工单才能同步到客户端。')
    else:
        recipient = identity_fields(user)
    data = {"kind": kind, 'origin': 'owner_ticket' if user.role == 'OWNER_ADMIN' else 'customer_submission', "description": str(body.get("description") or "")[:6000], **recipient, "timeline": [{"at": stamp(), "actor_id": user.id, "role": user.role, "event": "创建工单"}]}
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
    return listing(customer_records(db, Ticket, user))


@router.get("/approvals")
def approvals(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return listing([approval_view(db, item) for item in rows(db, Approval, user) if not is_demo_record(item)])


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
    if is_demo_record(approval):
        fail('此记录已归档', 410)
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
            if order and not is_demo_record(order) and customer_for(db, order):
                order.status = "REFUNDED"
                update_data(order, {'refunded_at': stamp()})
                ticket.status = "RESOLVED"
                update_data(ticket, {"resolution": "订单金额已从接单营收中撤销；未操作资金。"})
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
    costs = [item for item in rows(db, CostEvent, user) if not since or item.created_at >= since]
    own_cost_ids = {item.id for item in costs}
    linked_analysis_ids = set()
    for delivery in rows(db, Delivery, user):
        order = db.get(Order, delivery.order_id)
        analysis = db.get(ContentAnalysis, delivery.analysis_id)
        if order and not is_demo_record(order) and customer_for(db, order) and analysis and order.organization_id == user.organization_id and (order.data or {}).get("customer_organization_id") == analysis.organization_id:
            linked_analysis_ids.add(analysis.id)
    linked_costs = []
    if linked_analysis_ids:
        linked_runs = list(db.scalars(select(AgentRun).where(AgentRun.analysis_id.in_(linked_analysis_ids))))
        valid_runs = {run.id: run.organization_id for run in linked_runs if (db.get(ContentAnalysis, run.analysis_id).organization_id == run.organization_id)}
        if valid_runs:
            linked_costs = [item for item in db.scalars(select(CostEvent).where(CostEvent.run_id.in_(valid_runs))) if item.organization_id == valid_runs[item.run_id] and item.id not in own_cost_ids and (not since or item.created_at >= since)]
    costs.extend(linked_costs)
    all_orders = [item for item in customer_records(db, Order, user) if (item.data or {}).get('customer_confirmed_at')]
    orders = [item for item in all_orders if not since or item.created_at >= since]
    leads = [item for item in customer_records(db, Lead, user) if not since or item.created_at >= since]
    booked = [item for item in all_orders if item.status in {'IN_PROGRESS', 'DELIVERED', 'COMPLETED'} and (item.data or {}).get('accepted_at') and (not since or item.data['accepted_at'] >= since)]
    revenue = total_amount(item.amount for item in booked)
    cost = total_amount(item.estimated_cost for item in costs)
    won = sum(item.status == "WON" for item in leads)
    cost_rows = [{"id": item.id, "run_id": item.run_id, "model": item.model, "input_tokens": item.input_tokens, "output_tokens": item.output_tokens, "estimated_cost": item.estimated_cost, "created_at": item.created_at, "source": "本组织" if item.id in own_cost_ids else "明确关联的客户报告交付"} for item in costs]
    return {'currency': 'CNY', 'booked_revenue': revenue, 'order_count': len(orders), 'accepted_order_count': len(booked),
            'completed_order_count': sum(item.status == 'COMPLETED' for item in orders), 'ticket_count': len(customer_records(db, Ticket, user)),
            'model_cost_estimate': cost, 'linked_customer_model_cost_estimate': total_amount(item.estimated_cost for item in linked_costs), 'estimated_margin': round(revenue - cost, 6),
            'funnel': {'leads': len(leads), 'qualified': sum(item.status in {'QUALIFIED', 'PROPOSAL', 'WON'} for item in leads), 'proposals': sum(item.status in {'PROPOSAL', 'WON'} for item in leads), 'won': won, 'conversion_rate': round(won / len(leads), 4) if leads else None},
            'cost_events': cost_rows, 'bookings': [{'id': item.id, 'title': order_view(db, item)['title'], 'amount': item.amount, 'accepted_at': item.data['accepted_at'], 'status': item.status} for item in booked],
            'limitations': ['订单营收按已注册客户确认下单、老板接单后的金额统计；尚未接入资金支付。', '已取消的订单不计营收；归档的模拟数据不参与业务统计。', '模型费用按配置单价估算，毛利未扣除人工等其他经营成本。'],
            'source': '注册客户需求、已接单服务订单及实际记录的模型用量'}


@router.get("/admin/finance")
def finance(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return finance_summary(db, user)


@router.get("/admin/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    financial = finance_summary(db, user)
    orders = [item for item in customer_records(db, Order, user) if (item.data or {}).get('customer_confirmed_at')]
    leads = customer_records(db, Lead, user)
    pending = [item for item in rows(db, Approval, user) if item.status == 'PENDING' and not is_demo_record(item)]
    return {**financial, 'leads': len(leads), 'orders': len(orders), 'customers': len({item.data['customer_user_id'] for item in leads}),
            'pending_approvals': len(pending), 'pending_deliveries': sum(item.status == 'IN_PROGRESS' for item in orders),
            'details': {'leads': [{'id': item.id, 'name': item.contact, 'description': item.need, 'status': item.status} for item in leads],
                        'orders': [{'id': item.id, 'name': order_view(db, item)['title'], 'description': f'¥{item.amount:.2f} · {item.data.get("need") or item.data.get("quote_snapshot", {}).get("scope", "服务订单")}', 'status': item.status} for item in orders],
                        'approvals': [{'id': item.id, 'name': approval_view(db, item).get('target_name') or item.kind, 'description': item.reason or item.kind, 'status': item.status} for item in pending],
                        'costs': financial['cost_events']}}


@router.get("/admin/weekly-report")
def weekly_report(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    summary = finance_summary(db, user, start.isoformat())
    text = (f"# CreatorOS 经营周报\n\n统计窗口：{start.date()} 至 {end.date()}（UTC，最近 7 天）\n\n"
            f"新增线索：{summary['funnel']['leads']}；新增订单：{summary['order_count']}；完成订单：{summary['completed_order_count']}。\n\n"
            f"订单营收：¥{summary['booked_revenue']:.2f}；模型费用估算：¥{summary['model_cost_estimate']:.6f}。\n\n"
            "## 待办\n\n跟进注册客户需求，核对待接单服务与工单，完成交付并等待客户验收。\n\n"
            "## 统计口径\n\n订单营收按窗口内接单时间统计，尚未接入资金支付。归档模拟数据不参与统计；费用未含人工等其他经营成本。")
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
