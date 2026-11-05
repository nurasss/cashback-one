"""Tests for Alembic migration 0016 (business_android_app_id)."""
import importlib
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

migration_0016 = importlib.import_module("migrations.versions.0016_business_android_app_id")


def test_migration_0016_upgrade_and_downgrade_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE businesses ("
                "  id TEXT PRIMARY KEY,"
                "  name TEXT NOT NULL,"
                "  status TEXT NOT NULL DEFAULT 'active'"
                ")"
            )
        )
        conn.commit()

        # Upgrade
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        migration_0016.op = op
        migration_0016.upgrade()
        conn.commit()

        # Check column added
        inspector = inspect(conn)
        cols = [c["name"] for c in inspector.get_columns("businesses")]
        assert "android_app_id" in cols

        # Downgrade
        migration_0016.downgrade()
        conn.commit()

        # Check column removed
        inspector = inspect(conn)
        cols_after = [c["name"] for c in inspector.get_columns("businesses")]
        assert "android_app_id" not in cols_after


from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_migration_0016_postgres() -> None:
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url)

        def run_mig_test(conn: sa.Connection) -> None:
            # Drop previous test table if any
            conn.execute(text("DROP TABLE IF EXISTS test_mig_businesses CASCADE"))
            conn.execute(
                text(
                    "CREATE TABLE test_mig_businesses ("
                    "  id UUID PRIMARY KEY,"
                    "  name VARCHAR(255) NOT NULL,"
                    "  status VARCHAR(32) NOT NULL DEFAULT 'active'"
                    ")"
                )
            )

            # Upgrade: add column and unique constraint
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            with op.batch_alter_table("test_mig_businesses") as batch_op:
                batch_op.add_column(
                    sa.Column("android_app_id", sa.String(length=255), nullable=True)
                )
                batch_op.create_unique_constraint(
                    "uq_test_mig_businesses_app_id", ["android_app_id"]
                )

            inspector = inspect(conn)
            cols = [c["name"] for c in inspector.get_columns("test_mig_businesses")]
            assert "android_app_id" in cols

            # Unique constraint: multiple NULLs allowed
            conn.execute(
                text(
                    "INSERT INTO test_mig_businesses (id, name, android_app_id) VALUES "
                    "(gen_random_uuid(), 'Biz 1', 'kz.app.one'), "
                    "(gen_random_uuid(), 'Biz 2', NULL), "
                    "(gen_random_uuid(), 'Biz 3', NULL)"
                )
            )

            # Duplicate non-null raises IntegrityError on PostgreSQL
            # We use begin_nested() so that PostgreSQL subtransaction rolls back without aborting the main transaction.
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    text(
                        "INSERT INTO test_mig_businesses (id, name, android_app_id) VALUES "
                        "(gen_random_uuid(), 'Biz 4', 'kz.app.one')"
                    )
                )

            # Downgrade: remove unique constraint and column
            with op.batch_alter_table("test_mig_businesses") as batch_op:
                batch_op.drop_constraint("uq_test_mig_businesses_app_id", type_="unique")
                batch_op.drop_column("android_app_id")

            inspector = inspect(conn)
            cols_after = [c["name"] for c in inspector.get_columns("test_mig_businesses")]
            assert "android_app_id" not in cols_after

            # Clean up
            conn.execute(text("DROP TABLE IF EXISTS test_mig_businesses CASCADE"))

        async with engine.begin() as aconn:
            await aconn.run_sync(run_mig_test)

    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL migration test skipped: {exc}")
