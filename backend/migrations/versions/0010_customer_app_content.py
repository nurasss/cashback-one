"""Customer app: profile fields, loyalty levels, promotions, notifications, redemption codes.

Revision ID: 0010_customer_app_content
Revises: 0009_admin_mutations
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_customer_app_content"
down_revision: str | None = "0009_admin_mutations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILE_COLUMNS = [
    sa.Column("first_name", sa.String(length=100), nullable=True),
    sa.Column("last_name", sa.String(length=100), nullable=True),
    sa.Column("email", sa.String(length=255), nullable=True),
    sa.Column("gender", sa.String(length=16), nullable=True),
    sa.Column("city", sa.String(length=100), nullable=True),
    sa.Column("address", sa.String(length=255), nullable=True),
    sa.Column("birth_date", sa.Date(), nullable=True),
    sa.Column("iin", sa.String(length=12), nullable=True),
    sa.Column("company", sa.String(length=255), nullable=True),
    sa.Column("promotions_seen_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("notifications_seen_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    for column in _PROFILE_COLUMNS:
        op.add_column("users", column.copy())
    op.add_column("businesses", sa.Column("loyalty_tiers", sa.JSON(), nullable=True))
    op.add_column("cards", sa.Column("spend_total", sa.Numeric(18, 4), nullable=True))

    op.create_table(
        "promotions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("badge", sa.String(length=40), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promotions_business_id", "promotions", ["business_id"])
    op.create_index("ix_promotions_active_sort", "promotions", ["is_active", "sort_order"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index(
        "ix_notifications_business_created", "notifications", ["business_id", "created_at"]
    )

    op.create_table(
        "redemption_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_redemption_codes_card_created", "redemption_codes", ["card_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_redemption_codes_card_created", table_name="redemption_codes")
    op.drop_table("redemption_codes")
    op.drop_index("ix_notifications_business_created", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_promotions_active_sort", table_name="promotions")
    op.drop_index("ix_promotions_business_id", table_name="promotions")
    op.drop_table("promotions")
    op.drop_column("cards", "spend_total")
    op.drop_column("businesses", "loyalty_tiers")
    for column in reversed(_PROFILE_COLUMNS):
        op.drop_column("users", column.name)
