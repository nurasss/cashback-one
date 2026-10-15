"""Admin identities and independent refresh-token sessions.

Revision ID: 0008_admin_auth
Revises: 0007_sms_auth_core
Create Date: 2026-10-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_admin_auth"
down_revision: str | None = "0007_sms_auth_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("login", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(login) BETWEEN 3 AND 128 AND login = lower(trim(login))",
            name="ck_admin_users_normalized_login",
        ),
        sa.CheckConstraint("role IN ('superadmin', 'business_manager')", name="ck_admin_users_role"),
        sa.CheckConstraint(
            "(role = 'superadmin' AND business_id IS NULL) OR "
            "(role = 'business_manager' AND business_id IS NOT NULL)",
            name="ck_admin_users_role_business",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login", name="uq_admin_users_login"),
    )
    op.create_index("ix_admin_users_business_id", "admin_users", ["business_id"], unique=False)
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_admin_sessions_refresh_token_hash"),
    )
    op.create_index("ix_admin_sessions_admin_user_id", "admin_sessions", ["admin_user_id"], unique=False)
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_admin_user_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index("ix_admin_users_business_id", table_name="admin_users")
    op.drop_table("admin_users")
