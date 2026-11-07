"""Explicit local hard deletion of one owner-identified test order and its dependencies."""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def references(value, identifiers):
    return any(identifier in json.dumps(value, ensure_ascii=False) for identifier in identifiers)


def purge_database(path, order_id, quote_id):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    deleted = {}
    identifiers = {order_id, quote_id}
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA secure_delete=ON')
        db.execute('BEGIN IMMEDIATE')
        quote = db.execute('SELECT * FROM quotes WHERE id=?', (quote_id,)).fetchone()
        lead = db.execute('SELECT * FROM leads WHERE id=?', (quote['lead_id'],)).fetchone() if quote and quote['lead_id'] else None
        other_quotes = db.execute('SELECT count(*) FROM quotes WHERE lead_id=? AND id!=?', (lead['id'], quote_id)).fetchone()[0] if lead else 0
        remove_lead = bool(lead and not other_quotes and json.loads(lead['data']).get('origin') == 'customer_order')
        removals = {'orders': {order_id}, 'quotes': {quote_id}, 'tickets': set(), 'deliveries': set(), 'payment_records': set(), 'approvals': set(), 'audit_logs': set()}
        if remove_lead:
            removals['leads'] = {lead['id']}
            identifiers.add(lead['id'])
        for table in ('tickets', 'deliveries', 'payment_records'):
            for record in db.execute(f'SELECT * FROM {table}').fetchall():
                if record['order_id'] == order_id or table == 'tickets' and remove_lead and json.loads(record['data']).get('lead_id') == lead['id']:
                    removals[table].add(record['id'])
                    identifiers.add(record['id'])
        for table in ('approvals', 'audit_logs'):
            for record in db.execute(f'SELECT * FROM {table}').fetchall():
                if record['target_id'] in identifiers or references(json.loads(record['data']), identifiers):
                    removals[table].add(record['id'])
                    identifiers.add(record['id'])
        if lead and not remove_lead and not other_quotes and lead['status'] == 'WON':
            data = json.loads(lead['data'])
            previous = next((entry['status'] for entry in reversed(data.get('timeline', [])) if entry.get('status') in {'NEW', 'QUALIFIED', 'PROPOSAL', 'LOST'}), 'QUALIFIED')
            db.execute('UPDATE leads SET status=? WHERE id=?', (previous, lead['id']))
            for ticket in db.execute('SELECT id,data FROM tickets WHERE order_id IS NULL').fetchall():
                details = json.loads(ticket['data'])
                if details.get('lead_id') == lead['id']:
                    details['lead_status'] = previous
                    db.execute('UPDATE tickets SET data=? WHERE id=?', (json.dumps(details, ensure_ascii=False), ticket['id']))
        for table in ('audit_logs', 'approvals', 'deliveries', 'payment_records', 'tickets', 'orders', 'quotes', 'leads'):
            count = 0
            for identifier in removals.get(table, set()):
                count += db.execute(f'DELETE FROM {table} WHERE id=?', (identifier,)).rowcount
            if count:
                deleted[table] = count
        for table in [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]:
            if 'data' in [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]:
                if any(references(json.loads(row['data']), identifiers) for row in db.execute(f'SELECT data FROM "{table}"')):
                    raise RuntimeError(f'Unexpected remaining reference in {table}; transaction rolled back')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign key check failed; transaction rolled back')
        db.commit()
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        db.execute('VACUUM')
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        return {'deleted': deleted, 'removed_ids': identifiers}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--order-id', required=True)
    parser.add_argument('--expected-amount', required=True, type=float)
    args = parser.parse_args()
    data_dir = (ROOT / 'data').resolve()
    database = data_dir / 'creatoros.db'
    with sqlite3.connect(database) as db:
        record = db.execute('SELECT quote_id,amount,status FROM orders WHERE id=?', (args.order_id,)).fetchone()
        if not record or record[1] != args.expected_amount or record[2] != 'COMPLETED':
            raise RuntimeError('The exact completed test order does not match; nothing was removed')
        if db.execute("SELECT count(*) FROM agent_runs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]:
            raise RuntimeError('Active analysis tasks exist; nothing was removed')
    paths = [database, *sorted((data_dir / 'backups').glob('*.sqlite'))]
    all_ids = set()
    summary = []
    for path in paths:
        if not path.resolve().is_relative_to(data_dir):
            raise RuntimeError('Database path is outside workspace data')
        result = purge_database(path, args.order_id, record[0])
        all_ids.update(result['removed_ids'])
        summary.append({'database': str(path.relative_to(data_dir)), 'deleted': result['deleted']})
    removed_log_lines = 0
    markers = [identifier.encode('ascii') for identifier in all_ids]
    for path in (data_dir / 'logs').glob('*.log'):
        if not path.resolve().is_relative_to(data_dir):
            raise RuntimeError('Log path is outside workspace data')
        lines = path.read_bytes().splitlines(keepends=True)
        keep = [line for line in lines if not any(marker in line for marker in markers)]
        if len(keep) != len(lines):
            path.write_bytes(b''.join(keep))
            removed_log_lines += len(lines) - len(keep)
    print(json.dumps({'databases': summary, 'removed_log_lines': removed_log_lines}))


if __name__ == '__main__':
    main()
