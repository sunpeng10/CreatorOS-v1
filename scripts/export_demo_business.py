"""Export sanitized business records from the local SQLite database.

Reads data/creatoros.db and writes CSV files to fixtures/demo-business/.
Password hashes, session tokens and credential files are never exported.
Email addresses are masked everywhere (including JSON columns) so the
export is safe to publish; known local test domains are kept as-is.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "creatoros.db"
OUT_DIR = ROOT / "fixtures" / "demo-business"

# Business tables worth sharing as demo data; internal tables are omitted.
TABLES = [
    "users",
    "organizations",
    "memberships",
    "creator_accounts",
    "content_items",
    "content_analyses",
    "content_versions",
    "experiments",
    "recommendations",
    "benchmark_items",
    "metric_snapshots",
    "leads",
    "service_plans",
    "quotes",
    "orders",
    "deliveries",
    "payment_records",
    "tickets",
    "approvals",
    "cost_events",
]

# Columns that must never leave the machine.
DROP_COLUMNS = {
    "users": {"password_hash", "data"},
    "organizations": {"data"},
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![0-9A-Fa-f])1[3-9][0-9]{9}(?![0-9A-Fa-f])")
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
KEEP_DOMAINS = ("@example.test", "@creatoros.local")

MASKED_EMAILS: dict[str, str] = {}
MASKED_PHONES: dict[str, str] = {}


def mask_email(match: re.Match[str]) -> str:
    email = match.group(0)
    if email.endswith(KEEP_DOMAINS):
        return email
    if email not in MASKED_EMAILS:
        MASKED_EMAILS[email] = f"user{len(MASKED_EMAILS) + 1:02d}@example.test"
    return MASKED_EMAILS[email]


def mask_phone(match: re.Match[str]) -> str:
    phone = match.group(0)
    if phone not in MASKED_PHONES:
        MASKED_PHONES[phone] = f"1380000{len(MASKED_PHONES) + 1:04d}"
    return MASKED_PHONES[phone]


def mask_value(value: object) -> object:
    if not isinstance(value, str) or ("@" not in value and "1" not in value):
        return value
    # UUIDs can contain digit runs that look like phone numbers; keep them intact.
    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    def restore(match: re.Match[str]) -> str:
        return protected[int(match.group(1))]

    value = UUID_RE.sub(stash, value)
    value = EMAIL_RE.sub(mask_email, value)
    value = PHONE_RE.sub(mask_phone, value)
    return re.sub(r"\x00(\d+)\x00", restore, value)


def export(con: sqlite3.Connection, table: str) -> int:
    cur = con.execute(f'SELECT * FROM "{table}"')
    columns = [d[0] for d in cur.description]
    drop = DROP_COLUMNS.get(table, set())
    kept = [c for c in columns if c not in drop]
    rows = cur.fetchall()
    out_path = OUT_DIR / f"{table}.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(kept)
        for row in rows:
            record = dict(zip(columns, row))
            writer.writerow([mask_value(record.get(c)) for c in kept])
    return len(rows)


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"database not found: {DB_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        summary = {t: export(con, t) for t in TABLES}
    finally:
        con.close()
    total = sum(summary.values())
    print(f"exported {total} rows into {OUT_DIR}")
    print(f"masked emails: {len(MASKED_EMAILS)}, masked phones: {len(MASKED_PHONES)}")
    for table, count in summary.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
