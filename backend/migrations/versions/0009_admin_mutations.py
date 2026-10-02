"""Audited Admin mutations and durable Agent command requests.

Revision ID: 0009_admin_mutations
Revises: 0008_admin_auth
Create Date: 2026-10-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_admin_mutations"
down_revision: str | None = "0008_admin_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("admin_user_id", sa.Uuid(), nullable=True))
    op.add_column("audit_log", sa.Column("business_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_audit_log_admin_user_id_admin_users",
        "audit_log",
        "admin_users",
        ["admin_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_audit_log_business_id_businesses",
        "audit_log",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_audit_log_admin_user_id", "audit_log", ["admin_user_id"])
    op.create_index("ix_audit_log_business_created_at_id", "audit_log", ["business_id", "created_at", "id"])

    op.create_table(
        "agent_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_admin_id", sa.Uuid(), nullable=False),
        sa.Column("command_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.CheckConstraint(
            "command_type IN ('full_resync')", name="ck_agent_commands_command_type"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_agent_commands_status",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], name="fk_agent_commands_agent_id_agents", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], name="fk_agent_commands_business_id_businesses", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"], ["admin_users.id"],
            name="fk_agent_commands_admin_id_admin_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_agent_commands_active_full_resync_per_agent",
        "agent_commands",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text(
            "command_type = 'full_resync' AND status IN ('pending', 'running')"
        ),
    )
    op.create_index(
        "ix_agent_commands_agent_created_at", "agent_commands", ["agent_id", "created_at"]
    )
    op.create_index(
        "ix_agent_commands_business_created_at", "agent_commands", ["business_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_commands_business_created_at", table_name="agent_commands")
    op.drop_index("ix_agent_commands_agent_created_at", table_name="agent_commands")
    op.drop_index(
        "uq_agent_commands_active_full_resync_per_agent", table_name="agent_commands"
    )
    op.drop_table("agent_commands")
    op.drop_index("ix_audit_log_business_created_at_id", table_name="audit_log")
    op.drop_index("ix_audit_log_admin_user_id", table_name="audit_log")
    op.drop_constraint(
        "fk_audit_log_business_id_businesses", "audit_log", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_audit_log_admin_user_id_admin_users", "audit_log", type_="foreignkey"
    )
    op.drop_column("audit_log", "business_id")
    op.drop_column("audit_log", "admin_user_id")
