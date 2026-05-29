"""add partial unique index for active timer sessions

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_timer_active_unique',
        'timer_sessions',
        ['daily_task_id'],
        unique=True,
        postgresql_where=text('stopped_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_timer_active_unique', table_name='timer_sessions')
