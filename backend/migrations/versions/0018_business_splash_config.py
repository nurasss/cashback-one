"""Add splash_config JSON column to businesses table.

Revision ID: 0018_business_splash_config
Revises: 0017_scheduled_notifications
Create Date: 2026-11-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_business_splash_config"
down_revision: str | None = "0017_scheduled_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.add_column(
            sa.Column("splash_config", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.drop_column("splash_config")
