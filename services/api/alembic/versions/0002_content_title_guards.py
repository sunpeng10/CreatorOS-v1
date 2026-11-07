"""Prevent duplicate work titles on new writes, retaining existing records."""
from alembic import op

from app.models import CONTENT_TITLE_GUARDS

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'sqlite':
        for statement in CONTENT_TITLE_GUARDS.values():
            op.execute(statement)


def downgrade():
    if op.get_bind().dialect.name == 'sqlite':
        for name in CONTENT_TITLE_GUARDS:
            op.execute(f'DROP TRIGGER IF EXISTS {name}')
