"""add recurring task metadata

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-05-28 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1b2c3d4e5f6a'
down_revision: Union[str, None] = '0a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recurring_tasks', sa.Column('meeting_time', sa.Time(), nullable=True))
    op.add_column('recurring_tasks', sa.Column('external_url', sa.String(length=1000), nullable=True))
    op.add_column('recurring_tasks', sa.Column('tag', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('recurring_tasks', 'tag')
    op.drop_column('recurring_tasks', 'external_url')
    op.drop_column('recurring_tasks', 'meeting_time')
