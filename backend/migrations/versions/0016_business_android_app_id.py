"""Add android_app_id to businesses table.

Revision ID: 0016_business_android_app_id
Revises: 0015_notification_redemption
Create Date: 2026-11-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_business_android_app_id"
down_revision: str | None = "0015_notification_redemption"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.add_column(
            sa.Column("android_app_id", sa.String(length=255), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_businesses_android_app_id", ["android_app_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.drop_constraint("uq_businesses_android_app_id", type_="unique")
        batch_op.drop_column("android_app_id")
