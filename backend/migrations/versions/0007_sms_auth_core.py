"""SMS authentication core schema: expand otp_codes table
 
Revision ID: 0007_sms_auth_core
Revises: 0006_user_card_visibility
Create Date: 2026-09-29 21:00:00.000000
 
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_sms_auth_core"
down_revision: str | None = "0006_user_card_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "otp_codes",
        sa.Column("device_id", sa.String(length=128), server_default="", nullable=False),
    )
    op.add_column(
        "otp_codes",
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
    )
    op.add_column(
        "otp_codes",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "otp_codes",
        "code_hash",
        type_=sa.String(length=64),
        existing_type=sa.String(length=255),
    )
    op.create_index(
        "ix_otp_codes_phone_device_id",
        "otp_codes",
        ["phone", "device_id"],
        unique=False,
    )
    op.drop_index("ix_otp_codes_phone", table_name="otp_codes")


def downgrade() -> None:
    op.create_index("ix_otp_codes_phone", "otp_codes", ["phone"], unique=False)
    op.drop_index("ix_otp_codes_phone_device_id", table_name="otp_codes")
    op.alter_column(
        "otp_codes",
        "code_hash",
        type_=sa.String(length=255),
        existing_type=sa.String(length=64),
    )
    op.drop_column("otp_codes", "verified_at")
    op.drop_column("otp_codes", "status")
    op.drop_column("otp_codes", "device_id")
