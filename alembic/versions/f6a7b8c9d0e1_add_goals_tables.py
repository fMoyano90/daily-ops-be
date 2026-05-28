"""add goals tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'goals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('horizon', sa.Enum('short', 'medium', 'long', name='goalhorizon'), nullable=False, server_default='medium'),
        sa.Column('status', sa.Enum('active', 'achieved', 'paused', 'abandoned', name='goalstatus'), nullable=False, server_default='active'),
        sa.Column('progress', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('target_date', sa.Date, nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('anti_goals', sa.Text, nullable=True),
        sa.Column('key_results', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_goals_user_id', 'goals', ['user_id'])
    op.create_index('ix_goals_project_id', 'goals', ['project_id'])

    op.create_table(
        'goal_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'blocked', name='goalstepstatus'), nullable=False, server_default='pending'),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('linked_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_goal_steps_goal_id', 'goal_steps', ['goal_id'])
    op.create_index('ix_goal_steps_linked_task_id', 'goal_steps', ['linked_task_id'])

    op.create_table(
        'goal_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_goal_comments_user_id', 'goal_comments', ['user_id'])
    op.create_index('ix_goal_comments_goal_id', 'goal_comments', ['goal_id'])


def downgrade() -> None:
    op.drop_table('goal_comments')
    op.drop_table('goal_steps')
    op.drop_table('goals')
    op.execute("DROP TYPE IF EXISTS goalhorizon")
    op.execute("DROP TYPE IF EXISTS goalstatus")
    op.execute("DROP TYPE IF EXISTS goalstepstatus")
