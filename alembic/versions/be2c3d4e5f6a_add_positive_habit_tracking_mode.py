"""add positive habit tracking mode

Revision ID: be2c3d4e5f6a
Revises: ae1b2c3d4e5f
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "be2c3d4e5f6a"
down_revision: Union[str, None] = "ae1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE habittrackingmode ADD VALUE IF NOT EXISTS 'positive'")
    op.execute("ALTER TABLE habits ALTER COLUMN tracking_mode SET DEFAULT 'positive'")


def downgrade() -> None:
    op.execute("UPDATE habits SET tracking_mode = 'control' WHERE tracking_mode = 'positive'")
    op.execute("ALTER TABLE habits ALTER COLUMN tracking_mode DROP DEFAULT")
    op.execute("ALTER TYPE habittrackingmode RENAME TO habittrackingmode_old")
    op.execute("CREATE TYPE habittrackingmode AS ENUM ('abstinence', 'control')")
    op.execute(
        "ALTER TABLE habits ALTER COLUMN tracking_mode TYPE habittrackingmode "
        "USING tracking_mode::text::habittrackingmode"
    )
    op.execute("ALTER TABLE habits ALTER COLUMN tracking_mode SET DEFAULT 'abstinence'")
    op.execute("DROP TYPE habittrackingmode_old")
