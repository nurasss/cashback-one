"""Add agent heartbeat fields

Revision ID: 0002_agent_heartbeat_fields
Revises: 0001_initial_schema
Create Date: 2026-09-29 13:00:00.000000

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_agent_heartbeat_fields"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("last_error", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "last_error")
    op.drop_column("agents", "last_sync_at")
