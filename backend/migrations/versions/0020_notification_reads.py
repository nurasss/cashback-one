"""Per-user read receipts for notifications (exact-ID "mark read").

Additive only: one new table and one index. No backfill, no change to existing tables.

Revision ID: 0020_notification_reads
Revises: 0019_coords_and_loyalty_tiers
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_notification_reads"
down_revision: str | None = "0019_coords_and_loyalty_tiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_reads",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notification_id",
            sa.Uuid(),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "notification_id"),
    )
    op.create_index(
        "ix_notification_reads_notification_id", "notification_reads", ["notification_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notification_reads_notification_id", table_name="notification_reads")
    op.drop_table("notification_reads")
