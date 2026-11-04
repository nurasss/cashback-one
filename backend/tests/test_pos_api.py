"""Comprehensive tests for POS cash register API endpoints (Task B, 2026-11-04).

Covers:
1. Header authentication (missing, invalid, revoked, throttling last_used_at, tenant scoping).
2. Request redemption (/pos/redemptions):
   - Success (push sent via FakePushSender, Notification created, 4-digit code, no code in data, 201 response).
   - CUSTOMER_NO_APP (unbound card, no devices, all devices disabled).
   - CARD_NOT_FOUND, CARD_BLOCKED.
   - Rate limit (429).
   - PUSH_DELIVERY_FAILED with rollback (503).
   - Amount as string and number, validation errors.
3. Verify redemption (/pos/redemptions/{id}/verify):
   - Success (200, amount as string "150.5000").
   - INVALID_CODE (400).
   - 5 attempts -> REDEMPTION_MAX_ATTEMPTS_EXCEEDED (409).
   - REDEMPTION_EXPIRED (409).
   - REDEMPTION_ALREADY_CONFIRMED (409).
   - REDEMPTION_NOT_ACTIVE (superseded) (409).
   - REDEMPTION_NOT_FOUND (wrong tenant/id) (404).
"""
import re
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.entities import (
    AuthSession,
    Business,
    Card,
    Device,
    Notification,
    PosKey,
    RedemptionCode,
    User,
    UserCard,
)
from app.services.pos_auth import issue_pos_key
from app.services.push_sender import FakePushSender, PushResult, PushStatus, get_push_sender
from app.services.rate_limiter import _test_limiter, get_rate_limiter


@pytest.fixture
def fake_push_sender() -> FakePushSender:
    return FakePushSender()


@pytest.fixture
async def pos_client(db_session: AsyncSession, fake_push_sender: FakePushSender):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    app.dependency_overrides[get_push_sender] = lambda: fake_push_sender  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def setup_pos_env(
    db: AsyncSession,
    *,
    has_owner: bool = True,
    has_active_device: bool = True,
    device_disabled: bool = False,
    card_blocked: bool = False,
    barcode: str = "777000111222",
    business_name: str = "Супермаркет Керемет",
) -> tuple[Business, PosKey, str, Card, User | None, Device | None]:
    business = Business(name=business_name)
    db.add(business)
    await db.flush()

    pos_key, raw_key = await issue_pos_key(db, business.id, "Касса 1")

    card = Card(
        business_id=business.id,
        barcode=barcode,
        balance=Decimal("10000.0000"),
        is_blocked=card_blocked,
    )
    db.add(card)
    await db.flush()

    user = None
    device = None
    if has_owner:
        user = User(phone=f"+770{uuid.uuid4().int % 100000000:08d}")
        db.add(user)
        await db.flush()

        user_card = UserCard(user_id=user.id, card_id=card.id)
        db.add(user_card)
        await db.flush()

        if has_active_device:
            device = Device(
                user_id=user.id,
                push_token=f"test-push-token-{uuid.uuid4()}",
                platform="android",
                disabled_at=utcnow() if device_disabled else None,
            )
            db.add(device)
            await db.flush()

    await db.commit()
    return business, pos_key, raw_key, card, user, device


# =========================================================================
# 1. POS Authentication tests
# =========================================================================

@pytest.mark.asyncio
async def test_pos_auth_missing_header(pos_client: AsyncClient) -> None:
    res = await pos_client.post("/pos/redemptions", json={"barcode": "12345", "amount": "100"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "POS_KEY_MISSING"


@pytest.mark.asyncio
async def test_pos_auth_invalid_key(pos_client: AsyncClient) -> None:
    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": "pos_invalid_key_12345678901234567890"},
        json={"barcode": "12345", "amount": "100"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "POS_KEY_INVALID"


@pytest.mark.asyncio
async def test_pos_auth_revoked_key(db_session: AsyncSession, pos_client: AsyncClient) -> None:
    _, pos_key, raw_key, card, _, _ = await setup_pos_env(db_session)
    pos_key.revoked_at = utcnow()
    await db_session.commit()

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "POS_KEY_REVOKED"


@pytest.mark.asyncio
async def test_pos_auth_updates_last_used_at_throttled(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, pos_key, raw_key, card, _, _ = await setup_pos_env(db_session)
    assert pos_key.last_used_at is None

    # First request sets last_used_at
    res1 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res1.status_code == 201
    await db_session.refresh(pos_key)
    first_used_at = pos_key.last_used_at
    assert first_used_at is not None

    # Immediate second request does NOT update last_used_at (within 60s)
    res2 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "50"},
    )
    assert res2.status_code == 201
    await db_session.refresh(pos_key)
    assert pos_key.last_used_at == first_used_at


# =========================================================================
# 2. Request Redemption (/pos/redemptions) tests
# =========================================================================

@pytest.mark.asyncio
async def test_pos_redemption_success_push_and_notification(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    biz, _pos_key, raw_key, card, user, device = await setup_pos_env(
        db_session, barcode="1234567890", business_name="Магазин Керемет"
    )
    assert user is not None
    assert device is not None

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "150.5"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert "redemption_id" in data
    assert "expires_at" in data
    assert "recipient" not in data  # Phone must NOT be returned!
    assert "phone" not in data

    redemption_id = uuid.UUID(data["redemption_id"])
    rec = await db_session.get_one(RedemptionCode, redemption_id)
    assert rec.status == "pending"
    assert rec.amount == Decimal("150.5000")

    # Verify push notification sent via FakePushSender
    assert len(fake_push_sender.sent_messages) == 1
    msg = fake_push_sender.sent_messages[0]
    assert msg.token == device.push_token
    assert msg.title == "Код для списания баллов"
    assert "Магазин Керемет" in msg.body
    assert "150,5" in msg.body or "150.5" in msg.body

    # Extract 4-digit code from push body
    match = re.search(r"\b(\d{4})\b", msg.body)
    assert match is not None
    code = match.group(1)

    # Verify push data contains NO code
    assert msg.data is not None
    assert msg.data["type"] == "redemption_code"
    assert msg.data["redemption_id"] == str(redemption_id)
    assert "code" not in msg.data
    assert code not in str(msg.data)

    # Verify in-app Notification record created in DB
    notifications = (
        await db_session.scalars(
            select(Notification).where(Notification.user_id == user.id)
        )
    ).all()
    assert len(notifications) == 1
    notif = notifications[0]
    assert notif.business_id == biz.id
    assert notif.title == "Код для списания баллов"
    assert notif.body == msg.body


@pytest.mark.asyncio
async def test_pos_redemption_amount_number_and_string(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    # string "500"
    r1 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "500"},
    )
    assert r1.status_code == 201

    # number 250.75
    r2 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": 250.75},
    )
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_pos_redemption_customer_no_app_unbound_card(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session, has_owner=False)

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CUSTOMER_NO_APP"

    # Ensure no redemption code created in DB
    count = (await db_session.scalars(select(RedemptionCode))).all()
    assert len(count) == 0


@pytest.mark.asyncio
async def test_pos_redemption_customer_no_app_no_devices(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session, has_owner=True, has_active_device=False)

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CUSTOMER_NO_APP"


@pytest.mark.asyncio
async def test_pos_redemption_customer_no_app_all_devices_disabled(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(
        db_session, has_owner=True, has_active_device=True, device_disabled=True
    )

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CUSTOMER_NO_APP"


@pytest.mark.asyncio
async def test_pos_redemption_card_not_found(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, _, _, _ = await setup_pos_env(db_session)

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": "999999999999", "amount": "100"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_pos_redemption_card_blocked(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session, card_blocked=True)

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CARD_BLOCKED"


@pytest.mark.asyncio
async def test_pos_redemption_rate_limit(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    # Limit is 5 requests per window
    for _ in range(5):
        r = await pos_client.post(
            "/pos/redemptions",
            headers={"X-Pos-Key": raw_key},
            json={"barcode": card.barcode, "amount": "10"},
        )
        assert r.status_code == 201

    # 6th request is rate limited
    r6 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "10"},
    )
    assert r6.status_code == 429
    assert r6.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_pos_redemption_push_delivery_failed_rolls_back(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    # Set simulated response to INVALID_TOKEN so 0 devices are delivered
    fake_push_sender.next_result = PushResult(status=PushStatus.INVALID_TOKEN, error_details="UNREGISTERED")
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "100"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "PUSH_DELIVERY_FAILED"

    # Verify rollback: no redemption code in DB
    codes = (await db_session.scalars(select(RedemptionCode))).all()
    assert len(codes) == 0


@pytest.mark.asyncio
async def test_pos_redemption_validation_errors(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    # Barcode too short (< 4 digits)
    r1 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": "123", "amount": "10"},
    )
    assert r1.status_code == 422

    # Amount <= 0
    r2 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "0"},
    )
    assert r2.status_code == 422

    # Amount negative
    r3 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "-10"},
    )
    assert r3.status_code == 422


# =========================================================================
# 3. Verify Redemption (/pos/redemptions/{id}/verify) tests
# =========================================================================

@pytest.mark.asyncio
async def test_pos_verify_redemption_lifecycle(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session, barcode="1234567890")

    # Request code
    req_res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "150.50"},
    )
    assert req_res.status_code == 201
    rid = req_res.json()["redemption_id"]

    code = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # 1. Invalid code (400)
    wrong_code = "0000" if code != "0000" else "1111"
    wrong_res = await pos_client.post(
        f"/pos/redemptions/{rid}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": wrong_code},
    )
    assert wrong_res.status_code == 400
    assert wrong_res.json()["error"]["code"] == "INVALID_CODE"

    # 2. Correct code (200)
    ok_res = await pos_client.post(
        f"/pos/redemptions/{rid}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code},
    )
    assert ok_res.status_code == 200
    data = ok_res.json()
    assert data["status"] == "confirmed"
    assert data["barcode"] == card.barcode
    assert data["amount"] == "150.5000"  # Serialized string per contract

    # 3. Repeat verify (409 REDEMPTION_ALREADY_CONFIRMED)
    again_res = await pos_client.post(
        f"/pos/redemptions/{rid}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code},
    )
    assert again_res.status_code == 409
    assert again_res.json()["error"]["code"] == "REDEMPTION_ALREADY_CONFIRMED"


@pytest.mark.asyncio
async def test_pos_verify_max_attempts_exceeded(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "redemption_code_max_attempts", 3)
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    req_res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "50"},
    )
    rid = req_res.json()["redemption_id"]

    code = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]
    wrong_code = "0000" if code != "0000" else "1111"

    # Attempts 1 and 2: INVALID_CODE (400)
    for _ in range(2):
        r = await pos_client.post(
            f"/pos/redemptions/{rid}/verify",
            headers={"X-Pos-Key": raw_key},
            json={"code": wrong_code},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_CODE"

    # Attempt 3: REDEMPTION_MAX_ATTEMPTS_EXCEEDED (409)
    r3 = await pos_client.post(
        f"/pos/redemptions/{rid}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": wrong_code},
    )
    assert r3.status_code == 409
    assert r3.json()["error"]["code"] == "REDEMPTION_MAX_ATTEMPTS_EXCEEDED"

    # Subsequent attempt even with correct code is NOT_ACTIVE (exhausted)
    r4 = await pos_client.post(
        f"/pos/redemptions/{rid}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code},
    )
    assert r4.status_code == 409
    assert r4.json()["error"]["code"] == "REDEMPTION_NOT_ACTIVE"


@pytest.mark.asyncio
async def test_pos_verify_code_expired(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    req_res = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "50"},
    )
    rid = req_res.json()["redemption_id"]
    code = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # Expire the code manually
    rec = await db_session.get_one(RedemptionCode, uuid.UUID(rid))
    rec.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()

    ver_res = await pos_client.post(
        f"/pos/redemptions/{rid}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code},
    )
    assert ver_res.status_code == 409
    assert ver_res.json()["error"]["code"] == "REDEMPTION_EXPIRED"


@pytest.mark.asyncio
async def test_pos_verify_superseded_after_new_request(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    _, _, raw_key, card, _, _ = await setup_pos_env(db_session)

    # First request
    r1 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "50"},
    )
    rid1 = r1.json()["redemption_id"]
    code1 = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # Second request supersedes the first
    r2 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "60"},
    )
    rid2 = r2.json()["redemption_id"]
    code2 = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # Verify first code -> REDEMPTION_NOT_ACTIVE (409)
    v1 = await pos_client.post(
        f"/pos/redemptions/{rid1}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code1},
    )
    assert v1.status_code == 409
    assert v1.json()["error"]["code"] == "REDEMPTION_NOT_ACTIVE"

    # Verify second code -> 200 OK
    v2 = await pos_client.post(
        f"/pos/redemptions/{rid2}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code2},
    )
    assert v2.status_code == 200
    assert v2.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_pos_cross_tenant_isolation(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    # Business A
    _, _, raw_key_a, _card_a, _, _ = await setup_pos_env(
        db_session, barcode="1111111111", business_name="Бизнес А"
    )
    # Business B
    _, _, raw_key_b, card_b, _, _ = await setup_pos_env(
        db_session, barcode="2222222222", business_name="Бизнес Б"
    )

    # Key A cannot request code for Card B
    r_foreign = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key_a},
        json={"barcode": card_b.barcode, "amount": "100"},
    )
    assert r_foreign.status_code == 404
    assert r_foreign.json()["error"]["code"] == "CARD_NOT_FOUND"

    # Request code for Card B using Key B
    r_b = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key_b},
        json={"barcode": card_b.barcode, "amount": "100"},
    )
    assert r_b.status_code == 201
    rid_b = r_b.json()["redemption_id"]
    code_b = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # Key A cannot verify redemption of Business B -> 404 REDEMPTION_NOT_FOUND
    v_cross = await pos_client.post(
        f"/pos/redemptions/{rid_b}/verify",
        headers={"X-Pos-Key": raw_key_a},
        json={"code": code_b},
    )
    assert v_cross.status_code == 404
    assert v_cross.json()["error"]["code"] == "REDEMPTION_NOT_FOUND"


async def _customer_auth(db: AsyncSession, user: User) -> dict[str, str]:
    auth = AuthSession(
        user_id=user.id,
        device_id="test-device-app",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(auth)
    await db.commit()
    token = create_access_token(user_id=user.id, session_id=auth.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_notification_linked_and_cleared_on_confirm(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    business, _, raw_key, card, user, _ = await setup_pos_env(
        db_session, business_name="Супермаркет Керемет"
    )
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    # 1. Request redemption
    r = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "150.00"},
    )
    assert r.status_code == 201
    redemption_id = uuid.UUID(r.json()["redemption_id"])
    code = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # Verify notification in DB is linked via redemption_id
    notif = await db_session.scalar(
        select(Notification).where(Notification.redemption_id == redemption_id)
    )
    assert notif is not None
    assert code in notif.body

    # Check /me/notifications before verify: code is visible while pending
    me_res = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res.status_code == 200
    items = me_res.json()["items"]
    assert len(items) == 1
    assert code in items[0]["body"]

    # 2. Confirm redemption
    v = await pos_client.post(
        f"/pos/redemptions/{redemption_id}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": code},
    )
    assert v.status_code == 200

    # In DB: code is gone, text is neutral
    await db_session.refresh(notif)
    expected_confirmed = "Списание 150 баллов в «Супермаркет Керемет» подтверждено на кассе."
    assert notif.body == expected_confirmed
    assert code not in notif.body

    # In /me/notifications: text is neutral
    me_res_after = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res_after.status_code == 200
    items_after = me_res_after.json()["items"]
    assert items_after[0]["body"] == expected_confirmed
    assert code not in items_after[0]["body"]


@pytest.mark.asyncio
async def test_notification_cleared_on_exhausted_attempts(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    business, _, raw_key, card, user, _ = await setup_pos_env(
        db_session, business_name="Супермаркет Керемет"
    )
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    r = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "150.00"},
    )
    redemption_id = uuid.UUID(r.json()["redemption_id"])
    code = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    notif = await db_session.scalar(
        select(Notification).where(Notification.redemption_id == redemption_id)
    )
    assert notif is not None

    wrong_code = "9999" if code != "9999" else "8888"
    for _ in range(4):
        v = await pos_client.post(
            f"/pos/redemptions/{redemption_id}/verify",
            headers={"X-Pos-Key": raw_key},
            json={"code": wrong_code},
        )
        assert v.status_code == 400

    v5 = await pos_client.post(
        f"/pos/redemptions/{redemption_id}/verify",
        headers={"X-Pos-Key": raw_key},
        json={"code": wrong_code},
    )
    assert v5.status_code == 409
    assert v5.json()["error"]["code"] == "REDEMPTION_MAX_ATTEMPTS_EXCEEDED"

    expected_inactive = "Код для списания 150 баллов в «Супермаркет Керемет» больше не действует."
    await db_session.refresh(notif)
    assert notif.body == expected_inactive
    assert code not in notif.body

    me_res = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res.status_code == 200
    assert me_res.json()["items"][0]["body"] == expected_inactive


@pytest.mark.asyncio
async def test_notification_cleared_when_superseded_by_new_request(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    business, _, raw_key, card, user, _ = await setup_pos_env(
        db_session, business_name="Супермаркет Керемет"
    )
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    # 1. Request #1
    r1 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "150.00"},
    )
    assert r1.status_code == 201
    rid1 = uuid.UUID(r1.json()["redemption_id"])
    code1 = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    notif1 = await db_session.scalar(
        select(Notification).where(Notification.redemption_id == rid1)
    )
    assert notif1 is not None
    assert code1 in notif1.body

    # 2. Request #2 supersedes #1
    r2 = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "200.00"},
    )
    assert r2.status_code == 201
    rid2 = uuid.UUID(r2.json()["redemption_id"])
    code2 = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # In DB: notif1 has neutral inactive text
    await db_session.refresh(notif1)
    expected_inactive_1 = "Код для списания 150 баллов в «Супермаркет Керемет» больше не действует."
    assert notif1.body == expected_inactive_1
    assert code1 not in notif1.body

    # notif2 in DB still has code2
    notif2 = await db_session.scalar(
        select(Notification).where(Notification.redemption_id == rid2)
    )
    assert notif2 is not None
    assert code2 in notif2.body

    # In /me/notifications: notif1 is neutral, notif2 has code2
    me_res = await pos_client.get("/me/notifications", headers=user_headers)
    items = me_res.json()["items"]
    assert len(items) == 2
    # items are ordered by created_at desc (newest first)
    assert items[0]["id"] == str(notif2.id)
    assert code2 in items[0]["body"]

    assert items[1]["id"] == str(notif1.id)
    assert items[1]["body"] == expected_inactive_1
    assert code1 not in items[1]["body"]


@pytest.mark.asyncio
async def test_notification_passive_expiry_without_pos_request(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    business, _, raw_key, card, user, _ = await setup_pos_env(
        db_session, business_name="Супермаркет Керемет"
    )
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    r = await pos_client.post(
        "/pos/redemptions",
        headers={"X-Pos-Key": raw_key},
        json={"barcode": card.barcode, "amount": "150.00"},
    )
    rid = uuid.UUID(r.json()["redemption_id"])
    code = re.search(r"\b(\d{4})\b", fake_push_sender.sent_messages[-1].body).group(1)  # type: ignore[union-attr]

    # Manually expire the code in DB (no POS verify called)
    record = await db_session.get_one(RedemptionCode, rid)
    record.expires_at = utcnow() - timedelta(minutes=5)
    await db_session.commit()

    # DB still has status == "pending" and the raw code in notif.body
    notif = await db_session.scalar(
        select(Notification).where(Notification.redemption_id == rid)
    )
    assert notif is not None
    assert record.status == "pending"
    assert code in notif.body

    # /me/notifications dynamically hides code and returns neutral inactive text
    me_res = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res.status_code == 200
    items = me_res.json()["items"]
    expected_inactive = "Код для списания 150 баллов в «Супермаркет Керемет» больше не действует."
    assert items[0]["body"] == expected_inactive
    assert code not in items[0]["body"]


@pytest.mark.asyncio
async def test_ordinary_notifications_without_redemption_id_unaffected(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    business, _, _, card, user, _ = await setup_pos_env(db_session)
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    # Add standard notification without redemption_id
    notif = Notification(
        id=uuid.uuid4(),
        business_id=business.id,
        user_id=user.id,
        kind="promo",
        title="Специальная скидка",
        body="Скидка 20% на все сыры до конца недели!",
        created_at=utcnow(),
    )
    db_session.add(notif)
    await db_session.commit()

    me_res = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res.status_code == 200
    items = me_res.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Специальная скидка"
    assert items[0]["body"] == "Скидка 20% на все сыры до конца недели!"
