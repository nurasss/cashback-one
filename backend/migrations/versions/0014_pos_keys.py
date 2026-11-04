"""POS cash register access keys.

Revision ID: 0014_pos_keys
Revises: 0013_business_app_content
Create Date: 2026-11-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_pos_keys"
down_revision: str | None = "0013_business_app_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pos_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_pos_keys_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pos_keys"),
    )
    op.create_index(
        "ix_pos_keys_key_hash",
        "pos_keys",
        ["key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_pos_keys_business_created",
        "pos_keys",
        ["business_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pos_keys_business_created", table_name="pos_keys")
    op.drop_index("ix_pos_keys_key_hash", table_name="pos_keys")
    op.drop_table("pos_keys")
