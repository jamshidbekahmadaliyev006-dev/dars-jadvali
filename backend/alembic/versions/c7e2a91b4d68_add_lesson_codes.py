"""full subject code on schedules and teacher lessons (BGH001-3)

Revision ID: c7e2a91b4d68
Revises: b6d1f4a82c55
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c7e2a91b4d68'
down_revision: Union[str, None] = 'b6d1f4a82c55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ('schedules', 'teacher_lessons'):
        if 'code' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column('code', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('teacher_lessons', 'code')
    op.drop_column('schedules', 'code')
