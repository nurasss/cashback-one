import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import generate_challenge_code, hash_challenge_code
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.entities import LoginChallenge, WappiWebhookEvent


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
async def test_pg_wappi_01_concurrent_duplicate_message_delivery(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WAPPI-01: Concurrent duplicate webhook requests with identical message ID.

    ON CONFLICT DO NOTHING guarantees:
    - Exactly one request confirms the challenge and records the event.
    - Remaining concurrent requests detect the duplicate, return 200 with result='duplicate'.
    - Exactly 1 event row is stored in wappi_webhook_events.
    - Zero IntegrityError, zero unhandled 500 exceptions.
    """
    code = generate_challenge_code()
    async with pg_session_maker() as s:
        challenge = LoginChallenge(
            id=uuid.uuid4(),
            device_id="dev-pg-wappi-1",
            code_hash=hash_challenge_code(code),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        s.add(challenge)
        await s.commit()

    message_id = f"wamid.CONCURRENT_{uuid.uuid4()}"
    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": message_id,
                "body": code,
                "type": "chat",
                "from": "77017770001@c.us",
                "chat_type": "dialog",
            }
        ]
    }
    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}

    async def send_webhook() -> dict:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/webhooks/wappi", headers=headers, json=payload)
            assert resp.status_code == 200
            return resp.json()

    # 5 concurrent deliveries of the exact same message ID
    results = await asyncio.gather(*(send_webhook() for _ in range(5)))

    processed_count = sum(r["processed"] for r in results)
    duplicates_count = sum(r["duplicates"] for r in results)

    assert processed_count == 1
    assert duplicates_count == 4

    # Verify database state
    async with pg_session_maker() as s:
        event_count = (
            await s.execute(
                select(func.count(WappiWebhookEvent.id)).where(
                    WappiWebhookEvent.message_id == message_id
                )
            )
        ).scalar()
        assert event_count == 1

        c = (
            await s.execute(
                select(LoginChallenge).where(
                    LoginChallenge.code_hash == hash_challenge_code(code)
                )
            )
        ).scalar_one()
        assert c.status == "confirmed"
        assert c.phone == "+77017770001"


@pytest.mark.asyncio
async def test_pg_wappi_02_concurrent_different_senders_same_code(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WAPPI-02: Concurrent webhook messages for same code from different senders.

    Guarantees:
    - First phone wins and confirms challenge.
    - Second phone is rejected with 'already_confirmed_other_phone'.
    - Both return 200 OK to provider.
    - Two event rows are logged with respective results.
    """
    code = generate_challenge_code()
    async with pg_session_maker() as s:
        challenge = LoginChallenge(
            id=uuid.uuid4(),
            device_id="dev-pg-wappi-2",
            code_hash=hash_challenge_code(code),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        s.add(challenge)
        await s.commit()

    msg_id_1 = f"wamid.WINNER_{uuid.uuid4()}"
    msg_id_2 = f"wamid.LOSER_{uuid.uuid4()}"

    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}

    async def send_msg(msg_id: str, sender_jid: str) -> dict:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        payload = {
            "messages": [
                {
                    "wh_type": "incoming_message",
                    "profile_id": settings.wappi_login_profile_id,
                    "id": msg_id,
                    "body": code,
                    "type": "chat",
                    "from": sender_jid,
                    "chat_type": "dialog",
                }
            ]
        }
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/webhooks/wappi", headers=headers, json=payload)
            assert resp.status_code == 200
            return resp.json()

    res1, res2 = await asyncio.gather(
        send_msg(msg_id_1, "77017770001@c.us"),
        send_msg(msg_id_2, "77028880002@c.us"),
    )

    statuses = {
        res1["details"][0]["result"],
        res2["details"][0]["result"],
    }
    assert statuses == {"confirmed", "already_confirmed_other_phone"}

    async with pg_session_maker() as s:
        events = (
            await s.execute(
                select(WappiWebhookEvent).where(
                    WappiWebhookEvent.message_id.in_([msg_id_1, msg_id_2])
                )
            )
        ).scalars().all()
        assert len(events) == 2
        event_results = {e.result for e in events}
        assert event_results == {"confirmed", "already_confirmed_other_phone"}


@pytest.mark.asyncio
async def test_pg_wappi_03_db_unique_constraint(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WAPPI-03: Direct duplicate insert must violate unique constraint uq_wappi_webhook_events_profile_message."""
    msg_id = f"wamid.DIRECT_{uuid.uuid4()}"
    async with pg_session_maker() as s:
        event1 = WappiWebhookEvent(
            id=uuid.uuid4(),
            profile_id="test-profile",
            message_id=msg_id,
            wh_type="incoming_message",
            result="confirmed",
        )
        s.add(event1)
        await s.commit()

    async with pg_session_maker() as s:
        event2 = WappiWebhookEvent(
            id=uuid.uuid4(),
            profile_id="test-profile",
            message_id=msg_id,
            wh_type="incoming_message",
            result="confirmed",
        )
        s.add(event2)
        with pytest.raises(IntegrityError) as exc_info:
            await s.commit()
        assert "uq_wappi_webhook_events_profile_message" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pg_wappi_04_rollback_and_retry_atomicity(
    pg_session_maker,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PG-WAPPI-04: Idempotency + confirmation rollback and retry atomicity on PostgreSQL 16.

    Proves crash/retry semantics:
    - Reservation occurs within the active transaction.
    - Operational failure during confirmation triggers full transaction rollback.
    - First request returns controlled HTTP 503.
    - Database verification: challenge remains pending, zero event rows persisted.
    - Second request with the EXACT same message ID, profile, and code succeeds with 200.
    - Database verification: challenge is confirmed, exactly 1 event row with result='confirmed'.
    """
    code = generate_challenge_code()
    async with pg_session_maker() as s:
        challenge = LoginChallenge(
            id=uuid.uuid4(),
            device_id="dev-pg-wappi-4",
            code_hash=hash_challenge_code(code),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        s.add(challenge)
        await s.commit()
        challenge_id = challenge.id

    message_id = f"wamid.RETRY_{uuid.uuid4()}"
    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": message_id,
                "body": code,
                "type": "chat",
                "from": "77017770001@c.us",
                "chat_type": "dialog",
            }
        ]
    }
    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}

    # Step 3: Fault injection: monkeypatch confirm_login_challenge to raise SQLAlchemyError
    # (simulating failure after reservation has executed in the transaction)
    async def mock_confirm_fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise SQLAlchemyError("Simulated PostgreSQL connection drop during confirmation")

    monkeypatch.setattr(
        "app.services.wappi_webhook.confirm_login_challenge", mock_confirm_fail
    )

    async def execute_request() -> tuple[int, dict]:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/webhooks/wappi", headers=headers, json=payload)
            return resp.status_code, resp.json()

    # Step 4: First request returns 503
    status1, body1 = await execute_request()
    assert status1 == 503
    assert body1["error"]["code"] == "WEBHOOK_PROCESSING_UNAVAILABLE"

    # Step 5: Verify DB state after failure
    async with pg_session_maker() as s:
        c = await s.get(LoginChallenge, challenge_id)
        assert c is not None
        assert c.status == "pending"

        event_count = (
            await s.execute(
                select(func.count(WappiWebhookEvent.id)).where(
                    WappiWebhookEvent.message_id == message_id
                )
            )
        ).scalar()
        assert event_count == 0

    # Step 6: Remove fault injection
    monkeypatch.undo()

    # Step 7 & 8: Second request with identical payload succeeds
    status2, body2 = await execute_request()
    assert status2 == 200
    assert body2["status"] == "ok"
    assert body2["processed"] == 1
    assert body2["duplicates"] == 0

    # Step 9: Verify DB state after retry
    async with pg_session_maker() as s:
        c = await s.get(LoginChallenge, challenge_id)
        assert c is not None
        assert c.status == "confirmed"
        assert c.phone == "+77017770001"

        event = (
            await s.execute(
                select(WappiWebhookEvent).where(
                    WappiWebhookEvent.message_id == message_id
                )
            )
        ).scalar_one_or_none()
        assert event is not None
        assert event.result == "confirmed"

