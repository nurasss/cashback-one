"""Tests for Alembic migration 0019 (stores coordinates and loyalty tiers)."""
import asyncio
import importlib
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

migration_0019 = importlib.import_module("migrations.versions.0019_coords_and_loyalty_tiers")


def test_migration_0019_upgrade_and_downgrade_sqlite() -> None:
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
        conn.execute(
            text(
                "CREATE TABLE business_stores ("
                "  id TEXT PRIMARY KEY,"
                "  business_id TEXT NOT NULL,"
                "  title_ru TEXT NOT NULL"
                ")"
            )
        )
        conn.commit()

        # Upgrade
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        migration_0019.op = op
        migration_0019.upgrade()
        conn.commit()

        inspector = inspect(conn)
        biz_cols = [c["name"] for c in inspector.get_columns("businesses")]
        assert "loyalty_tiers_version" in biz_cols

        store_cols = [c["name"] for c in inspector.get_columns("business_stores")]
        assert "latitude" in store_cols
        assert "longitude" in store_cols

        tables = inspector.get_table_names()
        assert "business_loyalty_tiers" in tables
        tier_cols = [c["name"] for c in inspector.get_columns("business_loyalty_tiers")]
        assert "id" in tier_cols
        assert "business_id" in tier_cols
        assert "level" in tier_cols
        assert "priority" in tier_cols
        assert "turnover_period_months" in tier_cols
        assert "min_turnover" in tier_cols
        assert "max_turnover" in tier_cols
        assert "percent" in tier_cols

        # Downgrade
        migration_0019.downgrade()
        conn.commit()

        inspector = inspect(conn)
        tables = inspector.get_table_names()
        assert "business_loyalty_tiers" not in tables
        store_cols = [c["name"] for c in inspector.get_columns("business_stores")]
        assert "latitude" not in store_cols
        assert "longitude" not in store_cols
        biz_cols = [c["name"] for c in inspector.get_columns("businesses")]
        assert "loyalty_tiers_version" not in biz_cols


@pytest.mark.asyncio
async def test_migration_0019_postgres_up_down_up() -> None:
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    migrations_path = backend_dir / "migrations"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(migrations_path))

    old_db_url = settings.database_url
    old_env = os.environ.get("DATABASE_URL")
    settings.database_url = pg_url
    os.environ["DATABASE_URL"] = pg_url

    engine = create_async_engine(pg_url)
    try:
        # Reset database to base if previous run left migrations
        async with engine.connect() as conn:
            has_alembic = await conn.scalar(text("SELECT to_regclass('alembic_version')::text;"))
        if has_alembic:
            await asyncio.to_thread(command.downgrade, cfg, "base")

        # 1. Upgrade through full history up to 0018
        await asyncio.to_thread(command.upgrade, cfg, "0018_business_splash_config")

        async with engine.connect() as conn:
            tier_table_0018 = await conn.scalar(text("SELECT to_regclass('business_loyalty_tiers')::text;"))
            assert tier_table_0018 is None, "business_loyalty_tiers must not exist before migration 0019"

        # 2. Upgrade to 0019
        await asyncio.to_thread(command.upgrade, cfg, "0019_coords_and_loyalty_tiers")

        async with engine.connect() as conn:
            tier_table_0019 = await conn.scalar(text("SELECT to_regclass('business_loyalty_tiers')::text;"))
            assert tier_table_0019 == "business_loyalty_tiers", "business_loyalty_tiers must exist after 0019"

            store_coord_cols = (
                await conn.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='business_stores' AND column_name IN ('latitude', 'longitude') "
                        "ORDER BY column_name;"
                    )
                )
            ).all()
            assert list(store_coord_cols) == ["latitude", "longitude"]

            version_col = await conn.scalar(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='businesses' AND column_name='loyalty_tiers_version';"
                )
            )
            assert version_col == "loyalty_tiers_version"

        # 3. Downgrade back to 0018
        await asyncio.to_thread(command.downgrade, cfg, "0018_business_splash_config")

        async with engine.connect() as conn:
            tier_table_down = await conn.scalar(text("SELECT to_regclass('business_loyalty_tiers')::text;"))
            assert tier_table_down is None, "business_loyalty_tiers must be dropped after downgrade"

            store_coord_down = (
                await conn.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='business_stores' AND column_name IN ('latitude', 'longitude');"
                    )
                )
            ).all()
            assert len(list(store_coord_down)) == 0

        # 4. Re-upgrade to 0019 (verifying idempotent re-application)
        await asyncio.to_thread(command.upgrade, cfg, "0019_coords_and_loyalty_tiers")

        async with engine.connect() as conn:
            tier_table_re = await conn.scalar(text("SELECT to_regclass('business_loyalty_tiers')::text;"))
            assert tier_table_re == "business_loyalty_tiers"
    finally:
        try:
            await asyncio.to_thread(command.downgrade, cfg, "base")
        except Exception:
            pass
        await engine.dispose()
        settings.database_url = old_db_url
        if old_env is not None:
            os.environ["DATABASE_URL"] = old_env
        else:
            os.environ.pop("DATABASE_URL", None)
