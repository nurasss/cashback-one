"""User card visibility and transaction history indexing

Revision ID: 0006_user_card_visibility
Revises: 0005_wappi_webhook_events
Create Date: 2026-09-29 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_user_card_visibility"
down_revision: str | None = "0005_wappi_webhook_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_cards",
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_cards_user_id_hidden_at",
        "user_cards",
        ["user_id", "hidden_at"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_card_id_occurred_at",
        "transactions",
        ["card_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_card_id_occurred_at", table_name="transactions")
    op.drop_index("ix_user_cards_user_id_hidden_at", table_name="user_cards")
    op.drop_column("user_cards", "hidden_at")
