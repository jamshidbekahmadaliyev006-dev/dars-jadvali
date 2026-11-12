"""add kind to admin broadcasts (msg = message, ad = advertisement)

Revision ID: a5c8e2f91d34
Revises: f3a9d5c70b12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a5c8e2f91d34'
down_revision: Union[str, None] = 'f3a9d5c70b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('admin_broadcasts')}
    if 'kind' not in cols:
        op.add_column('admin_broadcasts', sa.Column('kind', sa.String(length=10), nullable=False, server_default='msg'))


def downgrade() -> None:
    op.drop_column('admin_broadcasts', 'kind')
