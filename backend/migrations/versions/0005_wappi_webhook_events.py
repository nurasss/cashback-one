"""Wappi webhook idempotency log and audit trail

Revision ID: 0005_wappi_webhook_events
Revises: 0004_auth_hardening
Create Date: 2026-09-29 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_wappi_webhook_events"
down_revision: str | None = "0004_auth_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wappi_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("wh_type", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "message_id", name="uq_wappi_webhook_events_profile_message"),
    )
    op.create_index(
        "ix_wappi_webhook_events_received_at",
        "wappi_webhook_events",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_wappi_webhook_events_received_at", table_name="wappi_webhook_events")
    op.drop_table("wappi_webhook_events")
