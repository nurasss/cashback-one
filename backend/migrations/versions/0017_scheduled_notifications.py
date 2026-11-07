"""Add scheduled_at and push_sent_at to notifications table.

Revision ID: 0017_scheduled_notifications
Revises: 0016_business_android_app_id
Create Date: 2026-11-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_scheduled_notifications"
down_revision: str | None = "0016_business_android_app_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("push_sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_notifications_scheduled_pending", ["scheduled_at", "push_sent_at"]
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_scheduled_pending")
        batch_op.drop_column("push_sent_at")
        batch_op.drop_column("scheduled_at")
