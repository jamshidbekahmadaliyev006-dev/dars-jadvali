"""personal plans: event columns and users.plan_only

Revision ID: b6d1f4a82c55
Revises: a5c8e2f91d34
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b6d1f4a82c55'
down_revision: Union[str, None] = 'a5c8e2f91d34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add(table: str, column: sa.Column) -> None:
    if column.name not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    _add('users', sa.Column('plan_only', sa.Boolean(), nullable=False, server_default=sa.false()))
    _add('personal_events', sa.Column('place', sa.String(length=255), nullable=True))
    _add('personal_events', sa.Column('has_time', sa.Boolean(), nullable=False, server_default=sa.true()))
    _add('personal_events', sa.Column('remind1_sent', sa.Boolean(), nullable=False, server_default=sa.false()))
    _add('personal_events', sa.Column('remind2_sent', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for table, col in (('personal_events', 'remind2_sent'), ('personal_events', 'remind1_sent'),
                       ('personal_events', 'has_time'), ('personal_events', 'place'), ('users', 'plan_only')):
        op.drop_column(table, col)
