"""add schedule week parity

Revision ID: c3a91e7d4f20
Revises: 112f3f2c2588
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3a91e7d4f20'
down_revision: Union[str, None] = '112f3f2c2588'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedules', sa.Column('week_parity', sa.String(length=10), server_default='ALL', nullable=False))


def downgrade() -> None:
    op.drop_column('schedules', 'week_parity')
