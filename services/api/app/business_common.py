"""Small shared helpers for organization-scoped business endpoints."""
import math
from fastapi import HTTPException
from sqlalchemy import select

from .models import AuditLog, serialize, stamp


def fail(message, code=422):
    raise HTTPException(code, message)


def rows(db, model, user):
    return list(db.scalars(select(model).where(model.organization_id == user.organization_id).order_by(model.created_at.desc(), model.id)))


def listing(items):
    return {"items": [serialize(x) if not isinstance(x, dict) else x for x in items], "total": len(items)}


def required(body, key, limit=2000):
    value = body.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail(f"{key} 必须为非空文本，且不超过 {limit} 字符")
    return value.strip()


def money(value, label="amount"):
    try:
        number = float(value)
    except (ValueError, TypeError):
        fail(f"{label} 必须为有效金额")
    if isinstance(value, bool) or not math.isfinite(number) or number < 0 or number > 10000000:
        fail(f"{label} 必须在 0 到 10000000 之间")
    return round(number, 2)


def extras(body, allowed):
    return {key: body[key] for key in allowed if key in body}


def audit(db, user, action, target_id, detail=None):
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action=action, target_id=target_id, data=detail or {}))


def save(db, entity, user=None, action=None):
    db.add(entity)
    db.flush()
    if action and user:
        audit(db, user, action, entity.id)
    db.commit()
    db.refresh(entity)
    return serialize(entity)


def update_data(entity, changes):
    entity.data = {**(entity.data or {}), **changes}
    entity.updated_at = stamp()
