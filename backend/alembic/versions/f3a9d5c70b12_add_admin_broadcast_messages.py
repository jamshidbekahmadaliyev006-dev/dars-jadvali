"""add admin broadcast messages (message ids, so a deleted broadcast disappears from users' chats too)

Revision ID: f3a9d5c70b12
Revises: e7b2c4d19a58
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f3a9d5c70b12'
down_revision: Union[str, None] = 'e7b2c4d19a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('admin_broadcast_messages'):
        return
    op.create_table(
        'admin_broadcast_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('broadcast_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
    )
    op.create_index('ix_admin_broadcast_messages_broadcast_id', 'admin_broadcast_messages', ['broadcast_id'])


def downgrade() -> None:
    op.drop_table('admin_broadcast_messages')
