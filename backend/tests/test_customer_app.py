"""Customer app features: WhatsApp OTP login, profile, levels, content, dynamic QR, POS codes."""
import re
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_refresh_token
from app.core.time import as_utc, utcnow
from app.models.entities import (
    AuthSession,
    Business,
    Card,
    Notification,
    Promotion,
    RedemptionCode,
    User,
    UserCard,
)
from app.schemas.customer_app import iin_is_valid
from app.services.agent_auth import issue_agent_key
from app.services.qr_tokens import issue_card_token, verify_card_token
from app.services.whatsapp_sender import get_fake_whatsapp_sender


@pytest.fixture(autouse=True)
def fake_whatsapp(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "whatsapp_provider_mode", "fake")
    sender = get_fake_whatsapp_sender()
    sender.clear()
    yield sender
    sender.clear()


async def customer(db: AsyncSession, phone: str = "+77015550101") -> tuple[User, dict[str, str]]:
    user = User(phone=phone, language="ru", created_at=utcnow() - timedelta(days=1))
    db.add(user)
    await db.flush()
    auth = AuthSession(
        user_id=user.id,
        device_id="dev-app",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=14),
    )
    db.add(auth)
    await db.commit()
    token = create_access_token(user_id=user.id, session_id=auth.id)
    return user, {"Authorization": f"Bearer {token}"}


async def business_with_card(
    db: AsyncSession, user: User | None, name: str = "Shop", barcode: str = "0123456789001", **card: object
) -> tuple[Business, Card]:
    biz = Business(name=name, status="active")
    db.add(biz)
    await db.flush()
    row = Card(business_id=biz.id, barcode=barcode, phone=user.phone if user else None,
               balance=Decimal(100), **card)
    db.add(row)
    await db.flush()
    if user is not None:
        db.add(UserCard(user_id=user.id, card_id=row.id, bind_method="phone_auto"))
    await db.commit()
    return biz, row


# --- WhatsApp OTP login -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_whatsapp_login_sends_code_and_issues_14_day_session(
    client: AsyncClient, db_session: AsyncSession, fake_whatsapp
) -> None:
    phone, device = "+77017770011", "dev-wa-1"
    res = await client.post("/auth/whatsapp/request", json={"phone": "8 701 777 00 11", "device_id": device})
    assert res.status_code == 200
    assert res.json()["status"] == "sent"
    [(recipient, text)] = fake_whatsapp.sent_messages
    assert recipient == phone
    code = re.search(r"\b(\d{6})\b", text).group(1)  # type: ignore[union-attr]

    res = await client.post("/auth/whatsapp/verify", json={"phone": phone, "device_id": device, "code": code})
    assert res.status_code == 200
    assert res.json()["access_token"] and res.json()["refresh_token"]

    auth = await db_session.scalar(select(AuthSession))
    assert auth is not None
    lifetime = as_utc(auth.expires_at) - as_utc(auth.created_at)
    assert timedelta(days=14) - timedelta(minutes=1) < lifetime <= timedelta(days=14)


@pytest.mark.asyncio
async def test_whatsapp_login_wrong_code_and_disabled_provider(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, fake_whatsapp
) -> None:
    await client.post("/auth/whatsapp/request", json={"phone": "+77017770022", "device_id": "dev-wa-2"})
    code = re.search(r"\b(\d{6})\b", fake_whatsapp.sent_messages[0][1]).group(1)  # type: ignore[union-attr]
    wrong = "000000" if code != "000000" else "111111"
    res = await client.post("/auth/whatsapp/verify", json={"phone": "+77017770022", "device_id": "dev-wa-2", "code": wrong})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_CODE"

    monkeypatch.setattr(settings, "whatsapp_provider_mode", "disabled")
    res = await client.post("/auth/whatsapp/request", json={"phone": "+77017770033", "device_id": "dev-wa-3"})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "WHATSAPP_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_whatsapp_delivery_failure_leaves_no_active_code(
    client: AsyncClient, db_session: AsyncSession, fake_whatsapp
) -> None:
    fake_whatsapp.fail_next = True
    res = await client.post("/auth/whatsapp/request", json={"phone": "+77017770044", "device_id": "dev-wa-4"})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "WHATSAPP_DELIVERY_UNAVAILABLE"
    res = await client.post("/auth/whatsapp/verify", json={"phone": "+77017770044", "device_id": "dev-wa-4", "code": "123456"})
    assert res.json()["error"]["code"] == "OTP_NOT_FOUND"


# --- Profile ----------------------------------------------------------------------------


def test_iin_checksum() -> None:
    assert iin_is_valid("123456789012") is False
    assert iin_is_valid("88051530068") is False  # 11 digits
    # Valid IIN built with the official weights
    base = "90010130000"
    valid = next(base + str(d) for d in range(10) if iin_is_valid(base + str(d)))
    assert iin_is_valid(valid)


@pytest.mark.asyncio
async def test_profile_read_update_and_validation(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers = await customer(db_session)
    res = await client.get("/me/profile", headers=headers)
    assert res.status_code == 200
    assert res.json()["phone"] == "+77015550101"
    assert res.json()["first_name"] is None

    base = "90010130000"
    iin = next(base + str(d) for d in range(10) if iin_is_valid(base + str(d)))
    res = await client.patch("/me/profile", headers=headers, json={
        "first_name": " Айгерим ", "last_name": "Серикова", "email": "Aigerim@Example.KZ",
        "gender": "female", "city": "Алматы", "birth_date": "1990-01-01", "iin": iin,
        "company": "", "language": "kz",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["first_name"] == "Айгерим"
    assert body["email"] == "aigerim@example.kz"
    assert body["company"] is None
    assert body["language"] == "kz"

    for bad in ({"email": "not-an-email"}, {"iin": "123456789012"}, {"gender": "x"},
                {"birth_date": "2999-01-01"}, {"phone": "+77000000000"}):
        res = await client.patch("/me/profile", headers=headers, json=bad)
        assert res.status_code == 422, bad

    res = await client.patch("/me/profile", headers=headers, json={"city": None})
    assert res.json()["city"] is None and res.json()["first_name"] == "Айгерим"


# --- Loyalty levels ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_card_tier_progress(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await customer(db_session)
    biz, _ = await business_with_card(db_session, user, spend_total=Decimal(150000))
    biz.loyalty_tiers = [
        {"level": 1, "name": "Base", "threshold": "0", "percent": "3"},
        {"level": 2, "name": "Silver", "threshold": "500000", "percent": "7"},
        {"level": 3, "name": "Gold", "threshold": "1500000", "percent": "12"},
    ]
    await db_session.commit()

    tier = (await client.get("/me/cards", headers=headers)).json()[0]["tier"]
    assert tier["level"] == 1
    assert tier["next_level"] == 2
    assert Decimal(tier["remaining"]) == Decimal(350000)
    assert Decimal(tier["max_percent"]) == Decimal(12)
    assert [(lv["level"], lv["name"], Decimal(lv["threshold"]), Decimal(lv["percent"])) for lv in tier["levels"]] == [
        (1, "Base", Decimal(0), Decimal(3)),
        (2, "Silver", Decimal(500000), Decimal(7)),
        (3, "Gold", Decimal(1500000), Decimal(12)),
    ]


@pytest.mark.asyncio
async def test_card_tier_absent_without_levels_and_sync_sets_spend(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, headers = await customer(db_session)
    biz, card = await business_with_card(db_session, user)
    assert (await client.get("/me/cards", headers=headers)).json()[0]["tier"] is None

    _, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()
    res = await client.post("/agent/sync/cards", headers={"X-Agent-Key": key}, json={"cards": [{
        "barcode": card.barcode, "phone": user.phone, "balance": "1.0000",
        "spend_total": "2500.5000", "updated_at": (utcnow() + timedelta(minutes=1)).isoformat(),
    }]})
    assert res.status_code == 200
    card_id = card.id
    db_session.expire_all()
    stored = await db_session.scalar(select(Card).where(Card.id == card_id))
    assert stored is not None and stored.spend_total == Decimal("2500.5000")


# --- Promotions, notifications, badges --------------------------------------------------


@pytest.mark.asyncio
async def test_promotions_visibility_and_new_badge(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await customer(db_session)
    biz, _ = await business_with_card(db_session, user)
    other = Business(name="Other", status="active")
    db_session.add(other)
    await db_session.flush()
    now = utcnow()
    db_session.add_all([
        Promotion(kind="banner", title="Global banner"),
        Promotion(kind="offer", title="Own offer", business_id=biz.id, badge="Акция недели"),
        Promotion(kind="offer", title="Other business", business_id=other.id),
        Promotion(kind="offer", title="Inactive", is_active=False),
        Promotion(kind="offer", title="Expired", ends_at=now - timedelta(hours=1)),
        Promotion(kind="offer", title="Future", starts_at=now + timedelta(days=1)),
    ])
    await db_session.commit()

    res = await client.get("/me/promotions", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert [p["title"] for p in data["banners"]] == ["Global banner"]
    assert [p["title"] for p in data["offers"]] == ["Own offer"]
    assert data["has_new"] is True and data["offers"][0]["is_new"] is True
    assert (await client.get("/me/badges", headers=headers)).json()["promotions_new"] is True

    detail = await client.get(f"/me/promotions/{data['offers'][0]['id']}", headers=headers)
    assert detail.status_code == 200 and detail.json()["badge"] == "Акция недели"
    hidden = (await db_session.scalars(select(Promotion).where(Promotion.title == "Other business"))).one()
    assert (await client.get(f"/me/promotions/{hidden.id}", headers=headers)).status_code == 404

    assert (await client.post("/me/promotions/seen", headers=headers)).status_code == 204
    assert (await client.get("/me/promotions", headers=headers)).json()["has_new"] is False
    assert (await client.get("/me/badges", headers=headers)).json()["promotions_new"] is False


@pytest.mark.asyncio
async def test_notifications_audience_unread_and_read(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await customer(db_session)
    other_user, _ = await customer(db_session, phone="+77015550202")
    biz, _ = await business_with_card(db_session, user)
    other = Business(name="Other", status="active")
    db_session.add(other)
    await db_session.flush()
    db_session.add_all([
        Notification(title="Всем", body="global"),
        Notification(title="Магазин", body="biz", business_id=biz.id),
        Notification(title="Чужой магазин", body="x", business_id=other.id),
        Notification(title="Лично", body="me", user_id=user.id),
        Notification(title="Другому", body="x", user_id=other_user.id),
    ])
    await db_session.commit()

    data = (await client.get("/me/notifications", headers=headers)).json()
    assert {n["title"] for n in data["items"]} == {"Всем", "Магазин", "Лично"}
    assert data["unread_count"] == 3
    assert (await client.get("/me/badges", headers=headers)).json()["notifications_unread"] == 3

    assert (await client.post("/me/notifications/read", headers=headers)).status_code == 204
    data = (await client.get("/me/notifications", headers=headers)).json()
    assert data["unread_count"] == 0 and not any(n["is_unread"] for n in data["items"])


@pytest.mark.asyncio
async def test_fresh_transaction_sync_notifies_card_owner(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await customer(db_session)
    biz, card = await business_with_card(db_session, user, name="Магазин ONE")
    _, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()
    res = await client.post("/agent/sync/transactions", headers={"X-Agent-Key": key}, json={"transactions": [
        {"external_id": "t-new", "barcode": card.barcode, "type": "accrual", "amount": "1500.0000",
         "balance_after": "1600.0000", "occurred_at": utcnow().isoformat()},
        {"external_id": "t-old", "barcode": card.barcode, "type": "accrual", "amount": "5.0000",
         "balance_after": "100.0000", "occurred_at": (utcnow() - timedelta(days=30)).isoformat()},
    ]})
    assert res.status_code == 200, res.text
    items = (await client.get("/me/notifications", headers=headers)).json()["items"]
    assert [n["title"] for n in items] == ["Начислено 1 500 баллов"]
    assert "Магазин ONE" in items[0]["body"] and "1 600" in items[0]["body"]


# --- Dynamic QR -------------------------------------------------------------------------


def test_qr_token_roundtrip_expiry_and_tamper() -> None:
    card_id = uuid.uuid4()
    token, expires_at = issue_card_token(card_id)
    assert re.fullmatch(r"C1[A-Z2-7]{48}", token)
    assert verify_card_token(token) == card_id
    assert verify_card_token(token.lower()) == card_id
    assert verify_card_token(token, now=expires_at + timedelta(seconds=1)) is None
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert verify_card_token(tampered) is None
    assert verify_card_token("0123456789012") is None


@pytest.mark.asyncio
async def test_customer_qr_and_agent_resolution(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await customer(db_session)
    biz, card = await business_with_card(db_session, user)
    other_biz, foreign = await business_with_card(db_session, None, name="Other", barcode="0123456789002")
    _, key = await issue_agent_key(db_session, biz.id)
    _, other_key = await issue_agent_key(db_session, other_biz.id)
    await db_session.commit()

    res = await client.get(f"/me/cards/{card.id}/qr", headers=headers)
    assert res.status_code == 200
    token = res.json()["token"]
    assert res.json()["ttl_seconds"] == settings.qr_token_ttl_seconds
    assert card.barcode not in token
    assert (await client.get(f"/me/cards/{foreign.id}/qr", headers=headers)).status_code == 404

    resolved = await client.post("/agent/qr/resolve", headers={"X-Agent-Key": key}, json={"token": token})
    assert resolved.status_code == 200
    assert resolved.json()["barcode"] == card.barcode
    # Another business's POS cannot resolve this customer's card
    denied = await client.post("/agent/qr/resolve", headers={"X-Agent-Key": other_key}, json={"token": token})
    assert denied.status_code == 404
    bad = await client.post("/agent/qr/resolve", headers={"X-Agent-Key": key}, json={"token": "C1AAAA"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "QR_TOKEN_INVALID"


# --- POS redemption codes ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_redemption_code_sent_to_whatsapp_and_verified(
    client: AsyncClient, db_session: AsyncSession, fake_whatsapp
) -> None:
    user, _ = await customer(db_session)
    biz, card = await business_with_card(db_session, user, name="Магазин")
    _, key = await issue_agent_key(db_session, biz.id)
    _, other_key = await issue_agent_key(db_session, (await business_with_card(db_session, None, name="X", barcode="0123456789003"))[0].id)
    await db_session.commit()
    agent = {"X-Agent-Key": key}

    res = await client.post("/agent/redemptions", headers=agent, json={"barcode": card.barcode, "amount": "1500"})
    assert res.status_code == 201, res.text
    redemption_id = res.json()["redemption_id"]
    assert res.json()["recipient"] == "+770******01"
    [(recipient, text)] = fake_whatsapp.sent_messages
    assert recipient == user.phone and "1 500" in text and "Магазин" in text
    code = re.search(r"\b(\d{6})\b", text).group(1)  # type: ignore[union-attr]

    assert (await client.post(f"/agent/redemptions/{redemption_id}/verify", headers={"X-Agent-Key": other_key},
                              json={"code": code})).status_code == 404
    wrong = "000000" if code != "000000" else "111111"
    res = await client.post(f"/agent/redemptions/{redemption_id}/verify", headers=agent, json={"code": wrong})
    assert res.status_code == 400 and res.json()["error"]["code"] == "INVALID_CODE"

    res = await client.post(f"/agent/redemptions/{redemption_id}/verify", headers=agent, json={"code": code})
    assert res.status_code == 200
    assert res.json() == {"status": "confirmed", "barcode": card.barcode, "amount": "1500.0000"}
    again = await client.post(f"/agent/redemptions/{redemption_id}/verify", headers=agent, json={"code": code})
    assert again.status_code == 409 and again.json()["error"]["code"] == "REDEMPTION_ALREADY_CONFIRMED"


@pytest.mark.asyncio
async def test_redemption_via_qr_expiry_and_attempt_limit(
    client: AsyncClient, db_session: AsyncSession, fake_whatsapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "redemption_code_max_attempts", 2)
    user, _ = await customer(db_session)
    biz, card = await business_with_card(db_session, user)
    _, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()
    agent = {"X-Agent-Key": key}
    token, _ = issue_card_token(card.id)

    res = await client.post("/agent/redemptions", headers=agent, json={"qr_token": token, "amount": "10"})
    assert res.status_code == 201
    rid = res.json()["redemption_id"]
    code = re.search(r"\b(\d{6})\b", fake_whatsapp.sent_messages[-1][1]).group(1)  # type: ignore[union-attr]
    wrong = "000000" if code != "000000" else "111111"
    await client.post(f"/agent/redemptions/{rid}/verify", headers=agent, json={"code": wrong})
    res = await client.post(f"/agent/redemptions/{rid}/verify", headers=agent, json={"code": wrong})
    assert res.json()["error"]["code"] == "REDEMPTION_MAX_ATTEMPTS_EXCEEDED"
    res = await client.post(f"/agent/redemptions/{rid}/verify", headers=agent, json={"code": code})
    assert res.json()["error"]["code"] == "REDEMPTION_NOT_ACTIVE"

    res = await client.post("/agent/redemptions", headers=agent, json={"barcode": card.barcode, "amount": "10"})
    rid = res.json()["redemption_id"]
    code = re.search(r"\b(\d{6})\b", fake_whatsapp.sent_messages[-1][1]).group(1)  # type: ignore[union-attr]
    record = await db_session.get_one(RedemptionCode, uuid.UUID(rid))
    record.expires_at = utcnow() - timedelta(seconds=1)
    await db_session.commit()
    res = await client.post(f"/agent/redemptions/{rid}/verify", headers=agent, json={"code": code})
    assert res.json()["error"]["code"] == "REDEMPTION_EXPIRED"

    for payload in ({"amount": "10"}, {"barcode": card.barcode, "qr_token": token, "amount": "10"},
                    {"barcode": card.barcode, "amount": "0"}):
        assert (await client.post("/agent/redemptions", headers=agent, json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_redemption_requires_phone_and_configured_whatsapp(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    biz, card = await business_with_card(db_session, None)
    _, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()
    agent = {"X-Agent-Key": key}
    res = await client.post("/agent/redemptions", headers=agent, json={"barcode": card.barcode, "amount": "5"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "REDEMPTION_PHONE_MISSING"

    monkeypatch.setattr(settings, "whatsapp_provider_mode", "disabled")
    res = await client.post("/agent/redemptions", headers=agent, json={"barcode": card.barcode, "amount": "5"})
    assert res.status_code == 503 and res.json()["error"]["code"] == "WHATSAPP_NOT_CONFIGURED"


def test_log_whatsapp_mode_is_forbidden_in_production() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="forbidden in production"):
        Settings(app_env="production", database_url="postgresql+asyncpg://x/y", whatsapp_provider_mode="log")
    with pytest.raises(ValidationError, match="WAPPI_API_TOKEN"):
        Settings(app_env="test", database_url="sqlite+aiosqlite:///:memory:", whatsapp_provider_mode="wappi")


@pytest.mark.asyncio
async def test_log_whatsapp_sender_prints_message(caplog: pytest.LogCaptureFixture) -> None:
    from app.services.whatsapp_sender import LogWhatsAppSender

    with caplog.at_level("WARNING"):
        await LogWhatsAppSender().send_text("+77010000000", "Код: 123456\nтест")
    assert "123456" in caplog.text and "+77010000000" in caplog.text
