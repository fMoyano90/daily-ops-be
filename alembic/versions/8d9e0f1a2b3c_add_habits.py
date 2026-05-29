"""add habits

Revision ID: 8d9e0f1a2b3c
Revises: 7c8d9e0f1a2b
Create Date: 2026-05-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8d9e0f1a2b3c"
down_revision: Union[str, None] = "7c8d9e0f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

habit_category_enum = postgresql.ENUM("substance", "behavior", "digital", "other", name="habitcategory", create_type=False)
habit_tracking_mode_enum = postgresql.ENUM("abstinence", "control", name="habittrackingmode", create_type=False)
habit_status_enum = postgresql.ENUM("active", "paused", "achieved", "abandoned", name="habitstatus", create_type=False)
habit_event_type_enum = postgresql.ENUM("check_in", "urge", "relapse", name="habiteventtype", create_type=False)


def upgrade() -> None:
    habit_category_enum.create(op.get_bind(), checkfirst=True)
    habit_tracking_mode_enum.create(op.get_bind(), checkfirst=True)
    habit_status_enum.create(op.get_bind(), checkfirst=True)
    habit_event_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", habit_category_enum, nullable=False, server_default="other"),
        sa.Column("tracking_mode", habit_tracking_mode_enum, nullable=False, server_default="abstinence"),
        sa.Column("status", habit_status_enum, nullable=False, server_default="active"),
        sa.Column("motivation", sa.Text, nullable=True),
        sa.Column("triggers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("coping_strategies", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("action_plan", sa.Text, nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_habits_user_status", "habits", ["user_id", "status"])

    op.create_table(
        "habit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("habit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", habit_event_type_enum, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("intensity", sa.Integer, nullable=True),
        sa.Column("emotion", sa.String(80), nullable=True),
        sa.Column("trigger", sa.String(120), nullable=True),
        sa.Column("feeling_note", sa.Text, nullable=True),
        sa.Column("thought", sa.Text, nullable=True),
        sa.Column("action_taken", sa.Text, nullable=True),
        sa.Column("resisted", sa.Boolean, nullable=True),
        sa.Column("breathing_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("emotion_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emotion_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_habit_events_user_occurred_at", "habit_events", ["user_id", "occurred_at"])
    op.create_index("ix_habit_events_habit_id", "habit_events", ["habit_id"])
    op.create_index("ix_habit_events_event_type", "habit_events", ["habit_id", "event_type"])


def downgrade() -> None:
    op.drop_table("habit_events")
    op.drop_table("habits")
    op.execute("DROP TYPE IF EXISTS habiteventtype")
    op.execute("DROP TYPE IF EXISTS habitstatus")
    op.execute("DROP TYPE IF EXISTS habittrackingmode")
    op.execute("DROP TYPE IF EXISTS habitcategory")
