"""add rich task descriptions

Revision ID: d8e9f0a1b2c3
Revises: c7f06d2aa21e
Create Date: 2026-06-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7f06d2aa21e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("description_doc", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("tasks", sa.Column("description_customized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recurring_tasks", sa.Column("description_doc", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("recurring_tasks", sa.Column("description_customized_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "task_description_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recurring_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(task_id IS NOT NULL AND recurring_task_id IS NULL) OR (task_id IS NULL AND recurring_task_id IS NOT NULL)",
            name="ck_task_description_attachment_single_owner",
        ),
        sa.ForeignKeyConstraint(["recurring_task_id"], ["recurring_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_description_attachments_task", "task_description_attachments", ["task_id"])
    op.create_index("ix_task_description_attachments_recurring", "task_description_attachments", ["recurring_task_id"])
    op.create_index("ix_task_description_attachments_user", "task_description_attachments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_task_description_attachments_user", table_name="task_description_attachments")
    op.drop_index("ix_task_description_attachments_recurring", table_name="task_description_attachments")
    op.drop_index("ix_task_description_attachments_task", table_name="task_description_attachments")
    op.drop_table("task_description_attachments")
    op.drop_column("recurring_tasks", "description_customized_at")
    op.drop_column("recurring_tasks", "description_doc")
    op.drop_column("tasks", "description_customized_at")
    op.drop_column("tasks", "description_doc")
