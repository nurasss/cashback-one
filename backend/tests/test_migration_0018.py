"""Tests for Alembic migration 0018 (business_splash_config and business_splash_assets)."""
import importlib
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

migration_0018 = importlib.import_module("migrations.versions.0018_business_splash_config")


def test_migration_0018_upgrade_and_downgrade_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE businesses ("
                "  id TEXT PRIMARY KEY,"
                "  name TEXT NOT NULL"
                ")"
            )
        )
        conn.commit()

        # Upgrade
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        migration_0018.op = op
        migration_0018.upgrade()
        conn.commit()

        # Check splash_config column added
        inspector = inspect(conn)
        biz_cols = [c["name"] for c in inspector.get_columns("businesses")]
        assert "splash_config" in biz_cols

        # Check business_splash_assets table created
        tables = inspector.get_table_names()
        assert "business_splash_assets" in tables
        asset_cols = [c["name"] for c in inspector.get_columns("business_splash_assets")]
        assert "id" in asset_cols
        assert "business_id" in asset_cols
        assert "media_type" in asset_cols
        assert "media_url" in asset_cols
        assert "width" in asset_cols
        assert "height" in asset_cols
        assert "duration_seconds" in asset_cols
        assert "file_size" in asset_cols
        assert "created_at" in asset_cols

        # Downgrade
        migration_0018.downgrade()
        conn.commit()

        # Check table dropped and column removed
        inspector = inspect(conn)
        assert "business_splash_assets" not in inspector.get_table_names()
        biz_cols_after = [c["name"] for c in inspector.get_columns("businesses")]
        assert "splash_config" not in biz_cols_after


@pytest.mark.asyncio
async def test_migration_0018_postgres() -> None:
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url)

        def run_mig_test(conn: sa.Connection) -> None:
            conn.execute(text("DROP TABLE IF EXISTS test_mig_splash_assets CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS test_mig_businesses CASCADE"))
            conn.execute(
                text(
                    "CREATE TABLE test_mig_businesses ("
                    "  id UUID PRIMARY KEY,"
                    "  name VARCHAR(120) NOT NULL"
                    ")"
                )
            )

            # Upgrade
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            with op.batch_alter_table("test_mig_businesses") as batch_op:
                batch_op.add_column(sa.Column("splash_config", sa.JSON(), nullable=True))

            op.create_table(
                "test_mig_splash_assets",
                sa.Column("id", sa.Uuid(), primary_key=True),
                sa.Column(
                    "business_id",
                    sa.Uuid(),
                    sa.ForeignKey("test_mig_businesses.id", ondelete="CASCADE"),
                    nullable=True,
                ),
                sa.Column("media_type", sa.String(length=16), nullable=False),
                sa.Column("media_url", sa.String(length=512), nullable=False),
                sa.Column("width", sa.Integer(), nullable=False),
                sa.Column("height", sa.Integer(), nullable=False),
                sa.Column("duration_seconds", sa.Float(), nullable=True),
                sa.Column("file_size", sa.Integer(), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            )
            op.create_index(
                "ix_test_mig_splash_assets_business_id",
                "test_mig_splash_assets",
                ["business_id"],
            )
            op.create_index(
                "ix_test_mig_splash_assets_media_url",
                "test_mig_splash_assets",
                ["media_url"],
                unique=True,
            )

            inspector = inspect(conn)
            tables = inspector.get_table_names()
            assert "test_mig_splash_assets" in tables
            cols = [c["name"] for c in inspector.get_columns("test_mig_splash_assets")]
            assert "media_url" in cols
            assert "duration_seconds" in cols

            # Insert test records
            conn.execute(
                text(
                    "INSERT INTO test_mig_businesses (id, name, splash_config) "
                    "VALUES (gen_random_uuid(), 'Test Biz', '{\"enabled\": true}')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO test_mig_splash_assets (id, media_type, media_url, width, height, duration_seconds, file_size, created_at) "
                    "VALUES (gen_random_uuid(), 'video', 'https://cdn.example.kz/splash.mp4', 1080, 1920, 4.5, 1024000, now())"
                )
            )

            # Downgrade
            op.drop_index("ix_test_mig_splash_assets_media_url", table_name="test_mig_splash_assets")
            op.drop_index("ix_test_mig_splash_assets_business_id", table_name="test_mig_splash_assets")
            op.drop_table("test_mig_splash_assets")
            with op.batch_alter_table("test_mig_businesses") as batch_op:
                batch_op.drop_column("splash_config")

            inspector = inspect(conn)
            assert "test_mig_splash_assets" not in inspector.get_table_names()
            cols_after = [c["name"] for c in inspector.get_columns("test_mig_businesses")]
            assert "splash_config" not in cols_after

            # Clean up
            conn.execute(text("DROP TABLE IF EXISTS test_mig_businesses CASCADE"))

        async with engine.begin() as aconn:
            await aconn.run_sync(run_mig_test)

    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL migration test skipped: {exc}")
