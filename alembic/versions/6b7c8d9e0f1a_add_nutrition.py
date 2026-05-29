"""add nutrition

Revision ID: 6b7c8d9e0f1a
Revises: 5a6b7c8d9e0f
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "6b7c8d9e0f1a"
down_revision: Union[str, None] = "5a6b7c8d9e0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


sex_enum = postgresql.ENUM("male", "female", name="sex", create_type=False)
activity_level_enum = postgresql.ENUM("sedentary", "light", "moderate", "active", "very_active", name="activitylevel", create_type=False)
nutrition_goal_enum = postgresql.ENUM("lose", "maintain", "gain", name="nutritiongoal", create_type=False)
nutrition_day_status_enum = postgresql.ENUM("draft", "analyzed", name="nutritiondaystatus", create_type=False)


def upgrade() -> None:
    sex_enum.create(op.get_bind(), checkfirst=True)
    activity_level_enum.create(op.get_bind(), checkfirst=True)
    nutrition_goal_enum.create(op.get_bind(), checkfirst=True)
    nutrition_day_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "health_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sex", sex_enum, nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("activity_level", activity_level_enum, nullable=False),
        sa.Column("goal", nutrition_goal_enum, nullable=False),
        sa.Column("target_calories_override", sa.Integer(), nullable=True),
        sa.Column("glass_ml", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_health_profiles_user_id"),
    )
    op.create_index("ix_health_profiles_user_id", "health_profiles", ["user_id"])

    op.create_table(
        "nutrition_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("water_ml", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("day_note", sa.Text(), nullable=True),
        sa.Column("status", nutrition_day_status_enum, nullable=False, server_default="draft"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_model", sa.String(length=120), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("recommended_calories", sa.Integer(), nullable=True),
        sa.Column("consumed_calories", sa.Integer(), nullable=True),
        sa.Column("burned_calories", sa.Integer(), nullable=True),
        sa.Column("balance_calories", sa.Integer(), nullable=True),
        sa.Column("total_protein_g", sa.Float(), nullable=True),
        sa.Column("total_carbs_g", sa.Float(), nullable=True),
        sa.Column("total_sugar_g", sa.Float(), nullable=True),
        sa.Column("total_fat_g", sa.Float(), nullable=True),
        sa.Column("total_fiber_g", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date", name="uq_nutrition_days_user_date"),
    )
    op.create_index("ix_nutrition_days_user_date", "nutrition_days", ["user_id", "date"])
    op.create_index("ix_nutrition_days_daily_plan_id", "nutrition_days", ["daily_plan_id"])

    op.create_table(
        "meal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calories", sa.Integer(), nullable=True),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbs_g", sa.Float(), nullable=True),
        sa.Column("sugar_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("ai_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_meal_entries_user_date", "meal_entries", ["user_id", "date"])
    op.create_index("ix_meal_entries_daily_plan_id", "meal_entries", ["daily_plan_id"])

    op.create_table(
        "exercise_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calories_burned", sa.Integer(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("intensity", sa.String(length=80), nullable=True),
        sa.Column("ai_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exercise_entries_user_date", "exercise_entries", ["user_id", "date"])
    op.create_index("ix_exercise_entries_daily_plan_id", "exercise_entries", ["daily_plan_id"])


def downgrade() -> None:
    op.drop_table("exercise_entries")
    op.drop_table("meal_entries")
    op.drop_table("nutrition_days")
    op.drop_table("health_profiles")
    nutrition_day_status_enum.drop(op.get_bind(), checkfirst=True)
    nutrition_goal_enum.drop(op.get_bind(), checkfirst=True)
    activity_level_enum.drop(op.get_bind(), checkfirst=True)
    sex_enum.drop(op.get_bind(), checkfirst=True)
