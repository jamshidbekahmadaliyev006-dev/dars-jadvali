"""add user language chosen

Revision ID: d81f2b6c9a34
Revises: c3a91e7d4f20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd81f2b6c9a34'
down_revision: Union[str, None] = 'c3a91e7d4f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('language_chosen', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'language_chosen')
