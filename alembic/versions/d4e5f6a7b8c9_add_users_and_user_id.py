"""add users table and user_id to all tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-25 00:00:00.000000

"""
import os
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

TABLES_WITH_USER = [
    'projects',
    'tasks',
    'daily_plans',
    'daily_tasks',
    'daily_subtasks',
    'timer_sessions',
    'recurring_tasks',
    'recurring_task_instances',
    'jira_connections',
    'task_comments',
]


def upgrade():
    from passlib.context import CryptContext

    conn = op.get_bind()
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.func.utcnow(), nullable=False),
    )

    founder_id = uuid.uuid4()
    founder_email = os.environ['FOUNDER_EMAIL']
    founder_password = os.environ['FOUNDER_PASSWORD']
    founder_display_name = os.environ.get('FOUNDER_DISPLAY_NAME', 'Felipe Moyano')

    conn.execute(
        sa.text("""
            INSERT INTO users (id, email, display_name, hashed_password, is_active, created_at)
            VALUES (:id, :email, :display_name, :hashed_password, true, now())
        """),
        {
            "id": founder_id,
            "email": founder_email,
            "display_name": founder_display_name,
            "hashed_password": pwd_context.hash(founder_password),
        }
    )

    for table in TABLES_WITH_USER:
        op.add_column(table, sa.Column('user_id', UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f'fk_{table}_user_id',
            table, 'users',
            ['user_id'], ['id'],
            ondelete='CASCADE',
        )
        conn.execute(
            sa.text(f"UPDATE {table} SET user_id = :founder_id"),
            {"founder_id": founder_id}
        )
        op.alter_column(table, 'user_id', nullable=False)

    op.drop_constraint('uq_daily_plans_date', 'daily_plans', type_='unique')
    op.create_unique_constraint('uq_daily_plans_user_date', 'daily_plans', ['user_id', 'date'])


def downgrade():
    op.drop_constraint('uq_daily_plans_user_date', 'daily_plans', type_='unique')
    op.create_unique_constraint('uq_daily_plans_date', 'daily_plans', ['date'])

    for table in TABLES_WITH_USER:
        op.drop_constraint(f'fk_{table}_user_id', table, type_='foreignkey')
        op.drop_column(table, 'user_id')

    op.drop_table('users')
