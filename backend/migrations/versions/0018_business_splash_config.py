"""Add splash_config JSON column and business_splash_assets table.

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

    op.create_table(
        "business_splash_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("business_id", sa.Uuid(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("media_type", sa.String(length=16), nullable=False),
        sa.Column("media_url", sa.String(length=512), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_splash_assets_business_id", "business_splash_assets", ["business_id"])
    op.create_index("ix_business_splash_assets_media_url", "business_splash_assets", ["media_url"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_business_splash_assets_media_url", table_name="business_splash_assets")
    op.drop_index("ix_business_splash_assets_business_id", table_name="business_splash_assets")
    op.drop_table("business_splash_assets")
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.drop_column("splash_config")
