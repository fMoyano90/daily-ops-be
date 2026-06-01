"""extend workout_exercises with sets_data, rest and timer

Revision ID: d0e1f2a3b4c5
Revises: cf1a2b3c4d5e
Create Date: 2026-05-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "cf1a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workout_exercises", sa.Column("rest_seconds_recommended", sa.Integer, nullable=True))
    op.add_column("workout_exercises", sa.Column("sets_data", postgresql.JSONB, nullable=True))
    op.add_column("workout_exercises", sa.Column("timer_seconds", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("workout_exercises", "timer_seconds")
    op.drop_column("workout_exercises", "sets_data")
    op.drop_column("workout_exercises", "rest_seconds_recommended")
