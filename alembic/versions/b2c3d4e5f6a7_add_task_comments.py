"""add_task_comments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'task_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('recurring_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('recurring_tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            '(task_id IS NOT NULL)::int + (recurring_task_id IS NOT NULL)::int = 1',
            name='ck_task_comment_owner_exactly_one',
        ),
    )

    op.create_index('ix_task_comments_task_id', 'task_comments', ['task_id'])
    op.create_index('ix_task_comments_recurring_task_id', 'task_comments', ['recurring_task_id'])


def downgrade() -> None:
    op.drop_index('ix_task_comments_recurring_task_id', table_name='task_comments')
    op.drop_index('ix_task_comments_task_id', table_name='task_comments')
    op.drop_table('task_comments')
