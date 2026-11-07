"""Tests for admin broadcast push notifications."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.admin import AdminUser
from app.models.entities import AuditLog, Business, Card, Device, Notification, User, UserCard
from app.schemas.admin_content import NotificationCreateRequest
from app.services import admin_content
from app.services.push_sender import FakePushSender, PushResult, PushStatus, get_push_sender
from tests.test_admin_mutations import (  # noqa: F401
    auth_headers,
    mutation_client,
)


class ErroringPushSender:
    disabled = False

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult:
        return PushResult(status=PushStatus.TEMPORARY_ERROR, error_details="Server error")


@pytest.fixture
def fake_push_sender() -> FakePushSender:
    sender = FakePushSender()
    sender.clear()
    return sender


@pytest.fixture
async def admin_users(db_session: AsyncSession) -> tuple[AdminUser, AdminUser, Business, Business]:
    biz_b = Business(
        name="Business B",
        status="active",
        android_app_id="kz.cashbackone.b",
    )
    biz_c = Business(
        name="Business C",
        status="active",
        android_app_id="kz.cashbackone.c",
    )
    db_session.add_all([biz_b, biz_c])
    await db_session.flush()

    superadmin = AdminUser(
        login="superadmin",
        password_hash="fake",
        role="superadmin",
        is_active=True,
    )
    manager_b = AdminUser(
        login="manager_b",
        password_hash="fake",
        role="business_manager",
        business_id=biz_b.id,
        is_active=True,
    )
    db_session.add_all([superadmin, manager_b])
    await db_session.commit()
    return superadmin, manager_b, biz_b, biz_c


@pytest.mark.asyncio
async def test_broadcast_push_business_b_targeting(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """Business B with android_app_id:

    - dev1: app_id == B.android_app_id, user has NO card -> receives push
    - dev2: app_id == shared_app_id, user has card of B -> receives push
    - dev3: app_id == shared_app_id, user has NO card of B -> does NOT receive
    - dev4: app_id == shared_app_id, user card of B is hidden -> does NOT receive
    - dev5: app_id == C.android_app_id -> does NOT receive
    """
    superadmin, _, biz_b, _ = admin_users

    # Users
    u1 = User(phone="+77000000001", language="ru")  # no card, has B app
    u2 = User(phone="+77000000002", language="ru")  # has card of B, has shared app
    u3 = User(phone="+77000000003", language="ru")  # no card of B, has shared app
    u4 = User(phone="+77000000004", language="ru")  # hidden card of B, has shared app
    u5 = User(phone="+77000000005", language="ru")  # has C app
    db_session.add_all([u1, u2, u3, u4, u5])
    await db_session.flush()

    # Cards
    c2 = Card(business_id=biz_b.id, barcode="0002", balance=0)
    c4 = Card(business_id=biz_b.id, barcode="0004", balance=0)
    db_session.add_all([c2, c4])
    await db_session.flush()

    # UserCards
    uc2 = UserCard(user_id=u2.id, card_id=c2.id)
    uc4 = UserCard(user_id=u4.id, card_id=c4.id, hidden_at=utcnow())
    db_session.add_all([uc2, uc4])
    await db_session.flush()

    # Devices
    d1 = Device(user_id=u1.id, push_token="tok_d1", app_id="kz.cashbackone.b", platform="android")
    d2 = Device(user_id=u2.id, push_token="tok_d2", app_id=settings.push_shared_app_id, platform="android")
    d3 = Device(user_id=u3.id, push_token="tok_d3", app_id=settings.push_shared_app_id, platform="android")
    d4 = Device(user_id=u4.id, push_token="tok_d4", app_id=settings.push_shared_app_id, platform="android")
    d5 = Device(user_id=u5.id, push_token="tok_d5", app_id="kz.cashbackone.c", platform="android")
    db_session.add_all([d1, d2, d3, d4, d5])
    await db_session.commit()

    req = NotificationCreateRequest(
        business_id=biz_b.id,
        title="B Promo",
        body="B Body text",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=fake_push_sender)
    assert res.push is not None
    assert res.push.status == "sent"
    # Owner rule (2026-11-07): business with own android_app_id targets ONLY devices of that app (tok_d1)
    assert res.push.devices == 1
    assert res.push.delivered == 1

    tokens = {msg.token for msg in fake_push_sender.sent_messages}
    assert tokens == {"tok_d1"}
    for msg in fake_push_sender.sent_messages:
        assert msg.title == "B Promo"
        assert msg.body == "B Body text"
        assert msg.data == {"type": "broadcast", "notification_id": str(res.id)}


@pytest.mark.asyncio
async def test_broadcast_push_business_without_app_id(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """Business without android_app_id: only shared app devices with card receive push."""
    superadmin, _, _, _ = admin_users
    biz_plain = Business(name="Plain Biz", status="active", android_app_id=None)
    db_session.add(biz_plain)
    await db_session.flush()

    u1 = User(phone="+77000000011", language="ru")
    u2 = User(phone="+77000000012", language="ru")
    db_session.add_all([u1, u2])
    await db_session.flush()

    card = Card(business_id=biz_plain.id, barcode="0011", balance=0)
    db_session.add(card)
    await db_session.flush()

    uc = UserCard(user_id=u1.id, card_id=card.id)
    db_session.add(uc)

    d1 = Device(user_id=u1.id, push_token="tok_plain_1", app_id=settings.push_shared_app_id, platform="android")
    d2 = Device(user_id=u2.id, push_token="tok_plain_2", app_id=settings.push_shared_app_id, platform="android")
    d3 = Device(user_id=u1.id, push_token="tok_plain_3", app_id="kz.cashbackone.other", platform="android")
    db_session.add_all([d1, d2, d3])
    await db_session.commit()

    req = NotificationCreateRequest(
        business_id=biz_plain.id,
        title="Plain Title",
        body="Plain Body",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=fake_push_sender)
    assert res.push is not None
    assert res.push.status == "sent"
    assert res.push.devices == 1
    assert res.push.delivered == 1
    assert len(fake_push_sender.sent_messages) == 1
    assert fake_push_sender.sent_messages[0].token == "tok_plain_1"


@pytest.mark.asyncio
async def test_broadcast_push_all_businesses(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """business_id is None ('Все бизнесы'): all active devices receive push, disabled do not."""
    superadmin, _, _, _ = admin_users

    u1 = User(phone="+77000000021", language="ru")
    u2 = User(phone="+77000000022", language="ru")
    db_session.add_all([u1, u2])
    await db_session.flush()

    d1 = Device(user_id=u1.id, push_token="tok_all_1", app_id=settings.push_shared_app_id, platform="android")
    d2 = Device(user_id=u1.id, push_token="tok_all_2", app_id="kz.cashbackone.b", platform="android")
    d3 = Device(user_id=u2.id, push_token="tok_all_3", app_id="kz.cashbackone.c", platform="android")
    d4 = Device(
        user_id=u2.id,
        push_token="tok_all_disabled",
        app_id="kz.cashbackone.c",
        platform="android",
        disabled_at=u2.created_at,
    )
    db_session.add_all([d1, d2, d3, d4])
    await db_session.commit()

    req = NotificationCreateRequest(
        business_id=None,
        title="Global Announcement",
        body="Hello everyone",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=fake_push_sender)
    assert res.push is not None
    assert res.push.status == "sent"
    assert res.push.devices == 3
    assert res.push.delivered == 3

    tokens = {msg.token for msg in fake_push_sender.sent_messages}
    assert tokens == {"tok_all_1", "tok_all_2", "tok_all_3"}


@pytest.mark.asyncio
async def test_broadcast_push_send_push_false(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """send_push=False: no push is sent, status is 'skipped', notification created."""
    superadmin, _, _, _ = admin_users

    u = User(phone="+77000000031", language="ru")
    db_session.add(u)
    await db_session.flush()
    d = Device(user_id=u.id, push_token="tok_nopush", app_id=settings.push_shared_app_id, platform="android")
    db_session.add(d)
    await db_session.commit()

    req = NotificationCreateRequest(
        business_id=None,
        title="No Push Note",
        body="Silent note",
        send_push=False,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=fake_push_sender)
    assert res.push is not None
    assert res.push.status == "skipped"
    assert res.push.devices == 0
    assert res.push.delivered == 0
    assert len(fake_push_sender.sent_messages) == 0

    note = await db_session.scalar(select(Notification).where(Notification.id == res.id))
    assert note is not None
    assert note.title == "No Push Note"


@pytest.mark.asyncio
async def test_broadcast_push_mode_disabled(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mode disabled: status is 'disabled', notification created."""
    superadmin, _, _, _ = admin_users
    monkeypatch.setattr(settings, "push_provider_mode", "disabled")

    req = NotificationCreateRequest(
        business_id=None,
        title="Disabled Mode Note",
        body="Text",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req)
    assert res.push is not None
    assert res.push.status == "disabled"
    assert res.push.devices == 0
    assert res.push.delivered == 0

    note = await db_session.scalar(select(Notification).where(Notification.id == res.id))
    assert note is not None


@pytest.mark.asyncio
async def test_broadcast_push_sender_error(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
) -> None:
    """Sender error does not fail notification creation, status is 'failed', 201 response."""
    superadmin, _, _, _ = admin_users

    u = User(phone="+77000000051", language="ru")
    db_session.add(u)
    await db_session.flush()
    d = Device(user_id=u.id, push_token="tok_err", app_id=settings.push_shared_app_id, platform="android")
    db_session.add(d)
    await db_session.commit()

    err_sender = ErroringPushSender()
    req = NotificationCreateRequest(
        business_id=None,
        title="Error Push Note",
        body="Text",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=err_sender)
    assert res.push is not None
    assert res.push.status == "failed"
    assert res.push.devices == 1
    assert res.push.delivered == 0

    # Notification still created
    note = await db_session.scalar(select(Notification).where(Notification.id == res.id))
    assert note is not None


@pytest.mark.asyncio
async def test_broadcast_push_invalid_token_disables_device(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """Invalid token marks device disabled_at."""
    superadmin, _, _, _ = admin_users

    u = User(phone="+77000000061", language="ru")
    db_session.add(u)
    await db_session.flush()
    d = Device(user_id=u.id, push_token="tok_invalid", app_id=settings.push_shared_app_id, platform="android")
    db_session.add(d)
    await db_session.commit()

    fake_push_sender.results_by_token["tok_invalid"] = PushResult(
        status=PushStatus.INVALID_TOKEN, error_details="UNREGISTERED"
    )

    req = NotificationCreateRequest(
        business_id=None,
        title="Invalid Token Note",
        body="Text",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=fake_push_sender)
    assert res.push is not None
    assert res.push.status == "failed"
    assert res.push.devices == 1
    assert res.push.delivered == 0

    await db_session.refresh(d)
    assert d.disabled_at is not None


@pytest.mark.asyncio
async def test_broadcast_push_manager_cannot_send_to_other_business(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """Manager of business B cannot send notification with business C."""
    _, manager_b, _, biz_c = admin_users

    req = NotificationCreateRequest(
        business_id=biz_c.id,
        title="Cross-tenant Note",
        body="Text",
        send_push=True,
    )
    with pytest.raises(Exception) as exc:
        await admin_content.create_notification(db_session, manager_b, req, sender=fake_push_sender)
    assert getattr(exc.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_broadcast_push_audit_log(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    fake_push_sender: FakePushSender,
) -> None:
    """Audit log contains push_devices and push_delivered."""
    superadmin, _, _, _ = admin_users

    u = User(phone="+77000000081", language="ru")
    db_session.add(u)
    await db_session.flush()
    d = Device(user_id=u.id, push_token="tok_audit", app_id=settings.push_shared_app_id, platform="android")
    db_session.add(d)
    await db_session.commit()

    req = NotificationCreateRequest(
        business_id=None,
        title="Audit Note",
        body="Text",
        send_push=True,
    )
    res = await admin_content.create_notification(db_session, superadmin, req, sender=fake_push_sender)
    assert res.push is not None
    assert res.push.status == "sent"

    log = await db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "notification_created")
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    assert log is not None
    assert log.after_state is not None
    assert log.after_state.get("push_devices") == 1
    assert log.after_state.get("push_delivered") == 1


@pytest.mark.asyncio
async def test_broadcast_push_api_endpoint(
    db_session: AsyncSession,
    admin_users: tuple[AdminUser, AdminUser, Business, Business],
    mutation_client: AsyncClient,  # noqa: F811
    fake_push_sender: FakePushSender,
) -> None:
    """POST /admin/notifications returns 201 with push summary."""
    superadmin, _, biz_b, _ = admin_users
    headers = await auth_headers(db_session, superadmin)

    u = User(phone="+77000000091", language="ru")
    db_session.add(u)
    await db_session.flush()
    d = Device(user_id=u.id, push_token="tok_api_endpoint", app_id="kz.cashbackone.b", platform="android")
    db_session.add(d)
    await db_session.commit()

    from app.main import app

    app.dependency_overrides[get_push_sender] = lambda: fake_push_sender
    try:
        resp = await mutation_client.post(
            "/admin/notifications",
            headers=headers,
            json={
                "business_id": str(biz_b.id),
                "title": "API Note",
                "body": "API Body",
                "send_push": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Note"
        assert data["push"] == {"status": "sent", "devices": 1, "delivered": 1}
    finally:
        app.dependency_overrides.pop(get_push_sender, None)
