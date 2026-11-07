"""Comprehensive tests for POS /pos/code-push endpoint (2026-11-07).

Covers:
1. Success: push delivered to customer app, RedemptionCode (amount=0) & Notification created, 200 OK.
2. Validation: code != 4 digits (3, 5, letters, whitespace), invalid phone format -> 400 VALIDATION_ERROR.
3. Card resolution:
   - User does not exist -> 404 CARD_NOT_FOUND (no user leak).
   - User soft-deleted -> 404 CARD_NOT_FOUND.
   - User has card in other business only -> 404 CARD_NOT_FOUND.
   - User has multiple cards (one blocked, one active) -> picks active card.
   - User has only blocked cards -> 409 CARD_BLOCKED.
4. App/device check:
   - No devices -> 409 CUSTOMER_NO_APP.
   - All devices disabled -> 409 CUSTOMER_NO_APP.
5. Rate limit: 5 requests allowed in 10 minutes, 6th -> 429 RATE_LIMIT_EXCEEDED.
6. Push service unavailable: push disabled -> 503 PUSH_NOT_CONFIGURED.
7. Delivery failed (0 deliveries / exception) -> 503 PUSH_DELIVERY_FAILED with rollback.
8. Privacy / caplog: phone and code are NOT logged anywhere in logs.
9. Notification lifecycle:
   - Code hidden after 5 minutes (no code and no "0 баллов").
   - Subsequent code request supersedes previous pending code (neutral text without code and without "0 баллов").
10. Authentication:
    - Missing X-Pos-Key -> 401 POS_KEY_MISSING.
    - Invalid X-Pos-Key -> 401 POS_KEY_INVALID.
"""
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    RedemptionCode,
    User,
    UserCard,
)
from app.services.pos_auth import issue_pos_key
from app.services.push_sender import FakePushSender, PushResult, PushStatus, get_push_sender
from app.services.rate_limiter import _test_limiter, get_rate_limiter
from app.services.redemption_service import _hash_code


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


async def _customer_auth(session: AsyncSession, user: User) -> dict[str, str]:
    auth_session = AuthSession(
        user_id=user.id,
        device_id="test-device-app",
        refresh_token_hash=hash_refresh_token(f"refresh-{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    session.add(auth_session)
    await session.commit()
    token = create_access_token(user_id=user.id, session_id=auth_session.id)
    return {"Authorization": f"Bearer {token}"}


async def setup_code_push_env(
    db: AsyncSession,
    *,
    phone: str = "+77011234567",
    has_owner: bool = True,
    has_device: bool = True,
    device_disabled: bool = False,
    card_blocked: bool = False,
    business_name: str = "Супермаркет Керемет",
) -> tuple[Business, str, Card, User | None, Device | None]:
    business = Business(name=business_name)
    db.add(business)
    await db.flush()

    _, raw_key = await issue_pos_key(db, business.id, "Касса 1")

    card = Card(
        business_id=business.id,
        barcode=f"1000{uuid.uuid4().int % 10000000:07d}",
        balance=Decimal("5000.0000"),
        is_blocked=card_blocked,
    )
    db.add(card)
    await db.flush()

    user = None
    device = None
    if has_owner:
        user = User(phone=phone)
        db.add(user)
        await db.flush()

        user_card = UserCard(user_id=user.id, card_id=card.id)
        db.add(user_card)
        await db.flush()

        if has_device:
            device = Device(
                user_id=user.id,
                push_token=f"test-push-token-{uuid.uuid4()}",
                platform="android",
                disabled_at=utcnow() if device_disabled else None,
            )
            db.add(device)
            await db.flush()

    await db.commit()
    return business, raw_key, card, user, device


# =========================================================================
# 1. Success scenarios
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_success(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    biz, raw_key, card, user, _ = await setup_code_push_env(db_session, phone="+77011234567")
    assert user is not None

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "4554"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "sent"
    assert "expires_at" in data
    assert "phone" not in data
    assert "code" not in data

    # Check push delivered
    assert len(fake_push_sender.sent_messages) == 1
    push_msg = fake_push_sender.sent_messages[0]
    assert push_msg.title == "Код для списания бонусов"
    assert "4554" in push_msg.body
    assert f"«{biz.name}»" in push_msg.body
    assert push_msg.data["type"] == "redemption_code"
    redemption_id = uuid.UUID(push_msg.data["redemption_id"])

    # Check RedemptionCode in DB: amount must be 0
    record = await db_session.get(RedemptionCode, redemption_id)
    assert record is not None
    assert record.business_id == biz.id
    assert record.card_id == card.id
    assert record.amount == Decimal("0.0000")
    assert record.status == "pending"
    assert record.code_hash == _hash_code(record.id, "4554")

    # Check Notification in DB
    notif = await db_session.scalar(
        select(Notification).where(Notification.redemption_id == redemption_id)
    )
    assert notif is not None
    assert notif.user_id == user.id
    assert notif.business_id == biz.id
    assert notif.title == "Код для списания бонусов"
    assert "4554" in notif.body
    assert f"«{biz.name}»" in notif.body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phone_input",
    [
        "77011234567",
        "+77011234567",
        "87011234567",
        "8 (701) 123-45-67",
    ],
)
async def test_pos_code_push_phone_normalization(
    db_session: AsyncSession,
    pos_client: AsyncClient,
    phone_input: str,
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(db_session, phone="+77011234567")

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": phone_input, "code": "9876"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "sent"


# =========================================================================
# 2. Validation errors (400)
# =========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_code",
    [
        "123",        # 3 digits
        "12345",      # 5 digits
        "abcd",       # letters
        "12a4",       # mixed
        " 1234",      # leading space
        "1234 ",      # trailing space
        "",           # empty
    ],
)
async def test_pos_code_push_invalid_code(
    db_session: AsyncSession, pos_client: AsyncClient, bad_code: str
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(db_session)

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": bad_code},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_phone",
    [
        "invalid",
        "123",
        "+123",
        "",
        "not_a_phone",
    ],
)
async def test_pos_code_push_invalid_phone(
    db_session: AsyncSession, pos_client: AsyncClient, bad_phone: str
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(db_session)

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": bad_phone, "code": "1234"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


# =========================================================================
# 3. Card & customer resolution (404, 409)
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_user_not_found(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(db_session, phone="+77011234567")

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77099999999", "code": "1234"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_pos_code_push_user_soft_deleted(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, raw_key, _, user, _ = await setup_code_push_env(db_session, phone="+77011234567")
    assert user is not None
    user.deleted_at = utcnow()
    await db_session.commit()

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_pos_code_push_user_has_card_in_different_business_only(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    # Set up user in business A
    _, _raw_key_a, _, user, _ = await setup_code_push_env(db_session, phone="+77011234567")
    assert user is not None

    # Set up cash register in business B
    biz_b = Business(name="Другой Магазин")
    db_session.add(biz_b)
    await db_session.flush()
    _, raw_key_b = await issue_pos_key(db_session, biz_b.id, "Касса Б")
    await db_session.commit()

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key_b},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_pos_code_push_multiple_cards_picks_unblocked(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    biz, raw_key, _card1, user, _ = await setup_code_push_env(
        db_session, phone="+77011234567", card_blocked=True
    )
    assert user is not None

    # Add a second, unblocked card for the same user in the same business
    card2 = Card(
        business_id=biz.id,
        barcode=f"1000{uuid.uuid4().int % 10000000:07d}",
        balance=Decimal("2000.0000"),
        is_blocked=False,
    )
    db_session.add(card2)
    await db_session.flush()

    user_card2 = UserCard(user_id=user.id, card_id=card2.id)
    db_session.add(user_card2)
    await db_session.commit()

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "sent"

    # Verify redemption was created on the active card
    code_record = await db_session.scalar(
        select(RedemptionCode).where(RedemptionCode.card_id == card2.id)
    )
    assert code_record is not None


@pytest.mark.asyncio
async def test_pos_code_push_all_cards_blocked(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(
        db_session, phone="+77011234567", card_blocked=True
    )

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CARD_BLOCKED"


# =========================================================================
# 4. Device checks (CUSTOMER_NO_APP)
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_customer_no_app_no_device(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(
        db_session, phone="+77011234567", has_device=False
    )

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CUSTOMER_NO_APP"


@pytest.mark.asyncio
async def test_pos_code_push_customer_no_app_all_devices_disabled(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(
        db_session, phone="+77011234567", has_device=True, device_disabled=True
    )

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CUSTOMER_NO_APP"


# =========================================================================
# 5. Rate limiting (429)
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_rate_limit(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _, raw_key, _, _, _ = await setup_code_push_env(db_session, phone="+77011234567")

    for _ in range(5):
        r = await pos_client.post(
            "/pos/code-push",
            headers={"X-Pos-Key": raw_key},
            json={"phone": "77011234567", "code": "1111"},
        )
        assert r.status_code == 200

    r6 = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1111"},
    )
    assert r6.status_code == 429
    assert r6.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


# =========================================================================
# 6. Push disabled and delivery failure (503)
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_push_not_configured(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    fake_push_sender.disabled = True
    _, raw_key, _, _, _ = await setup_code_push_env(db_session, phone="+77011234567")

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "PUSH_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_pos_code_push_delivery_failed_rolls_back(
    db_session: AsyncSession, pos_client: AsyncClient, fake_push_sender: FakePushSender
) -> None:
    fake_push_sender.next_result = PushResult(
        status=PushStatus.INVALID_TOKEN, error_details="UNREGISTERED"
    )
    _, raw_key, _, _, _ = await setup_code_push_env(db_session, phone="+77011234567")

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "PUSH_DELIVERY_FAILED"

    # Rollback verified: no records created
    codes = (await db_session.scalars(select(RedemptionCode))).all()
    assert len(codes) == 0


# =========================================================================
# 7. Notification lifecycle (expired after 5 mins, superseded)
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_notification_hidden_after_5_minutes(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _biz, raw_key, _, user, _ = await setup_code_push_env(
        db_session, phone="+77011234567", business_name="Магазин Керемет"
    )
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "7890"},
    )
    assert res.status_code == 200

    # 1. Immediately: notification shows code in /me/notifications
    me_res1 = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res1.status_code == 200
    items1 = me_res1.json()["items"]
    assert len(items1) == 1
    assert "7890" in items1[0]["body"]

    # 2. Simulate 5 minutes pass: expire the RedemptionCode
    redemption = await db_session.scalar(select(RedemptionCode))
    assert redemption is not None
    redemption.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()

    # 3. Query /me/notifications: text must NOT have code and NOT have "0" / "0 баллов"
    me_res2 = await pos_client.get("/me/notifications", headers=user_headers)
    assert me_res2.status_code == 200
    items2 = me_res2.json()["items"]
    assert len(items2) == 1
    body = items2[0]["body"]
    assert "7890" not in body
    assert "0" not in body
    assert "0 баллов" not in body
    assert "Код для списания в «Магазин Керемет» больше не действует." == body


@pytest.mark.asyncio
async def test_pos_code_push_superseded_by_subsequent_request(
    db_session: AsyncSession, pos_client: AsyncClient
) -> None:
    _biz, raw_key, _, user, _ = await setup_code_push_env(
        db_session, phone="+77011234567", business_name="Магазин Керемет"
    )
    assert user is not None
    user_headers = await _customer_auth(db_session, user)

    # 1. Request #1
    res1 = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "1111"},
    )
    assert res1.status_code == 200

    # 2. Request #2 supersedes #1
    res2 = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": raw_key},
        json={"phone": "77011234567", "code": "2222"},
    )
    assert res2.status_code == 200

    # In DB: previous notification body is updated to inactive text without "0"
    notifications = (
        await db_session.execute(
            select(Notification).order_by(Notification.created_at.asc())
        )
    ).scalars().all()
    assert len(notifications) == 2
    notif1, notif2 = notifications[0], notifications[1]

    assert notif1.body == "Код для списания в «Магазин Керемет» больше не действует."
    assert "1111" not in notif1.body
    assert "0" not in notif1.body

    assert "2222" in notif2.body

    # In /me/notifications: notif1 has inactive text, notif2 has code
    me_res = await pos_client.get("/me/notifications", headers=user_headers)
    items = me_res.json()["items"]
    assert len(items) == 2
    # items are ordered desc
    assert "2222" in items[0]["body"]
    assert items[1]["body"] == "Код для списания в «Магазин Керемет» больше не действует."


# =========================================================================
# 8. Privacy: no phone and no code in logs (caplog)
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_privacy_no_phone_or_code_in_logs(
    db_session: AsyncSession,
    pos_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    test_phone = "77019998877"
    test_code = "6543"

    _, raw_key, _, _, _ = await setup_code_push_env(db_session, phone=f"+{test_phone}")
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        res = await pos_client.post(
            "/pos/code-push",
            headers={"X-Pos-Key": raw_key},
            json={"phone": test_phone, "code": test_code},
        )
        assert res.status_code == 200

        # Also test error path
        res_err = await pos_client.post(
            "/pos/code-push",
            headers={"X-Pos-Key": raw_key},
            json={"phone": "77098765432", "code": "4321"},
        )
        assert res_err.status_code == 404

    # Assert neither sensitive phone nor sensitive code was leaked in application logs
    app_logs = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("app"))
    assert test_phone not in app_logs
    assert test_code not in app_logs
    assert "77098765432" not in app_logs
    assert "4321" not in app_logs


# =========================================================================
# 9. Authentication
# =========================================================================

@pytest.mark.asyncio
async def test_pos_code_push_auth_missing_key(pos_client: AsyncClient) -> None:
    res = await pos_client.post(
        "/pos/code-push",
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "POS_KEY_MISSING"


@pytest.mark.asyncio
async def test_pos_code_push_auth_invalid_key(pos_client: AsyncClient) -> None:
    res = await pos_client.post(
        "/pos/code-push",
        headers={"X-Pos-Key": "pos_invalid_key_12345678901234567890"},
        json={"phone": "77011234567", "code": "1234"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "POS_KEY_INVALID"
