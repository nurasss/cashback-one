import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.entities import AuthSession, OtpCode, User
from app.services.rate_limiter import _test_limiter
from app.services.sms_provider import get_fake_sms_provider


@pytest.fixture
async def pg_engine():  # type: ignore[no-untyped-def]
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL connection skipped: {exc}")

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def pg_session_maker(pg_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
def reset_concurrency_state() -> None:
    _test_limiter.reset()
    fake = get_fake_sms_provider()
    fake.clear()


@pytest.mark.asyncio
async def test_pg_sms_01_concurrent_otp_requests_leave_one_active(
    pg_session_maker, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    """PG-SMS-01: Concurrent OTP requests for same (phone, device_id).

    Ensures:
    - Multiple concurrent requests for the same phone & device complete without DB conflict.
    - Exactly 1 OTP code remains in 'pending' status.
    - Previous OTP codes are marked 'superseded'.
    """
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    monkeypatch.setattr(settings, "sms_otp_request_phone_limit", 100)
    monkeypatch.setattr(settings, "sms_otp_request_device_limit", 100)
    monkeypatch.setattr(settings, "sms_otp_request_ip_limit", 100)

    phone = "+77019990001"
    device_id = "pg-dev-sms-01"

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        barrier = asyncio.Barrier(5)

        async def worker(ac: AsyncClient) -> tuple[int, dict]:  # type: ignore[type-arg]
            await barrier.wait()
            resp = await ac.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
            return resp.status_code, resp.json()

        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            results = await asyncio.gather(*(worker(ac) for _ in range(5)))

        for status_code, body in results:
            assert status_code == 200
            assert body["status"] == "sent"

        async with pg_session_maker() as s:
            pending_records = (
                await s.execute(
                    select(OtpCode).where(
                        OtpCode.phone == phone,
                        OtpCode.device_id == device_id,
                        OtpCode.status == "pending",
                    )
                )
            ).scalars().all()
            assert len(pending_records) == 1

            superseded_records = (
                await s.execute(
                    select(OtpCode).where(
                        OtpCode.phone == phone,
                        OtpCode.device_id == device_id,
                        OtpCode.status == "superseded",
                    )
                )
            ).scalars().all()
            assert len(superseded_records) == 4
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pg_sms_02_concurrent_wrong_verifies_cannot_bypass_max_attempts(
    pg_session_maker, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    """PG-SMS-02: Concurrent wrong verifies cannot bypass max 5 attempts.

    Row-level locking (`with_for_update()`) serializes verification attempts:
    - 10 concurrent requests send invalid OTP codes.
    - Exactly 5 incorrect attempts are counted before status transitions to 'exhausted'.
    - An attacker cannot bypass the 5-attempt limit through concurrent racing.
    """
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake = get_fake_sms_provider()

    phone = "+77019990002"
    device_id = "pg-dev-sms-02"

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        # Request OTP
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            req_res = await ac.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
            assert req_res.status_code == 200

            correct_code = fake.sent_messages[0][1]
            wrong_code = "000000" if correct_code != "000000" else "111111"

            barrier = asyncio.Barrier(10)

            async def worker() -> tuple[int, str]:
                await barrier.wait()
                resp = await ac.post(
                    "/auth/sms/verify",
                    json={"phone": phone, "device_id": device_id, "code": wrong_code},
                )
                err_code = resp.json().get("error", {}).get("code", "")
                return resp.status_code, err_code

            results = await asyncio.gather(*(worker() for _ in range(10)))

        for status_code, _ in results:
            assert status_code == 400

        codes = [r[1] for r in results]
        assert "INVALID_CODE" in codes
        assert "OTP_MAX_ATTEMPTS_EXCEEDED" in codes or "OTP_NOT_FOUND" in codes

        async with pg_session_maker() as s:
            otp_record = (
                await s.execute(
                    select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
                )
            ).scalar_one()
            assert otp_record.status == "exhausted"
            assert otp_record.attempts == 5
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pg_sms_03_concurrent_correct_verify_creates_exactly_one_session(
    pg_session_maker, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    """PG-SMS-03: Concurrent correct verify creates exactly 1 session.

    - 5 concurrent requests verify with the correct code.
    - Row-level lock ensures exactly 1 request succeeds (status 200).
    - Other 4 requests get rejected (status 400 OTP_NOT_FOUND).
    - Exactly 1 AuthSession is created in DB.
    """
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake = get_fake_sms_provider()

    phone = "+77019990003"
    device_id = "pg-dev-sms-03"

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            req_res = await ac.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
            assert req_res.status_code == 200
            correct_code = fake.sent_messages[0][1]

            barrier = asyncio.Barrier(5)

            async def worker() -> tuple[int, dict]:  # type: ignore[type-arg]
                await barrier.wait()
                resp = await ac.post(
                    "/auth/sms/verify",
                    json={"phone": phone, "device_id": device_id, "code": correct_code},
                )
                return resp.status_code, resp.json()

            results = await asyncio.gather(*(worker() for _ in range(5)))

        status_codes = [r[0] for r in results]
        assert status_codes.count(200) == 1
        assert status_codes.count(400) == 4

        winner = next(r[1] for r in results if r[0] == 200)
        assert "access_token" in winner
        assert "refresh_token" in winner

        async with pg_session_maker() as s:
            user = (await s.execute(select(User).where(User.phone == phone))).scalar_one()
            sessions = (
                await s.execute(
                    select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.device_id == device_id)
                )
            ).scalars().all()
            assert len(sessions) == 1

            otp_record = (
                await s.execute(
                    select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
                )
            ).scalar_one()
            assert otp_record.status == "consumed"
            assert otp_record.verified_at is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pg_sms_04_provider_failure_rollback_leaves_no_active_otp(
    pg_session_maker, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    """PG-SMS-04: Provider failure rollback leaves no active OTP.

    - Provider raises delivery failure.
    - Transaction rollback ensures 0 OtpCode records are saved.
    - 503 SMS_DELIVERY_UNAVAILABLE returned to client.
    """
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake = get_fake_sms_provider()
    fake.fail_next = True

    phone = "+77019990004"
    device_id = "pg-dev-sms-04"

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            res = await ac.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
            assert res.status_code == 503
            assert res.json()["error"]["code"] == "SMS_DELIVERY_UNAVAILABLE"

        async with pg_session_maker() as s:
            records = (
                await s.execute(
                    select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
                )
            ).scalars().all()
            assert len(records) == 0
    finally:
        app.dependency_overrides.clear()
