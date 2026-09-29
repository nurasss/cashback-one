import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_challenge_code
from app.core.time import utcnow
from app.models.entities import LoginChallenge, WappiWebhookEvent


async def _create_test_challenge(
    session: AsyncSession,
    code: str,
    device_id: str = "test-device-uuid-1",
    ttl_seconds: int = 180,
) -> LoginChallenge:
    code_hash = hash_challenge_code(code.strip().upper())
    now = utcnow()
    challenge = LoginChallenge(
        id=uuid.uuid4(),
        code_hash=code_hash,
        device_id=device_id,
        status="pending",
        phone=None,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)
    return challenge



@pytest.mark.asyncio
async def test_wappi_webhook_valid_message_confirms_challenge(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Valid incoming WhatsApp message confirms pending challenge atomically."""
    code = "ABCDEF23"
    challenge = await _create_test_challenge(db_session, code)

    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.HBgLMTEwMDAx",
                "body": code.lower(),  # Verify case-insensitivity
                "type": "chat",
                "from": "77017778899@c.us",
                "to": "77001234567@c.us",
                "chat_type": "dialog",
            }
        ]
    }

    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["processed"] == 1
    assert data["ignored"] == 0
    assert data["duplicates"] == 0
    assert data["details"][0]["result"] == "confirmed"

    # Verify DB challenge state
    await db_session.refresh(challenge)
    assert challenge.status == "confirmed"
    assert challenge.phone == "+77017778899"

    # Verify audit event in DB
    event = (
        await db_session.execute(
            select(WappiWebhookEvent).where(
                WappiWebhookEvent.message_id == "wamid.HBgLMTEwMDAx"
            )
        )
    ).scalar_one_or_none()
    assert event is not None
    assert event.profile_id == settings.wappi_login_profile_id
    assert event.result == "confirmed"
    assert event.wh_type == "incoming_message"


@pytest.mark.asyncio
async def test_wappi_webhook_sequential_duplicate_message_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sequential duplicate message returns duplicate with 0 500 errors."""
    code = "ABCDEF24"
    challenge = await _create_test_challenge(db_session, code)

    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.DUPLICATE_01",
                "body": code,
                "type": "chat",
                "from": "77017778899@c.us",
                "chat_type": "dialog",
            }
        ]
    }
    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}

    # First delivery
    resp1 = await client.post("/webhooks/wappi", headers=headers, json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["processed"] == 1

    # Second duplicate delivery
    resp2 = await client.post("/webhooks/wappi", headers=headers, json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["processed"] == 0
    assert data2["duplicates"] == 1
    assert data2["details"][0]["result"] == "duplicate"

    # Challenge remains confirmed
    await db_session.refresh(challenge)
    assert challenge.status == "confirmed"
    assert challenge.phone == "+77017778899"


@pytest.mark.asyncio
async def test_wappi_webhook_foreign_profile_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Messages from profiles other than wappi_login_profile_id are ignored."""
    code = "ABCDEF25"
    challenge = await _create_test_challenge(db_session, code)

    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": "foreign-profile-999",
                "id": "wamid.FOREIGN_01",
                "body": code,
                "type": "chat",
                "from": "77017778899@c.us",
            }
        ]
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 0
    assert data["ignored"] == 1
    assert data["details"][0]["reason"] == "ignored_profile"

    # Challenge remains pending
    await db_session.refresh(challenge)
    assert challenge.status == "pending"


@pytest.mark.asyncio
async def test_wappi_webhook_non_incoming_event_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Non-incoming_message events (e.g. delivery_status) are ignored."""
    payload = {
        "messages": [
            {
                "wh_type": "delivery_status",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.STATUS_01",
                "body": "ACK",
                "type": "chat",
                "from": "77017778899@c.us",
            }
        ]
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 0
    assert data["ignored"] == 1
    assert data["details"][0]["reason"] == "ignored_event_type"


@pytest.mark.asyncio
async def test_wappi_webhook_non_chat_type_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Non-chat message types (images, voice, reactions) are ignored."""
    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.IMAGE_01",
                "body": "",
                "type": "image",
                "from": "77017778899@c.us",
            }
        ]
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 0
    assert data["ignored"] == 1
    assert data["details"][0]["reason"] == "ignored_non_chat_type"


@pytest.mark.asyncio
async def test_wappi_webhook_group_messages_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Group chats (@g.us or chat_type != dialog) are strictly rejected."""
    # Test 1: @g.us sender
    payload1 = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.GROUP_01",
                "body": "ABCDEF26",
                "type": "chat",
                "from": "1234567890-987654@g.us",
            }
        ]
    }
    resp1 = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload1,
    )
    assert resp1.status_code == 200
    assert resp1.json()["ignored"] == 1
    assert resp1.json()["details"][0]["reason"] == "ignored_group"

    # Test 2: chat_type == "group"
    payload2 = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.GROUP_02",
                "body": "ABCDEF26",
                "type": "chat",
                "from": "77017778899@c.us",
                "chat_type": "group",
            }
        ]
    }
    resp2 = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload2,
    )
    assert resp2.status_code == 200
    assert resp2.json()["ignored"] == 1
    assert resp2.json()["details"][0]["reason"] == "ignored_group"


@pytest.mark.asyncio
async def test_wappi_webhook_invalid_sender_format_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Invalid sender formats (e.g. non-phone or @lid) are ignored."""
    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.LID_01",
                "body": "ABCDEF27",
                "type": "chat",
                "from": "1234567890@lid",
            }
        ]
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["ignored"] == 1
    assert resp.json()["details"][0]["reason"] == "invalid_sender"


@pytest.mark.asyncio
async def test_wappi_webhook_invalid_challenge_code_format_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Invalid code formats (short, long, forbidden characters) are rejected before DB lookups."""
    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.BAD_CODE_01",
                "body": "SHORT",  # Only 5 chars
                "type": "chat",
                "from": "77017778899@c.us",
            },
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.BAD_CODE_02",
                "body": "01IL0000",  # 0, 1, I, L not in alphabet
                "type": "chat",
                "from": "77017778899@c.us",
            },
        ]
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ignored"] == 2
    assert data["details"][0]["reason"] == "invalid_code_format"
    assert data["details"][1]["reason"] == "invalid_code_format"


@pytest.mark.asyncio
async def test_wappi_webhook_unknown_challenge_code_recorded(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Valid format code not matching any challenge is recorded as not_found."""
    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.UNKNOWN_01",
                "body": "23456789",  # Valid alphabet, but does not exist
                "type": "chat",
                "from": "77017778899@c.us",
            }
        ]
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 1
    assert data["details"][0]["result"] == "not_found"


@pytest.mark.asyncio
async def test_wappi_webhook_second_phone_attack_isolated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Second phone attempting to confirm an already confirmed challenge is rejected and isolated."""
    code = "ABCDEF28"
    challenge = await _create_test_challenge(db_session, code)
    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}

    # Legitimate user confirms first
    legit_payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.LEGIT_01",
                "body": code,
                "type": "chat",
                "from": "77017778899@c.us",
            }
        ]
    }
    resp1 = await client.post("/webhooks/wappi", headers=headers, json=legit_payload)
    assert resp1.status_code == 200
    assert resp1.json()["details"][0]["result"] == "confirmed"

    # Attacker tries to confirm same code with another phone number
    attack_payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": "wamid.ATTACK_01",
                "body": code,
                "type": "chat",
                "from": "77029998877@c.us",
            }
        ]
    }
    resp2 = await client.post("/webhooks/wappi", headers=headers, json=attack_payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["details"][0]["result"] == "already_confirmed_other_phone"
    assert data2["details"][0]["is_success"] is False

    # Verify DB: phone was NOT hijacked
    await db_session.refresh(challenge)
    assert challenge.phone == "+77017778899"


@pytest.mark.asyncio
async def test_wappi_webhook_db_failure_returns_503_and_no_leak(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operational DB failure during confirmation returns controlled 503 with zero detail leak."""
    from sqlalchemy.exc import SQLAlchemyError

    code = "ABCDEF29"
    challenge = await _create_test_challenge(db_session, code)
    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}
    msg_id = "wamid.FAIL_LEAK_01"

    async def mock_confirm_fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise SQLAlchemyError(
            "FATAL: relation login_challenges does not exist at "
            "postgresql://secret_user:super_secret_password@db:5432/poscenter_loyalty"
        )

    monkeypatch.setattr(
        "app.services.wappi_webhook.confirm_login_challenge", mock_confirm_fail
    )

    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": msg_id,
                "body": code,
                "type": "chat",
                "from": "77017778899@c.us",
            }
        ]
    }

    resp = await client.post("/webhooks/wappi", headers=headers, json=payload)
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"]["code"] == "WEBHOOK_PROCESSING_UNAVAILABLE"
    assert data["error"]["message"] == "Webhook could not be processed. Retry later."

    # Verify zero leakage of sensitive error internals
    raw_text = resp.text.lower()
    assert "postgresql" not in raw_text
    assert "secret_password" not in raw_text
    assert "login_challenges" not in raw_text
    assert "fatal" not in raw_text

    # Verify rollback: challenge is still pending, no event record saved
    await db_session.refresh(challenge)
    assert challenge.status == "pending"

    event = (
        await db_session.execute(
            select(WappiWebhookEvent).where(WappiWebhookEvent.message_id == msg_id)
        )
    ).scalar_one_or_none()
    assert event is None


@pytest.mark.asyncio
async def test_wappi_webhook_batch_failure_semantics(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Batch failure semantics: first message commits, second rolls back; retry processes remaining."""
    from sqlalchemy.exc import OperationalError

    code1 = "ABCDEF23"
    code2 = "ABCDEF24"
    c1 = await _create_test_challenge(db_session, code1)
    c2 = await _create_test_challenge(db_session, code2)

    headers = {settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret}
    msg_id_1 = "wamid.BATCH_01"
    msg_id_2 = "wamid.BATCH_02"

    payload = {
        "messages": [
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": msg_id_1,
                "body": code1,
                "type": "chat",
                "from": "77017770001@c.us",
            },
            {
                "wh_type": "incoming_message",
                "profile_id": settings.wappi_login_profile_id,
                "id": msg_id_2,
                "body": code2,
                "type": "chat",
                "from": "77017770002@c.us",
            },
        ]
    }

    from app.services.auth_confirmation import confirm_login_challenge as real_confirm

    async def mock_confirm_batch_fail(session, code, sender_phone, commit=True):  # type: ignore[no-untyped-def]
        if code == code2:
            raise OperationalError("statement timeout", {}, Exception())
        return await real_confirm(session, code, sender_phone, commit=commit)

    monkeypatch.setattr(
        "app.services.wappi_webhook.confirm_login_challenge", mock_confirm_batch_fail
    )

    # First attempt: msg 1 succeeds and commits; msg 2 fails and aborts batch request with 503
    resp1 = await client.post("/webhooks/wappi", headers=headers, json=payload)
    assert resp1.status_code == 503

    # Msg 1 is committed
    await db_session.refresh(c1)
    assert c1.status == "confirmed"

    # Msg 2 was rolled back completely
    await db_session.refresh(c2)
    assert c2.status == "pending"

    # Second attempt (provider retry with fault removed):
    monkeypatch.undo()
    resp2 = await client.post("/webhooks/wappi", headers=headers, json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "ok"
    assert data2["processed"] == 1  # msg 2
    assert data2["duplicates"] == 1  # msg 1

    # Both are now confirmed
    await db_session.refresh(c1)
    await db_session.refresh(c2)
    assert c1.status == "confirmed"
    assert c2.status == "confirmed"

