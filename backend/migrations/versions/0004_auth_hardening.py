"""Auth hardening: unique constraint on login_challenges code_hash

Revision ID: 0004_auth_hardening
Revises: 0003_customer_auth_core
Create Date: 2026-09-29 16:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_auth_hardening"
down_revision: str | None = "0003_customer_auth_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("login_challenges") as batch_op:
        batch_op.create_unique_constraint(
            "uq_login_challenges_code_hash", ["code_hash"]
        )


def downgrade() -> None:
    with op.batch_alter_table("login_challenges") as batch_op:
        batch_op.drop_constraint("uq_login_challenges_code_hash", type_="unique")
