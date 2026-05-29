"""add sleep logs

Revision ID: 5a6b7c8d9e0f
Revises: 4f5a6b7c8d9e
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "5a6b7c8d9e0f"
down_revision: Union[str, None] = "4f5a6b7c8d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sleep_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hours_slept", sa.Float(), nullable=True),
        sa.Column("sleep_quality", sa.Integer(), nullable=True),
        sa.Column("bedtime", sa.Time(), nullable=True),
        sa.Column("wake_time", sa.Time(), nullable=True),
        sa.Column("wakeups", sa.Integer(), nullable=True),
        sa.Column("tiredness_on_wake", sa.Integer(), nullable=True),
        sa.Column("tiredness_during_day", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("hours_slept IS NULL OR (hours_slept >= 0 AND hours_slept <= 24)", name="ck_sleep_logs_hours_slept"),
        sa.CheckConstraint("sleep_quality IS NULL OR (sleep_quality >= 1 AND sleep_quality <= 10)", name="ck_sleep_logs_sleep_quality"),
        sa.CheckConstraint("wakeups IS NULL OR (wakeups >= 0 AND wakeups <= 50)", name="ck_sleep_logs_wakeups"),
        sa.CheckConstraint(
            "tiredness_on_wake IS NULL OR (tiredness_on_wake >= 1 AND tiredness_on_wake <= 10)",
            name="ck_sleep_logs_tiredness_on_wake",
        ),
        sa.CheckConstraint(
            "tiredness_during_day IS NULL OR (tiredness_during_day >= 1 AND tiredness_during_day <= 10)",
            name="ck_sleep_logs_tiredness_during_day",
        ),
        sa.UniqueConstraint("user_id", "date", name="uq_sleep_logs_user_date"),
    )
    op.create_index("ix_sleep_logs_user_date", "sleep_logs", ["user_id", "date"])
    op.create_index("ix_sleep_logs_daily_plan_id", "sleep_logs", ["daily_plan_id"])


def downgrade() -> None:
    op.drop_table("sleep_logs")
