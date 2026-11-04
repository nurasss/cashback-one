"""Business stores and localized app texts.

Revision ID: 0013_business_app_content
Revises: 0012_push_devices
Create Date: 2026-11-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_business_app_content"
down_revision: str | None = "0012_push_devices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch_op:
        batch_op.add_column(sa.Column("app_texts", sa.JSON(), nullable=True))

    op.create_table(
        "business_stores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("title_ru", sa.String(length=160), nullable=False),
        sa.Column("title_kk", sa.String(length=160), nullable=False),
        sa.Column("address_ru", sa.String(length=255), nullable=False),
        sa.Column("address_kk", sa.String(length=255), nullable=False),
        sa.Column("map_url", sa.String(length=1024), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name="fk_business_stores_business_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_business_stores"),
    )
    op.create_index(
        "ix_business_stores_business_id",
        "business_stores",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_business_stores_active_sort",
        "business_stores",
        ["business_id", "is_active", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_business_stores_active_sort", table_name="business_stores")
    op.drop_index("ix_business_stores_business_id", table_name="business_stores")
    op.drop_table("business_stores")

    with op.batch_alter_table("businesses") as batch_op:
        batch_op.drop_column("app_texts")
