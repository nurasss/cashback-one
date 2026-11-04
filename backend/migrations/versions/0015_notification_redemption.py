"""Notification link to redemption code.

Revision ID: 0015_notification_redemption
Revises: 0014_pos_keys
Create Date: 2026-11-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_notification_redemption"
down_revision: str | None = "0014_pos_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("redemption_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notifications_redemption_id",
            "redemption_codes",
            ["redemption_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_notifications_redemption_id",
            ["redemption_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_redemption_id")
        batch_op.drop_constraint("fk_notifications_redemption_id", type_="foreignkey")
        batch_op.drop_column("redemption_id")
