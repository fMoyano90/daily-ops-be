"""add weight_entries, country to health_profiles, ai_meal_plan to nutrition_days

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weight_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "recorded_at", name="uq_weight_entries_user_date"),
    )
    op.create_index("ix_weight_entries_user_recorded_at", "weight_entries", ["user_id", "recorded_at"])

    op.add_column("health_profiles", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column("nutrition_days", sa.Column("ai_meal_plan", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("nutrition_days", "ai_meal_plan")
    op.drop_column("health_profiles", "country")
    op.drop_index("ix_weight_entries_user_recorded_at", table_name="weight_entries")
    op.drop_table("weight_entries")
