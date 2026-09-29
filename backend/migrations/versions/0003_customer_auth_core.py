"""Customer authentication core schema

Revision ID: 0003_customer_auth_core
Revises: 0002_agent_heartbeat_fields
Create Date: 2026-09-29 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_customer_auth_core"
down_revision: str | None = "0002_agent_heartbeat_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add unique phone constraint to users table
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_phone", ["phone"])

    # 2. Add confirmed_at to login_challenges
    with op.batch_alter_table("login_challenges") as batch_op:
        batch_op.add_column(
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True)
        )

    # 3. Create auth_sessions table
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"
        ),
    )
    op.create_index(
        "ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False
    )
    op.create_index(
        "ix_auth_sessions_refresh_token_hash",
        "auth_sessions",
        ["refresh_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_refresh_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    with op.batch_alter_table("login_challenges") as batch_op:
        batch_op.drop_column("confirmed_at")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_phone", type_="unique")
