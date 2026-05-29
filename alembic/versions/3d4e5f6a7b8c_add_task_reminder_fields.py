"""add task reminder fields

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-05-28 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '3d4e5f6a7b8c'
down_revision: Union[str, None] = '2c3d4e5f6a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('reminder_minutes_before', sa.Integer(), nullable=True))
    op.add_column('recurring_tasks', sa.Column('reminder_minutes_before', sa.Integer(), nullable=True))

    op.create_table(
        'task_reminder_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('recurring_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recurring_tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('reminder_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('minutes_before', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('task_id', 'reminder_date', 'minutes_before', name='uq_reminder_task_date_min'),
        sa.UniqueConstraint('recurring_task_id', 'reminder_date', 'minutes_before', name='uq_reminder_recurring_date_min'),
    )
    op.create_index('ix_reminder_user', 'task_reminder_deliveries', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_reminder_user', table_name='task_reminder_deliveries')
    op.drop_table('task_reminder_deliveries')
    op.drop_column('recurring_tasks', 'reminder_minutes_before')
    op.drop_column('tasks', 'reminder_minutes_before')
