"""add admin broadcasts (messages sent from the admin site)

Revision ID: e7b2c4d19a58
Revises: d81f2b6c9a34
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e7b2c4d19a58'
down_revision: Union[str, None] = 'd81f2b6c9a34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Serverda jadval ilova ishga tushganda (create_all) ham yaratiladi, shuning uchun bor bo'lsa tegmaymiz
    if sa.inspect(op.get_bind()).has_table('admin_broadcasts'):
        return
    op.create_table(
        'admin_broadcasts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('university_id', sa.Integer(), nullable=False),
        sa.Column('audience', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_done', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_admin_broadcasts_university_id', 'admin_broadcasts', ['university_id'])
    op.create_index('ix_admin_broadcasts_audience', 'admin_broadcasts', ['audience'])


def downgrade() -> None:
    op.drop_table('admin_broadcasts')
