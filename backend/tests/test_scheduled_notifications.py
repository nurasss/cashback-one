"""Tests for scheduled notifications and background scheduler (2026-11-07)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminUser
from app.models.entities import Business, Card, Device, Notification, User, UserCard
from app.schemas.admin_content import NotificationCreateRequest
from app.services import admin_content
from app.services.admin_auth import authenticate_admin
from app.services.content_service import list_notifications
from app.services.notification_scheduler import process_scheduled_notifications
from app.services.push_sender import FakePushSender


@pytest.fixture
def fake_push_sender() -> FakePushSender:
    return FakePushSender()


@pytest.fixture
async def admin_client(db_session: AsyncSession, fake_push_sender: FakePushSender):
    admin = AdminUser(
        login="superadmin_test",
        password_hash="dummy_hash",
        role="superadmin",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()

    async def override_session():
        yield db_session

    async def override_admin():
        return admin

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[authenticate_admin] = override_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
        yield client, admin

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scheduled_notification_creation_and_validation(
    db_session: AsyncSession, admin_client
) -> None:
    client, _admin = admin_client
    now = utcnow()

    headers = {"Origin": "https://admin.test", "X-Admin-Request": "1"}

    # 1. Past time -> 400 or 422
    past_time = now - timedelta(hours=1)
    res_past = await client.post(
        "/admin/notifications",
        headers=headers,
        json={
            "title": "Past Notice",
            "body": "Body",
            "scheduled_at": past_time.isoformat(),
        },
    )
    assert res_past.status_code in (400, 422)
    assert "прошлом" in res_past.text

    # 2. Too far into the future (> 30 days) -> 400 or 422
    far_future = now + timedelta(days=35)
    res_far = await client.post(
        "/admin/notifications",
        headers=headers,
        json={
            "title": "Far Future",
            "body": "Body",
            "scheduled_at": far_future.isoformat(),
        },
    )
    assert res_far.status_code in (400, 422)
    assert "30 дней" in res_far.text

    # 3. Valid future time -> 201 Created
    valid_time = now + timedelta(days=2)
    res_valid = await client.post(
        "/admin/notifications",
        headers=headers,
        json={
            "title": "Valid Scheduled",
            "body": "Body for future",
            "scheduled_at": valid_time.isoformat(),
            "send_push": True,
        },
    )
    assert res_valid.status_code == 201
    data = res_valid.json()
    assert data["title"] == "Valid Scheduled"
    assert data["scheduled_at"] is not None
    assert data["push_sent_at"] is None
    assert data["push"] is None  # Push not sent yet


@pytest.mark.asyncio
async def test_scheduled_notification_customer_visibility(db_session: AsyncSession) -> None:
    """Scheduled notification is invisible to customer until scheduled_at."""
    now = utcnow()
    user = User(phone="+77001112244", language="ru", created_at=now - timedelta(days=2))
    biz = Business(name="Shop S", status="active")
    db_session.add_all([user, biz])
    await db_session.flush()

    card = Card(business_id=biz.id, barcode="888001", balance=Decimal(100))
    db_session.add(card)
    await db_session.flush()

    binding = UserCard(user_id=user.id, card_id=card.id)
    db_session.add(binding)

    # 1. Notification scheduled for future (in 1 hour)
    note_future = Notification(
        business_id=biz.id,
        title="Future Notice",
        body="Secret sale",
        scheduled_at=now + timedelta(hours=1),
    )
    # 2. Notification scheduled in past (effectively active)
    note_ready = Notification(
        business_id=biz.id,
        title="Active Notice",
        body="Sale now",
        scheduled_at=now - timedelta(minutes=5),
    )
    db_session.add_all([note_future, note_ready])
    await db_session.commit()

    # List notifications for customer
    res = await list_notifications(db_session, user, business_id=biz.id)
    titles = [item.title for item in res.items]

    # Future note must NOT be visible, active note MUST be visible
    assert "Active Notice" in titles
    assert "Future Notice" not in titles
    assert res.unread_count == 1


@pytest.mark.asyncio
async def test_scheduler_worker_sends_push_once_and_deletes_cleanly(
    db_session: AsyncSession, fake_push_sender: FakePushSender
) -> None:
    """Scheduler finds due notifications, sends push, sets push_sent_at, exactly once."""
    user = User(phone="+77005554433", language="ru")
    biz = Business(name="Biz Sched", android_app_id=None, status="active")
    db_session.add_all([user, biz])
    await db_session.flush()

    card = Card(business_id=biz.id, barcode="777001", balance=Decimal(50))
    db_session.add(card)
    await db_session.flush()

    binding = UserCard(user_id=user.id, card_id=card.id)
    dev = Device(
        user_id=user.id,
        push_token="tok_sched_123",
        app_id=settings.push_shared_app_id,
        platform="android",
    )
    db_session.add_all([binding, dev])
    await db_session.flush()

    now = utcnow()
    # Create notification due now
    note = Notification(
        business_id=biz.id,
        title="Due Notice",
        body="Due text",
        scheduled_at=now - timedelta(seconds=10),
        push_sent_at=None,
    )
    db_session.add(note)
    await db_session.commit()

    # Process via worker
    count = await process_scheduled_notifications(db_session, sender=fake_push_sender)
    assert count == 1
    assert len(fake_push_sender.sent_messages) == 1
    assert fake_push_sender.sent_messages[0].token == "tok_sched_123"

    # Verify push_sent_at is set in DB
    refreshed = await db_session.get(Notification, note.id)
    assert refreshed is not None
    assert refreshed.push_sent_at is not None

    # Running worker again finds nothing (idempotent / exactly once)
    count2 = await process_scheduled_notifications(db_session, sender=fake_push_sender)
    assert count2 == 0
    assert len(fake_push_sender.sent_messages) == 1  # No duplicate push


@pytest.mark.asyncio
async def test_delete_scheduled_notification_before_send(
    db_session: AsyncSession, admin_client, fake_push_sender: FakePushSender
) -> None:
    """Admin can delete a scheduled notification before send; worker does not send push."""
    _client, admin = admin_client
    now = utcnow()
    future_time = now + timedelta(hours=2)

    req = NotificationCreateRequest(
        title="To Be Deleted",
        body="Will be deleted",
        scheduled_at=future_time,
        send_push=True,
    )
    created = await admin_content.create_notification(db_session, admin, req, sender=fake_push_sender)
    assert created.id is not None

    # Delete via admin service
    await admin_content.delete_notification(db_session, admin, created.id)

    # Verify gone from DB
    deleted = await db_session.get(Notification, created.id)
    assert deleted is None

    # Fast forward in time - worker should find nothing
    processed = await process_scheduled_notifications(db_session, sender=fake_push_sender)
    assert processed == 0
    assert len(fake_push_sender.sent_messages) == 0
