"""extend finance entries for credit and loans

Revision ID: ae1b2c3d4e5f
Revises: 9e0f1a2b3c4d
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "ae1b2c3d4e5f"
down_revision: Union[str, None] = "9e0f1a2b3c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("finance_entries", sa.Column("kind", sa.String(20), nullable=False, server_default="cash"))
    op.add_column("finance_entries", sa.Column("affects_balance", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("finance_entries", sa.Column("person", sa.String(120), nullable=True))
    op.add_column("finance_entries", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("finance_entries", sa.Column("status", sa.String(20), nullable=False, server_default="posted"))
    op.add_column("finance_entries", sa.Column("linked_entry_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_finance_entries_linked_entry_id",
        "finance_entries",
        "finance_entries",
        ["linked_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_finance_entries_user_kind_status", "finance_entries", ["user_id", "kind", "status"])


def downgrade() -> None:
    op.drop_index("ix_finance_entries_user_kind_status", table_name="finance_entries")
    op.drop_constraint("fk_finance_entries_linked_entry_id", "finance_entries", type_="foreignkey")
    op.drop_column("finance_entries", "linked_entry_id")
    op.drop_column("finance_entries", "status")
    op.drop_column("finance_entries", "due_date")
    op.drop_column("finance_entries", "person")
    op.drop_column("finance_entries", "affects_balance")
    op.drop_column("finance_entries", "kind")
