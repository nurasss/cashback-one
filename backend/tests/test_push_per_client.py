"""Tests for push notification targeting per client app (Task I-backend)."""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Business, Card, Device, User, UserCard
from app.services.push_sender import PushResult, PushStatus
from app.services.push_service import (
    has_active_device,
    resolve_allowed_app_ids,
    send_to_user,
)


class RecordingPushSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult:
        self.sent.append({"token": token, "title": title, "body": body, "data": data})
        return PushResult(status=PushStatus.DELIVERED)


@pytest.mark.asyncio
async def test_resolve_allowed_app_ids(db_session: AsyncSession) -> None:
    # 1. business_id is None -> returns None (all devices)
    assert await resolve_allowed_app_ids(db_session, None) is None

    # 2. Business with android_app_id -> {android_app_id, shared_app_id}
    biz_keremet = Business(
        name="Keremet Market",
        android_app_id="kz.cashbackone.keremet",
        status="active",
    )
    # 3. Business without android_app_id -> {shared_app_id}
    biz_general = Business(
        name="General Market",
        android_app_id=None,
        status="active",
    )
    db_session.add_all([biz_keremet, biz_general])
    await db_session.commit()

    allowed_keremet = await resolve_allowed_app_ids(db_session, biz_keremet.id)
    assert allowed_keremet == {"kz.cashbackone.keremet", settings.push_shared_app_id}

    allowed_general = await resolve_allowed_app_ids(db_session, biz_general.id)
    assert allowed_general == {settings.push_shared_app_id}


@pytest.mark.asyncio
async def test_push_targeting_three_devices(db_session: AsyncSession) -> None:
    """User has 3 devices: shared (kz.cashbackone.mobile), keremet, other.

    Redemption for keremet (with android_app_id) -> shared and keremet receive, other does not.
    Business without android_app_id -> only shared receives.
    """
    user = User(phone="+77001112233", language="ru")
    biz_keremet = Business(
        name="Keremet Store",
        android_app_id="kz.cashbackone.keremet",
        status="active",
    )
    biz_no_app = Business(
        name="Plain Store",
        android_app_id=None,
        status="active",
    )
    db_session.add_all([user, biz_keremet, biz_no_app])
    await db_session.flush()

    # Register 3 active devices
    dev_shared = Device(
        user_id=user.id,
        push_token="tok_shared_111",
        app_id="kz.cashbackone.mobile",
        platform="android",
    )
    dev_keremet = Device(
        user_id=user.id,
        push_token="tok_keremet_222",
        app_id="kz.cashbackone.keremet",
        platform="android",
    )
    dev_other = Device(
        user_id=user.id,
        push_token="tok_other_333",
        app_id="kz.cashbackone.other",
        platform="android",
    )
    db_session.add_all([dev_shared, dev_keremet, dev_other])
    await db_session.commit()

    # Check has_active_device
    assert await has_active_device(db_session, user.id, business_id=biz_keremet.id) is True
    assert await has_active_device(db_session, user.id, business_id=biz_no_app.id) is True

    # Send for Keremet
    sender = RecordingPushSender()
    delivered = await send_to_user(
        session=db_session,
        sender=sender,
        user_id=user.id,
        title="Keremet Notification",
        body="Body",
        business_id=biz_keremet.id,
    )
    assert delivered == 2
    sent_tokens = {msg["token"] for msg in sender.sent}
    assert sent_tokens == {"tok_shared_111", "tok_keremet_222"}
    assert "tok_other_333" not in sent_tokens

    # Send for Plain Store (no android_app_id)
    sender_plain = RecordingPushSender()
    delivered_plain = await send_to_user(
        session=db_session,
        sender=sender_plain,
        user_id=user.id,
        title="Plain Notification",
        body="Body",
        business_id=biz_no_app.id,
    )
    assert delivered_plain == 1
    sent_plain_tokens = {msg["token"] for msg in sender_plain.sent}
    assert sent_plain_tokens == {"tok_shared_111"}
    assert "tok_keremet_222" not in sent_plain_tokens
    assert "tok_other_333" not in sent_plain_tokens


@pytest.mark.asyncio
async def test_push_targeting_customer_no_app(db_session: AsyncSession) -> None:
    """User has only 'other' device.

    Keremet redemption must fail with CUSTOMER_NO_APP (409).
    """
    user = User(phone="+77009998877", language="ru")
    biz_keremet = Business(
        name="Keremet Store",
        android_app_id="kz.cashbackone.keremet",
        status="active",
    )
    db_session.add_all([user, biz_keremet])
    await db_session.flush()

    card = Card(
        business_id=biz_keremet.id,
        barcode="999900001",
        phone="+77009998877",
        balance=Decimal("5000.0000"),
    )
    db_session.add(card)
    await db_session.flush()

    binding = UserCard(user_id=user.id, card_id=card.id, bind_method="manual")
    # Only other app device registered
    dev_other = Device(
        user_id=user.id,
        push_token="tok_other_999",
        app_id="kz.cashbackone.other",
        platform="android",
    )
    db_session.add_all([binding, dev_other])
    await db_session.commit()

    # has_active_device returns False for Keremet because user has only kz.cashbackone.other
    assert await has_active_device(db_session, user.id, business_id=biz_keremet.id) is False

    # Also for Plain Store
    biz_plain = Business(name="Plain Store", android_app_id=None, status="active")
    db_session.add(biz_plain)
    await db_session.commit()
    assert await has_active_device(db_session, user.id, business_id=biz_plain.id) is False
