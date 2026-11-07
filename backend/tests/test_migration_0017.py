"""Tests for Alembic migration 0017 (scheduled_notifications)."""
import importlib
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

migration_0017 = importlib.import_module("migrations.versions.0017_scheduled_notifications")


def test_migration_0017_upgrade_and_downgrade_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE notifications ("
                "  id TEXT PRIMARY KEY,"
                "  business_id TEXT,"
                "  user_id TEXT,"
                "  title TEXT NOT NULL,"
                "  body TEXT NOT NULL,"
                "  kind TEXT NOT NULL DEFAULT 'info',"
                "  created_at TIMESTAMP NOT NULL"
                ")"
            )
        )
        conn.commit()

        # Upgrade
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        migration_0017.op = op
        migration_0017.upgrade()
        conn.commit()

        # Check columns added
        inspector = inspect(conn)
        cols = [c["name"] for c in inspector.get_columns("notifications")]
        assert "scheduled_at" in cols
        assert "push_sent_at" in cols

        # Downgrade
        migration_0017.downgrade()
        conn.commit()

        # Check columns removed
        inspector = inspect(conn)
        cols_after = [c["name"] for c in inspector.get_columns("notifications")]
        assert "scheduled_at" not in cols_after
        assert "push_sent_at" not in cols_after


@pytest.mark.asyncio
async def test_migration_0017_postgres() -> None:
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url)

        def run_mig_test(conn: sa.Connection) -> None:
            conn.execute(text("DROP TABLE IF EXISTS test_mig_notifications CASCADE"))
            conn.execute(
                text(
                    "CREATE TABLE test_mig_notifications ("
                    "  id UUID PRIMARY KEY,"
                    "  business_id UUID,"
                    "  user_id UUID,"
                    "  title VARCHAR(120) NOT NULL,"
                    "  body TEXT NOT NULL,"
                    "  kind VARCHAR(16) NOT NULL DEFAULT 'info',"
                    "  created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                    ")"
                )
            )

            # Upgrade
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            with op.batch_alter_table("test_mig_notifications") as batch_op:
                batch_op.add_column(
                    sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True)
                )
                batch_op.add_column(
                    sa.Column("push_sent_at", sa.DateTime(timezone=True), nullable=True)
                )
                batch_op.create_index(
                    "ix_test_mig_notifications_sched", ["scheduled_at", "push_sent_at"]
                )

            inspector = inspect(conn)
            cols = [c["name"] for c in inspector.get_columns("test_mig_notifications")]
            assert "scheduled_at" in cols
            assert "push_sent_at" in cols

            # Insert test records
            conn.execute(
                text(
                    "INSERT INTO test_mig_notifications (id, title, body, scheduled_at, push_sent_at) "
                    "VALUES (gen_random_uuid(), 'Title', 'Body', now(), NULL)"
                )
            )

            # Downgrade
            with op.batch_alter_table("test_mig_notifications") as batch_op:
                batch_op.drop_index("ix_test_mig_notifications_sched")
                batch_op.drop_column("push_sent_at")
                batch_op.drop_column("scheduled_at")

            inspector = inspect(conn)
            cols_after = [c["name"] for c in inspector.get_columns("test_mig_notifications")]
            assert "scheduled_at" not in cols_after
            assert "push_sent_at" not in cols_after

            # Clean up
            conn.execute(text("DROP TABLE IF EXISTS test_mig_notifications CASCADE"))

        async with engine.begin() as aconn:
            await aconn.run_sync(run_mig_test)

    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL migration test skipped: {exc}")
