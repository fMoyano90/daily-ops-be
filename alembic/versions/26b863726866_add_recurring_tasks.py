"""add_recurring_tasks

Revision ID: 26b863726866
Revises: 0e92674cfbc6
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '26b863726866'
down_revision: Union[str, None] = '0e92674cfbc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE recurringtasktype AS ENUM ('daily', 'weekly', 'monthly')")
    op.execute("CREATE TYPE recurringinstancestatus AS ENUM ('pending', 'completed', 'skipped')")

    op.create_table(
        'recurring_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('priority', postgresql.ENUM(name='priority', create_type=False), nullable=False, server_default=sa.text("'medium'")),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('recurrence_type', postgresql.ENUM(name='recurringtasktype', create_type=False), nullable=False),
        sa.Column('recurrence_days', postgresql.JSON, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_recurring_tasks_project_id', 'recurring_tasks', ['project_id'])

    op.create_table(
        'recurring_task_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('recurring_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recurring_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('daily_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daily_tasks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', postgresql.ENUM(name='recurringinstancestatus', create_type=False), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_recurring_task_instances_recurring_task_id', 'recurring_task_instances', ['recurring_task_id'])
    op.create_index('ix_recurring_task_instances_daily_task_id', 'recurring_task_instances', ['daily_task_id'])
    op.create_index('ix_recurring_task_instances_date', 'recurring_task_instances', ['date'])
    op.create_unique_constraint('uq_recurring_task_instance_date', 'recurring_task_instances', ['recurring_task_id', 'date'])

    op.add_column('daily_tasks', sa.Column('recurring_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recurring_tasks.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_daily_tasks_recurring_task_id', 'daily_tasks', ['recurring_task_id'])


def downgrade() -> None:
    op.drop_index('ix_daily_tasks_recurring_task_id', table_name='daily_tasks')
    op.drop_column('daily_tasks', 'recurring_task_id')

    op.drop_index('ix_recurring_task_instances_date', table_name='recurring_task_instances')
    op.drop_index('ix_recurring_task_instances_daily_task_id', table_name='recurring_task_instances')
    op.drop_index('ix_recurring_task_instances_recurring_task_id', table_name='recurring_task_instances')
    op.drop_constraint('uq_recurring_task_instance_date', 'recurring_task_instances', type_='unique')
    op.drop_table('recurring_task_instances')

    op.drop_index('ix_recurring_tasks_project_id', table_name='recurring_tasks')
    op.drop_table('recurring_tasks')

    op.execute("DROP TYPE recurringinstancestatus")
    op.execute("DROP TYPE recurringtasktype")
