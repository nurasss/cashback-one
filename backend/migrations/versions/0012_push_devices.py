"""Push notification devices: app_id, last_seen_at, disabled_at, unique push_token.

Revision ID: 0012_push_devices
Revises: 0011_customer_avatar
Create Date: 2026-11-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_push_devices"
down_revision: str | None = "0011_customer_avatar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Deduplicate pre-existing rows with duplicate push_tokens before creating unique index,
    # deterministically keeping exactly one row per token (newest created_at, tie-breaking by id).
    op.execute(
        """
        DELETE FROM devices
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY push_token ORDER BY created_at DESC, id DESC
                ) AS rn
                FROM devices
            ) sub
            WHERE rn = 1
        )
        """
    )

    with op.batch_alter_table("devices") as batch_op:
        batch_op.add_column(
            sa.Column(
                "app_id",
                sa.String(length=255),
                nullable=False,
                server_default="kz.cashbackone.mobile",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch_op.add_column(
            sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.alter_column(
            "push_token",
            existing_type=sa.String(length=512),
            type_=sa.String(length=1024),
            existing_nullable=False,
        )
        batch_op.create_index("ix_devices_push_token", ["push_token"], unique=True)

    # For existing rows, align last_seen_at with created_at
    op.execute("UPDATE devices SET last_seen_at = created_at WHERE created_at IS NOT NULL")


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch_op:
        batch_op.drop_index("ix_devices_push_token")
        batch_op.alter_column(
            "push_token",
            existing_type=sa.String(length=1024),
            type_=sa.String(length=512),
            existing_nullable=False,
        )
        batch_op.drop_column("disabled_at")
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("app_id")
