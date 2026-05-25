"""add_jira_connections

Revision ID: a1b2c3d4e5f6
Revises: 26b863726866
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '26b863726866'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jira_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('api_token_encrypted', sa.LargeBinary, nullable=False),
        sa.Column('jql', sa.String(2000), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(50), nullable=True),
        sa.Column('last_sync_error', sa.String(2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_jira_connections_project_id', 'jira_connections', ['project_id'])
    op.create_index('ix_jira_connections_enabled', 'jira_connections', ['enabled'])

    op.create_index(
        'ix_tasks_jira_lookup',
        'tasks',
        ['project_id', 'source', 'external_key'],
    )


def downgrade() -> None:
    op.drop_index('ix_tasks_jira_lookup', table_name='tasks')
    op.drop_index('ix_jira_connections_enabled', table_name='jira_connections')
    op.drop_index('ix_jira_connections_project_id', table_name='jira_connections')
    op.drop_table('jira_connections')
