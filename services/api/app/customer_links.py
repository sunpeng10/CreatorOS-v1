"""Shared customer identity and legacy business-record reconciliation."""
import re

from sqlalchemy import func, select

from .models import Approval, AuditLog, Delivery, Lead, Order, PaymentRecord, Quote, Ticket, User, stamp


def is_demo_record(record):
    if record is None:
        return False
    data = record.data or {}
    if data.get('archived_demo') or data.get('is_demo') or isinstance(record, Order) and record.is_demo:
        return True
    if data.get('origin') in {'customer_submission', 'customer_order', 'customer_quote', 'owner_ticket', 'customer_communication', 'published_service'}:
        return False
    return any(re.match(r'^(?:TEST|DEMO)(?:$|[\s·:_-])', str(getattr(record, key, '')), re.I)
               for key in ('contact', 'need', 'subject'))


def customer_for(db, record):
    if record is None:
        return None
    data = record.data or {}
    customer = db.get(User, data['customer_user_id']) if data.get('customer_user_id') else None
    return customer if customer and customer.role == 'CLIENT_USER' and customer.organization_id == data.get('customer_organization_id') else None


def customer_fields(customer):
    return {'customer_user_id': customer.id, 'customer_organization_id': customer.organization_id}


def ensure_lead_ticket(db, lead):
    customer = customer_for(db, lead)
    if not customer or is_demo_record(lead):
        return None
    ticket = db.scalar(select(Ticket).where(Ticket.organization_id == lead.organization_id, Ticket.data['lead_id'].as_string() == lead.id).order_by(Ticket.created_at))
    if not ticket:
        ticket = Ticket(organization_id=lead.organization_id, subject=f'需求跟进·{lead.need[:80]}', status='OPEN',
                        data={**customer_fields(customer), 'lead_id': lead.id, 'kind': 'QUESTION', 'origin': 'customer_communication', 'description': lead.need, 'timeline': []})
        db.add(ticket); db.flush()
    ticket.data = {**ticket.data, **customer_fields(customer), 'lead_status': lead.status}
    lead.data = {**lead.data, 'customer_ticket_id': ticket.id}
    return ticket


def link_email_leads(db, customer, *, correct_mismatch=False):
    if customer.role != 'CLIENT_USER':
        return 0
    changed = 0
    for lead in db.scalars(select(Lead).where(func.lower(func.trim(Lead.contact)) == customer.email.strip().lower())).all():
        if is_demo_record(lead):
            continue
        previous = (lead.data or {}).get('customer_user_id')
        if previous and previous != customer.id and not correct_mismatch:
            continue
        if previous != customer.id or (lead.data or {}).get('customer_organization_id') != customer.organization_id:
            lead.data = {**lead.data, **customer_fields(customer), 'identity_source': 'contact_email', 'linked_at': stamp()}
            db.add(AuditLog(organization_id=lead.organization_id, actor_id=customer.id, action='lead.customer_link_repaired', target_id=lead.id,
                            data={'previous_customer_user_id': previous, 'customer_user_id': customer.id}))
            changed += 1
        for ticket in db.scalars(select(Ticket).where(Ticket.organization_id == lead.organization_id, Ticket.data['lead_id'].as_string() == lead.id)):
            ticket.data = {**ticket.data, **customer_fields(customer), 'lead_status': lead.status}
        for quote in db.scalars(select(Quote).where(Quote.organization_id == lead.organization_id, Quote.lead_id == lead.id)).all():
            quote.data = {**quote.data, **customer_fields(customer)}
            for order in db.scalars(select(Order).where(Order.organization_id == quote.organization_id, Order.quote_id == quote.id)).all():
                order.data = {**order.data, **customer_fields(customer)}
                for ticket in db.scalars(select(Ticket).where(Ticket.organization_id == order.organization_id, Ticket.order_id == order.id)):
                    ticket.data = {**ticket.data, **customer_fields(customer)}
        ensure_lead_ticket(db, lead)
    return changed


def repair_customer_links(db):
    """Owner-authorized deployment repair; runtime never transfers an existing binding."""
    return sum(link_email_leads(db, customer, correct_mismatch=True)
               for customer in db.scalars(select(User).where(User.role == 'CLIENT_USER')).all())


def archive_demo_business(db):
    archived = set()
    def archive(record):
        if not (record.data or {}).get('archived_demo'):
            record.data = {**(record.data or {}), 'archived_demo': True, 'archived_at': stamp()}
            archived.add(record.id)
    for order in db.scalars(select(Order)).all():
        if is_demo_record(order):
            archive(order)
            quote = db.get(Quote, order.quote_id)
            if quote:
                archive(quote)
            for model in (PaymentRecord, Delivery, Ticket):
                for record in db.scalars(select(model).where(model.order_id == order.id)):
                    archive(record)
    for lead in db.scalars(select(Lead)).all():
        if is_demo_record(lead):
            archive(lead)
            for quote in db.scalars(select(Quote).where(Quote.lead_id == lead.id)):
                archive(quote)
            for ticket in db.scalars(select(Ticket).where(Ticket.data['lead_id'].as_string() == lead.id)):
                archive(ticket)
    for ticket in db.scalars(select(Ticket)).all():
        if is_demo_record(ticket):
            archive(ticket)
    for approval in db.scalars(select(Approval)).all():
        if approval.target_id in archived:
            archive(approval)
    return len(archived)
