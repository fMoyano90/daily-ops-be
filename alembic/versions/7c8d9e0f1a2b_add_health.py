"""add health

Revision ID: 7c8d9e0f1a2b
Revises: 6b7c8d9e0f1a
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7c8d9e0f1a2b"
down_revision: Union[str, None] = "6b7c8d9e0f1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


condition_category_enum = postgresql.ENUM(
    "cardiovascular", "metabolic", "dental", "mental", "respiratory", "other", name="conditioncategory", create_type=False
)
condition_status_enum = postgresql.ENUM("active", "monitoring", "resolved", name="conditionstatus", create_type=False)
guideline_kind_enum = postgresql.ENUM("avoid", "helps", "action", name="guidelinekind", create_type=False)
episode_type_enum = postgresql.ENUM("cold", "flu", "physical", "mental", "other", name="episodetype", create_type=False)


def upgrade() -> None:
    condition_category_enum.create(op.get_bind(), checkfirst=True)
    condition_status_enum.create(op.get_bind(), checkfirst=True)
    guideline_kind_enum.create(op.get_bind(), checkfirst=True)
    episode_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "health_conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", condition_category_enum, nullable=False),
        sa.Column("status", condition_status_enum, nullable=False, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("diagnosed_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_conditions_user_id", "health_conditions", ["user_id"])

    op.create_table(
        "health_guidelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "condition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("health_conditions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", guideline_kind_enum, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_guidelines_condition_id", "health_guidelines", ["condition_id"])

    op.create_table(
        "health_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "condition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("health_conditions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=True),
        sa.Column("frequency", sa.String(length=80), nullable=False, server_default="daily"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_reminders_condition_id", "health_reminders", ["condition_id"])

    op.create_table(
        "sickness_episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "condition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("health_conditions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("episode_type", episode_type_enum, nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("severity IS NULL OR (severity >= 1 AND severity <= 5)", name="ck_sickness_episodes_severity"),
    )
    op.create_index("ix_sickness_episodes_user_started", "sickness_episodes", ["user_id", "started_on"])
    op.create_index("ix_sickness_episodes_condition_id", "sickness_episodes", ["condition_id"])


def downgrade() -> None:
    op.drop_table("sickness_episodes")
    op.drop_table("health_reminders")
    op.drop_table("health_guidelines")
    op.drop_table("health_conditions")
    episode_type_enum.drop(op.get_bind(), checkfirst=True)
    guideline_kind_enum.drop(op.get_bind(), checkfirst=True)
    condition_status_enum.drop(op.get_bind(), checkfirst=True)
    condition_category_enum.drop(op.get_bind(), checkfirst=True)
