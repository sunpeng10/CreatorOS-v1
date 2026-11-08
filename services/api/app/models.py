from datetime import datetime, timezone
from pathlib import PurePath
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, DDL, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, event, inspect
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, object_session

from .db import Base
from .media_types import asset_mime


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[str] = mapped_column(String(40), default=stamp)
    updated_at: Mapped[str] = mapped_column(String(40), default=stamp, onupdate=stamp)
    data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)


class Scoped(Record):
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)


class Organization(Record, Base):
    __tablename__ = 'organizations'
    name: Mapped[str] = mapped_column(String(200), default='工作区')


class User(Scoped, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default='创作者')
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default='CLIENT_USER')


class Membership(Scoped, Base):
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint('organization_id', 'user_id'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    role: Mapped[str] = mapped_column(String(30), default='CLIENT_USER')


class Session(Scoped, Base):
    __tablename__ = 'sessions'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CreatorAccount(Scoped, Base):
    __tablename__ = 'creator_accounts'
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(80), default='其他')


class ContentItem(Scoped, Base):
    __tablename__ = 'content_items'
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30), default='text')
    account_id: Mapped[str | None] = mapped_column(ForeignKey('creator_accounts.id'), nullable=True)
    text: Mapped[str] = mapped_column(Text, default='')


# Reject new conflicts without rewriting or deleting already saved legacy works.
CONTENT_TITLE_GUARDS = {
    'content_title_insert_guard': '''CREATE TRIGGER IF NOT EXISTS content_title_insert_guard
        BEFORE INSERT ON content_items
        WHEN EXISTS (SELECT 1 FROM content_items WHERE organization_id = NEW.organization_id AND trim(title) = trim(NEW.title))
        BEGIN SELECT RAISE(ABORT, 'CONTENT_TITLE_EXISTS'); END''',
    'content_title_update_guard': '''CREATE TRIGGER IF NOT EXISTS content_title_update_guard
        BEFORE UPDATE OF title, organization_id ON content_items
        WHEN EXISTS (SELECT 1 FROM content_items WHERE organization_id = NEW.organization_id AND trim(title) = trim(NEW.title) AND id != NEW.id)
        BEGIN SELECT RAISE(ABORT, 'CONTENT_TITLE_EXISTS'); END''',
}
for statement in CONTENT_TITLE_GUARDS.values():
    event.listen(ContentItem.__table__, 'after_create', DDL(statement).execute_if(dialect='sqlite'))


class ContentAsset(Scoped, Base):
    __tablename__ = 'content_assets'
    content_id: Mapped[str] = mapped_column(ForeignKey('content_items.id'), index=True)
    path: Mapped[str] = mapped_column(Text)
    original_name: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer, default=0)


class ContentAnalysis(Scoped, Base):
    __tablename__ = 'content_analyses'
    content_id: Mapped[str] = mapped_column(ForeignKey('content_items.id'), index=True)
    status: Mapped[str] = mapped_column(String(30), default='QUEUED')
    mode: Mapped[str] = mapped_column(String(20), default='local')
    report: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cache_key: Mapped[str] = mapped_column(String(64), default='', index=True)


class AnalysisEvidence(Scoped, Base):
    __tablename__ = 'analysis_evidence'
    analysis_id: Mapped[str] = mapped_column(ForeignKey('content_analyses.id'), index=True)


class ContentVersion(Scoped, Base):
    __tablename__ = 'content_versions'
    content_id: Mapped[str] = mapped_column(ForeignKey('content_items.id'), index=True)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey('content_analyses.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class MetricSnapshot(Scoped, Base):
    __tablename__ = 'metric_snapshots'
    __table_args__ = (UniqueConstraint('organization_id', 'import_hash'),)
    content_id: Mapped[str] = mapped_column(ForeignKey('content_items.id'), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey('creator_accounts.id'), nullable=True)
    observed_at: Mapped[str] = mapped_column(String(40), default=stamp)
    source: Mapped[str] = mapped_column(Text, default='手动导入')
    import_hash: Mapped[str] = mapped_column(String(64))


class BenchmarkItem(Scoped, Base):
    __tablename__ = 'benchmark_items'
    title: Mapped[str] = mapped_column(String(300))
    platform: Mapped[str] = mapped_column(String(80), default='手工资料')
    url: Mapped[str] = mapped_column(Text, default='')
    author: Mapped[str] = mapped_column(String(200), default='')
    category: Mapped[str] = mapped_column(String(100), default='')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Recommendation(Scoped, Base):
    __tablename__ = 'recommendations'
    content_id: Mapped[str | None] = mapped_column(ForeignKey('content_items.id'), nullable=True)
    benchmark_id: Mapped[str] = mapped_column(ForeignKey('benchmark_items.id', ondelete='CASCADE'))
    score: Mapped[float] = mapped_column(Float, default=0)


class Experiment(Scoped, Base):
    __tablename__ = 'experiments'
    content_id: Mapped[str | None] = mapped_column(ForeignKey('content_items.id'), nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey('content_analyses.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default='PLANNED')


class Lead(Scoped, Base):
    __tablename__ = 'leads'
    contact: Mapped[str] = mapped_column(String(300))
    need: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(30), default='NEW')
    campaign: Mapped[str] = mapped_column(String(100), default='官网')


class ServicePlan(Scoped, Base):
    __tablename__ = 'service_plans'
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[float] = mapped_column(Float, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Quote(Scoped, Base):
    __tablename__ = 'quotes'
    lead_id: Mapped[str | None] = mapped_column(ForeignKey('leads.id'), nullable=True)
    service_id: Mapped[str | None] = mapped_column(ForeignKey('service_plans.id'), nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default='PENDING_APPROVAL')


class Order(Scoped, Base):
    __tablename__ = 'orders'
    quote_id: Mapped[str] = mapped_column(ForeignKey('quotes.id'), unique=True)
    status: Mapped[str] = mapped_column(String(30), default='PENDING_PAYMENT')
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    amount: Mapped[float] = mapped_column(Float, default=0)


class PaymentRecord(Scoped, Base):
    __tablename__ = 'payment_records'
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), unique=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default='DEMO_PAID')


class Delivery(Scoped, Base):
    __tablename__ = 'deliveries'
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey('content_analyses.id'))
    status: Mapped[str] = mapped_column(String(30), default='DELIVERED')


class Ticket(Scoped, Base):
    __tablename__ = 'tickets'
    order_id: Mapped[str | None] = mapped_column(ForeignKey('orders.id'), nullable=True)
    subject: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default='OPEN')


class AgentRun(Scoped, Base):
    __tablename__ = 'agent_runs'
    analysis_id: Mapped[str] = mapped_column(ForeignKey('content_analyses.id'), index=True)
    status: Mapped[str] = mapped_column(String(30), default='QUEUED')
    budget: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[str] = mapped_column(Text, default='')


class AgentStep(Scoped, Base):
    __tablename__ = 'agent_steps'
    run_id: Mapped[str] = mapped_column(ForeignKey('agent_runs.id'), index=True)
    name: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default='QUEUED')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    output: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    error: Mapped[str] = mapped_column(Text, default='')
    model: Mapped[str] = mapped_column(String(100), default='local')
    tokens: Mapped[int] = mapped_column(Integer, default=0)


class Approval(Scoped, Base):
    __tablename__ = 'approvals'
    kind: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(30), default='PENDING')
    reason: Mapped[str] = mapped_column(Text, default='')


class CostEvent(Scoped, Base):
    __tablename__ = 'cost_events'
    run_id: Mapped[str | None] = mapped_column(ForeignKey('agent_runs.id'), nullable=True)
    model: Mapped[str] = mapped_column(String(100), default='')
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)


class AuditLog(Scoped, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(36), default='')


def serialize(obj):
    result = dict(obj.data or {})
    for column in inspect(obj).mapper.columns:
        if column.key in {'password_hash', 'token_hash', 'path', 'data'}:
            continue
        value = getattr(obj, column.key)
        result[column.key] = value.isoformat() if isinstance(value, datetime) else value
    result['data'] = dict(obj.data or {})
    if isinstance(obj, ContentAsset):
        result['mime'] = asset_mime(obj.original_name, obj.mime)
        db = object_session(obj)
        content = db.get(ContentItem, obj.content_id) if db else None
        title = content.title if content and content.organization_id == obj.organization_id else '作品'
        suffix = PurePath(obj.original_name).suffix.lower()
        detail = f'关键帧 {result.get("timecode", 0)}s' if result.get('role') == 'keyframe' else f'素材 {result.get("position", 0) + 1}'
        result['original_name'] = f'{title} · {detail}{suffix}'
    return result
