"""add capture enum types

Revision ID: c7f06d2aa21e
Revises: a0b1c2d3e4f5
Create Date: 2026-06-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7f06d2aa21e"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE capturetype AS ENUM ('text', 'url', 'image', 'voice', 'mixed')")
    op.execute("CREATE TYPE capturestatus AS ENUM ('inbox', 'reviewed', 'converted', 'archived')")
    op.execute("ALTER TABLE captures ALTER COLUMN capture_type DROP DEFAULT")
    op.execute("ALTER TABLE captures ALTER COLUMN capture_type TYPE capturetype USING capture_type::text::capturetype")
    op.execute("ALTER TABLE captures ALTER COLUMN capture_type SET DEFAULT 'text'")
    op.execute("ALTER TABLE captures ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE captures ALTER COLUMN status TYPE capturestatus USING status::text::capturestatus")
    op.execute("ALTER TABLE captures ALTER COLUMN status SET DEFAULT 'inbox'")


def downgrade() -> None:
    op.execute("ALTER TABLE captures ALTER COLUMN capture_type TYPE VARCHAR(20) USING capture_type::text")
    op.execute("ALTER TABLE captures ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    op.execute("DROP TYPE capturestatus")
    op.execute("DROP TYPE capturetype")
