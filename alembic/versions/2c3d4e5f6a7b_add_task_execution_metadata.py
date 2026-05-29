"""add task execution metadata

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-05-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2c3d4e5f6a7b'
down_revision: Union[str, None] = '1b2c3d4e5f6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    task_emotion_phase = sa.Enum('before', 'after', name='taskemotionphase')
    task_emotion_phase.create(op.get_bind(), checkfirst=True)

    op.add_column('tasks', sa.Column('estimated_seconds', sa.Integer(), nullable=True))
    op.add_column('recurring_tasks', sa.Column('estimated_seconds', sa.Integer(), nullable=True))
    op.add_column('daily_tasks', sa.Column('estimated_seconds', sa.Integer(), nullable=True))
    op.add_column('emotion_entries', sa.Column('task_phase', task_emotion_phase, nullable=True))
    op.create_index('ix_emotion_entries_daily_task_phase', 'emotion_entries', ['daily_task_id', 'task_phase'])


def downgrade() -> None:
    op.drop_index('ix_emotion_entries_daily_task_phase', table_name='emotion_entries')
    op.drop_column('emotion_entries', 'task_phase')
    op.drop_column('daily_tasks', 'estimated_seconds')
    op.drop_column('recurring_tasks', 'estimated_seconds')
    op.drop_column('tasks', 'estimated_seconds')
    op.execute('DROP TYPE IF EXISTS taskemotionphase')
