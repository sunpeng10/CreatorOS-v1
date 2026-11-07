"""One-time owner-authorized upgrade: back up, reconcile customers, archive demos."""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services' / 'api'))

from sqlalchemy import func, select
from app.db import SessionLocal, engine
from app.customer_links import archive_demo_business, customer_for, ensure_lead_ticket, is_demo_record, repair_customer_links
from app.models import AgentRun, AuditLog, Lead, User


def main():
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('This local upgrade requires the workspace SQLite database')
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.status.in_(['RUNNING', 'QUEUED']))):
            raise RuntimeError('Active analysis tasks exist; no business data was changed')
    folder = ROOT / 'data' / 'backups'
    folder.mkdir(exist_ok=True)
    backup = folder / ('creatoros-before-customer-business-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.sqlite')
    with sqlite3.connect(str(engine.url.database)) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    with SessionLocal() as db:
        archived = archive_demo_business(db)
        repaired = repair_customer_links(db)
        threads = 0
        for lead in db.scalars(select(Lead)).all():
            if not is_demo_record(lead) and customer_for(db, lead):
                ensure_lead_ticket(db, lead)
                threads += 1
        owner = db.scalar(select(User).where(User.role == 'OWNER_ADMIN').order_by(User.created_at, User.id))
        if owner:
            db.add(AuditLog(organization_id=owner.organization_id, actor_id=owner.id, action='business.customer_upgrade', target_id=owner.organization_id,
                            data={'archived_records': archived, 'repaired_customer_links': repaired, 'customer_threads': threads}))
        db.commit()
    print(json.dumps({'backup': str(backup.relative_to(ROOT)), 'archived_records': archived,
                      'repaired_customer_links': repaired, 'customer_threads': threads}))


if __name__ == '__main__':
    main()
