"""add emotion entries

Revision ID: 0a1b2c3d4e5f
Revises: f6a7b8c9d0e1
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0a1b2c3d4e5f'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'emotion_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('daily_plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daily_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('daily_task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daily_tasks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('emotion', sa.String(80), nullable=False),
        sa.Column('secondary_emotions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('intensity', sa.Integer, nullable=False),
        sa.Column('valence', sa.Enum('pleasant', 'neutral', 'unpleasant', name='emotionvalence'), nullable=False),
        sa.Column('energy', sa.Enum('low', 'medium', 'high', name='emotionenergy'), nullable=False, server_default='medium'),
        sa.Column('trigger_type', sa.String(80), nullable=True),
        sa.Column('trigger_note', sa.Text, nullable=True),
        sa.Column('body_sensation', sa.Text, nullable=True),
        sa.Column('thought', sa.Text, nullable=True),
        sa.Column('need', sa.Text, nullable=True),
        sa.Column('response', sa.Text, nullable=True),
        sa.Column('regulation_strategy', sa.String(120), nullable=True),
        sa.Column('strategy_helped', sa.String(20), nullable=True),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_emotion_entries_user_occurred_at', 'emotion_entries', ['user_id', 'occurred_at'])
    op.create_index('ix_emotion_entries_user_emotion', 'emotion_entries', ['user_id', 'emotion'])
    op.create_index('ix_emotion_entries_project_id', 'emotion_entries', ['project_id'])
    op.create_index('ix_emotion_entries_daily_plan_id', 'emotion_entries', ['daily_plan_id'])
    op.create_index('ix_emotion_entries_daily_task_id', 'emotion_entries', ['daily_task_id'])


def downgrade() -> None:
    op.drop_table('emotion_entries')
    op.execute("DROP TYPE IF EXISTS emotionvalence")
    op.execute("DROP TYPE IF EXISTS emotionenergy")
