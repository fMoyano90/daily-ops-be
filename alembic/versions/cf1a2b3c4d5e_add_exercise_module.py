"""add exercise module

Revision ID: cf1a2b3c4d5e
Revises: be2c3d4e5f6a
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "cf1a2b3c4d5e"
down_revision: Union[str, None] = "be2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exercise_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("available_days", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("location", sa.String(80), nullable=True),
        sa.Column("equipment", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("session_duration_min", sa.Integer, nullable=True),
        sa.Column("fitness_level", sa.String(40), nullable=True),
        sa.Column("physical_restrictions", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_exercise_profiles_user_id"),
    )

    op.create_table(
        "workout_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("status", sa.Enum("draft", "completed", name="exercisedaystatus"), nullable=False, server_default="draft"),
        sa.Column("total_calories_burned", sa.Integer, nullable=True),
        sa.Column("total_duration_min", sa.Integer, nullable=True),
        sa.Column("rpe", sa.Integer, nullable=True),
        sa.Column("post_workout_state", sa.String(80), nullable=True),
        sa.Column("day_note", sa.Text, nullable=True),
        sa.Column("coach_notes", sa.Text, nullable=True),
        sa.Column("ai_model", sa.String(120), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date", name="uq_workout_days_user_date"),
    )
    op.create_index("ix_workout_days_user_date", "workout_days", ["user_id", "date"])

    op.create_table(
        "workout_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workout_day_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workout_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("exercise_type", sa.Enum("strength", "cardio", "mobility", "recovery", name="exercisetype"), nullable=False, server_default="cardio"),
        sa.Column("muscle_group", sa.String(80), nullable=True),
        sa.Column("sets", sa.Integer, nullable=True),
        sa.Column("reps", sa.Integer, nullable=True),
        sa.Column("weight_kg", sa.Float, nullable=True),
        sa.Column("duration_min", sa.Integer, nullable=True),
        sa.Column("distance_km", sa.Float, nullable=True),
        sa.Column("calories_burned", sa.Integer, nullable=True),
        sa.Column("intensity", sa.String(40), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("pending", "completed", "partial", "skipped", name="workoutexercisestatus"), nullable=False, server_default="pending"),
        sa.Column("ai_suggested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("ai_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workout_exercises_user_date", "workout_exercises", ["user_id", "date"])
    op.create_index("ix_workout_exercises_workout_day_id", "workout_exercises", ["workout_day_id"])

    # Migrate existing exercise_entries → workout_days + workout_exercises
    op.execute(sa.text("""
        INSERT INTO workout_days (id, user_id, daily_plan_id, date, status, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            user_id,
            daily_plan_id,
            date,
            'draft',
            MIN(created_at),
            MAX(updated_at)
        FROM exercise_entries
        GROUP BY user_id, daily_plan_id, date
        ON CONFLICT (user_id, date) DO NOTHING
    """))

    op.execute(sa.text("""
        INSERT INTO workout_exercises (
            id, user_id, workout_day_id, date, name, exercise_type,
            calories_burned, duration_min, intensity, sort_order,
            status, ai_notes, created_at, updated_at
        )
        SELECT
            ee.id,
            ee.user_id,
            wd.id,
            ee.date,
            ee.label,
            'cardio',
            ee.calories_burned,
            ee.duration_min,
            ee.intensity,
            ee.sort_order,
            'completed',
            ee.ai_notes,
            ee.created_at,
            ee.updated_at
        FROM exercise_entries ee
        JOIN workout_days wd ON wd.user_id = ee.user_id AND wd.date = ee.date
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    op.drop_index("ix_workout_exercises_workout_day_id", "workout_exercises")
    op.drop_index("ix_workout_exercises_user_date", "workout_exercises")
    op.drop_table("workout_exercises")
    op.drop_index("ix_workout_days_user_date", "workout_days")
    op.drop_table("workout_days")
    op.drop_table("exercise_profiles")
    op.execute("DROP TYPE IF EXISTS workoutexercisestatus")
    op.execute("DROP TYPE IF EXISTS exercisetype")
    op.execute("DROP TYPE IF EXISTS exercisedaystatus")
