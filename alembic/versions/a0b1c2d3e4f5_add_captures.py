"""add captures

Revision ID: a0b1c2d3e4f5
Revises: f2a3b4c5d6e7
Create Date: 2026-06-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "captures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("capture_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="inbox"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("converted_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_captures_user_status", "captures", ["user_id", "status"])
    op.create_index("ix_captures_user_type", "captures", ["user_id", "capture_type"])
    op.create_index("ix_captures_user_date", "captures", ["user_id", "note_date"])

    op.create_table(
        "capture_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("captures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_capture_attachments_capture", "capture_attachments", ["capture_id"])


def downgrade() -> None:
    op.drop_index("ix_capture_attachments_capture", table_name="capture_attachments")
    op.drop_table("capture_attachments")
    op.drop_index("ix_captures_user_date", table_name="captures")
    op.drop_index("ix_captures_user_type", table_name="captures")
    op.drop_index("ix_captures_user_status", table_name="captures")
    op.drop_table("captures")
