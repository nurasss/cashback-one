"""Add store coordinates, business loyalty tiers and tiers version.

Revision ID: 0019_coords_and_loyalty_tiers
Revises: 0018_business_splash_config
Create Date: 2026-11-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_coords_and_loyalty_tiers"
down_revision: str | None = "0018_business_splash_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.add_column(
            sa.Column("loyalty_tiers_version", sa.Integer(), nullable=False, server_default="1")
        )

    with op.batch_alter_table("business_stores") as batch_op:
        batch_op.add_column(
            sa.Column("latitude", sa.Numeric(9, 6), nullable=True)
        )
        batch_op.add_column(
            sa.Column("longitude", sa.Numeric(9, 6), nullable=True)
        )

    op.create_table(
        "business_loyalty_tiers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("business_id", sa.Uuid(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("name_kk", sa.String(length=120), nullable=False),
        sa.Column("description_ru", sa.Text(), nullable=True),
        sa.Column("description_kk", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("turnover_period_months", sa.Integer(), nullable=False),
        sa.Column("min_turnover", sa.Numeric(14, 2), nullable=False),
        sa.Column("max_turnover", sa.Numeric(14, 2), nullable=True),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "level", name="uq_business_loyalty_tiers_biz_level"),
        sa.UniqueConstraint("business_id", "priority", name="uq_business_loyalty_tiers_biz_priority"),
        sa.CheckConstraint("turnover_period_months >= 1 AND turnover_period_months <= 36", name="ck_loyalty_tiers_period"),
        sa.CheckConstraint("min_turnover >= 0", name="ck_loyalty_tiers_min_turnover"),
        sa.CheckConstraint("percent >= 0 AND percent <= 100", name="ck_loyalty_tiers_percent"),
    )
    op.create_index("ix_business_loyalty_tiers_business_id", "business_loyalty_tiers", ["business_id"])
    op.create_index("ix_business_loyalty_tiers_biz_active", "business_loyalty_tiers", ["business_id", "is_active", "priority"])


def downgrade() -> None:
    op.drop_index("ix_business_loyalty_tiers_biz_active", table_name="business_loyalty_tiers")
    op.drop_index("ix_business_loyalty_tiers_business_id", table_name="business_loyalty_tiers")
    op.drop_table("business_loyalty_tiers")

    with op.batch_alter_table("business_stores") as batch_op:
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")

    with op.batch_alter_table("businesses") as batch_op:
        batch_op.drop_column("loyalty_tiers_version")
