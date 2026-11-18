"""Fixture that runs a test on SQLite (always) and on PostgreSQL (when POSTGRES_TEST_URL points at a throw-away database)."""
import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.db.base import Base


@pytest.fixture(params=["sqlite", "postgres"])
async def engine(request: pytest.FixtureRequest, db_engine: AsyncEngine) -> AsyncGenerator[AsyncEngine, None]:
    if request.param == "sqlite":
        yield db_engine
        return
    url = os.environ.get("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("POSTGRES_TEST_URL is not configured")
    pg = create_async_engine(url, echo=False)
    async with pg.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield pg
    async with pg.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await pg.dispose()
