"""add daily reflections

Revision ID: 4f5a6b7c8d9e
Revises: 3d4e5f6a7b8c, a7b8c9d0e1f2
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "4f5a6b7c8d9e"
down_revision: Union[str, tuple[str, str], None] = ("3d4e5f6a7b8c", "a7b8c9d0e1f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_reflections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("went_well", sa.Text(), nullable=True),
        sa.Column("drained_me", sa.Text(), nullable=True),
        sa.Column("learned", sa.Text(), nullable=True),
        sa.Column("grateful_for", sa.Text(), nullable=True),
        sa.Column("improve_tomorrow", sa.Text(), nullable=True),
        sa.Column("mood_rating", sa.Integer(), nullable=True),
        sa.Column("energy_rating", sa.Integer(), nullable=True),
        sa.Column("productivity_rating", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("mood_rating IS NULL OR (mood_rating >= 1 AND mood_rating <= 10)", name="ck_daily_reflections_mood_rating"),
        sa.CheckConstraint("energy_rating IS NULL OR (energy_rating >= 1 AND energy_rating <= 10)", name="ck_daily_reflections_energy_rating"),
        sa.CheckConstraint(
            "productivity_rating IS NULL OR (productivity_rating >= 1 AND productivity_rating <= 10)",
            name="ck_daily_reflections_productivity_rating",
        ),
        sa.UniqueConstraint("daily_plan_id", name="uq_daily_reflections_daily_plan_id"),
    )
    op.create_index("ix_daily_reflections_user_created_at", "daily_reflections", ["user_id", "created_at"])
    op.create_index("ix_daily_reflections_user_daily_plan", "daily_reflections", ["user_id", "daily_plan_id"])


def downgrade() -> None:
    op.drop_table("daily_reflections")
