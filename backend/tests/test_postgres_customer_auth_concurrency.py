import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import generate_challenge_code, hash_challenge_code
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.entities import LoginChallenge, User
from app.services.auth_confirmation import confirm_login_challenge
from app.services.user_service import get_or_create_user_by_phone


@pytest.fixture
async def pg_engine():  # type: ignore[no-untyped-def]
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL 16 connection skipped: {exc}")

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def pg_session_maker(pg_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def pg_client(pg_session_maker) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[no-untyped-def]
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pg_auth_01_concurrent_confirmation(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-AUTH-01: Two concurrent confirmation events with the same code.

    Both must complete cleanly without 500 / IntegrityError.
    Exactly one deterministic identity is saved.
    """
    code = generate_challenge_code()
    async with pg_session_maker() as s:
        challenge = LoginChallenge(
            device_id="dev-pg-auth-1",
            code_hash=hash_challenge_code(code),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        s.add(challenge)
        await s.commit()
        challenge_id = challenge.id

    async def worker_confirm(phone: str) -> None:
        async with pg_session_maker() as s:
            await confirm_login_challenge(s, code, phone)

    # Concurrently confirm with the same phone
    await asyncio.gather(
        worker_confirm("+77017770001"),
        worker_confirm("+77017770001"),
    )

    async with pg_session_maker() as s:
        c = await s.get(LoginChallenge, challenge_id)
        assert c is not None
        assert c.status == "confirmed"
        assert c.phone == "+77017770001"


@pytest.mark.asyncio
async def test_pg_auth_02_concurrent_same_phone_user_creation(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-AUTH-02: Two concurrent auth flows for the same phone create exactly 1 User."""
    phone = "+77019994455"

    async def worker_get_user() -> User:
        async with pg_session_maker() as s:
            user = await get_or_create_user_by_phone(s, phone)
            await s.commit()
            return user

    u1, u2 = await asyncio.gather(worker_get_user(), worker_get_user())
    assert u1.id == u2.id

    async with pg_session_maker() as s:
        users = (
            await s.scalars(select(User).where(User.phone == phone))
        ).all()
        assert len(users) == 1


@pytest.mark.asyncio
async def test_pg_auth_03_concurrent_refresh_rotation(
    pg_client: AsyncClient,
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-AUTH-03: Two concurrent refresh requests with same token -> exactly 1 winner."""
    device_id = "pg-dev-rot"
    create_res = await pg_client.post("/auth/challenge", json={"device_id": device_id})
    c_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    async with pg_session_maker() as s:
        await confirm_login_challenge(s, code, "+77013332211")

    poll = await pg_client.get(f"/auth/challenge/{c_id}", headers={"X-Device-Id": device_id})
    raw_refresh = poll.json()["refresh_token"]

    # Concurrently refresh using the exact same refresh token
    res1, res2 = await asyncio.gather(
        pg_client.post("/auth/refresh", json={"refresh_token": raw_refresh}),
        pg_client.post("/auth/refresh", json={"refresh_token": raw_refresh}),
    )

    statuses = [res1.status_code, res2.status_code]
    assert 200 in statuses
    assert 401 in statuses

    # The winning response has new tokens
    winner = res1 if res1.status_code == 200 else res2
    loser = res2 if res1.status_code == 200 else res1

    assert "access_token" in winner.json()
    assert loser.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_pg_auth_04_unique_phone_constraint(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-AUTH-04: DB unique constraint prevents duplicate non-null phone records."""
    async with pg_session_maker() as s:
        u1 = User(phone="+77028881122", language="ru")
        s.add(u1)
        await s.commit()

    # Second user with same phone must raise IntegrityError
    with pytest.raises(IntegrityError):
        async with pg_session_maker() as s:
            u2 = User(phone="+77028881122", language="kz")
            s.add(u2)
            await s.commit()
