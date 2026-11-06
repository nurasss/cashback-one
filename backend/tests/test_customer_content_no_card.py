"""Tests for customer content visibility in client app without a card (Task 2026-11-06)."""
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.entities import (
    AuthSession,
    Business,
    BusinessStore,
    Card,
    Notification,
    Promotion,
    User,
    UserCard,
)
from app.services.rate_limiter import _test_limiter, get_rate_limiter


@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://testserver"
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def create_customer(
    db: AsyncSession, phone: str = "+77017770099", registered_ago: timedelta = timedelta(days=2)
) -> tuple[User, dict[str, str]]:
    user = User(phone=phone, language="ru", created_at=utcnow() - registered_ago)
    db.add(user)
    await db.flush()
    session = AuthSession(
        user_id=user.id,
        device_id="dev-content-no-card",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(session)
    await db.flush()
    token = create_access_token(user.id, session.id)
    await db.commit()
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_customer_without_card_sees_business_b_content_and_global_banners(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Customer without card in business B:

    - with business_id=B: sees banners & offers of B and global banners;
    - global offers and business C content are NOT shown;
    - GET /me/promotions/{offer B} -> 200, {offer C} -> 404;
    - sees broadcast B, does NOT see broadcast C;
    - /me/app-content?business_id=B -> 200 with stores and texts.
    """
    user, headers = await create_customer(db_session, "+77011002030")

    biz_b = Business(
        name="Супермаркет Керемет",
        status="active",
        app_texts={
            "home_store_note_lead": {"ru": "Тратьте баллы в Керемет"},
            "balance_delay_note": {"ru": "Баллы начисляются после смены"},
        },
    )
    biz_c = Business(name="Другой ритейлер", status="active")
    db_session.add_all([biz_b, biz_c])
    await db_session.flush()

    store_b = BusinessStore(
        business_id=biz_b.id,
        title_ru="Керемет ТЦ In Plaza",
        title_kk="Керемет In Plaza СОО",
        address_ru="Тауелсиздик, 4",
        address_kk="Тәуелсіздік, 4",
        is_active=True,
        sort_order=1,
    )
    db_session.add(store_b)

    # Global promotions
    global_banner = Promotion(
        title="Общий баннер POSCENTER",
        kind="banner",
        business_id=None,
        is_active=True,
        sort_order=10,
    )
    global_offer = Promotion(
        title="Общая акция POSCENTER",
        kind="offer",
        business_id=None,
        is_active=True,
    )

    # Business B promotions
    banner_b = Promotion(
        title="Баннер Керемет",
        kind="banner",
        business_id=biz_b.id,
        is_active=True,
        sort_order=5,
    )
    offer_b = Promotion(
        title="Акция Керемет",
        kind="offer",
        business_id=biz_b.id,
        is_active=True,
    )

    # Business C promotions
    banner_c = Promotion(
        title="Баннер C",
        kind="banner",
        business_id=biz_c.id,
        is_active=True,
    )
    offer_c = Promotion(
        title="Акция C",
        kind="offer",
        business_id=biz_c.id,
        is_active=True,
    )

    # Broadcast notifications (user_id is None, created after customer registration)
    notif_b = Notification(
        business_id=biz_b.id,
        user_id=None,
        title="Рассылка Керемет",
        body="Скидки на выходных!",
        created_at=user.created_at + timedelta(hours=1),
    )
    notif_c = Notification(
        business_id=biz_c.id,
        user_id=None,
        title="Рассылка C",
        body="Новости магазина C",
        created_at=user.created_at + timedelta(hours=1),
    )

    db_session.add_all([
        global_banner,
        global_offer,
        banner_b,
        offer_b,
        banner_c,
        offer_c,
        notif_b,
        notif_c,
    ])
    await db_session.commit()

    # 1. GET /me/promotions?business_id=B
    resp_promo = await client.get(f"/me/promotions?business_id={biz_b.id}", headers=headers)
    assert resp_promo.status_code == 200
    promo_data = resp_promo.json()
    banner_titles = [b["title"] for b in promo_data["banners"]]
    offer_titles = [o["title"] for o in promo_data["offers"]]
    # Sees banner B and global banner; does NOT see banner C
    assert banner_titles == ["Баннер Керемет", "Общий баннер POSCENTER"]
    # Sees offer B; does NOT see global offer or offer C
    assert offer_titles == ["Акция Керемет"]
    assert promo_data["has_new"] is True

    # 2. Detail GET /me/promotions/{id}?business_id=B
    # Offer B -> 200 OK
    resp_ob = await client.get(f"/me/promotions/{offer_b.id}?business_id={biz_b.id}", headers=headers)
    assert resp_ob.status_code == 200
    assert resp_ob.json()["title"] == "Акция Керемет"

    # Offer C -> 404 NOT FOUND
    resp_oc = await client.get(f"/me/promotions/{offer_c.id}?business_id={biz_b.id}", headers=headers)
    assert resp_oc.status_code == 404
    assert resp_oc.json()["error"]["code"] == "PROMOTION_NOT_FOUND"

    # Global banner -> 200 OK
    resp_gb = await client.get(f"/me/promotions/{global_banner.id}?business_id={biz_b.id}", headers=headers)
    assert resp_gb.status_code == 200

    # Global offer -> 404 NOT FOUND (client app does not show global offers)
    resp_go = await client.get(f"/me/promotions/{global_offer.id}?business_id={biz_b.id}", headers=headers)
    assert resp_go.status_code == 404

    # 3. GET /me/notifications?business_id=B
    resp_notifs = await client.get(f"/me/notifications?business_id={biz_b.id}", headers=headers)
    assert resp_notifs.status_code == 200
    notif_items = resp_notifs.json()["items"]
    assert len(notif_items) == 1
    assert notif_items[0]["title"] == "Рассылка Керемет"
    assert resp_notifs.json()["unread_count"] == 1

    # 4. GET /me/badges?business_id=B
    resp_badges = await client.get(f"/me/badges?business_id={biz_b.id}", headers=headers)
    assert resp_badges.status_code == 200
    assert resp_badges.json() == {"promotions_new": True, "notifications_unread": 1}

    # 5. POST /me/notifications/read?business_id=B
    read_resp = await client.post(f"/me/notifications/read?business_id={biz_b.id}", headers=headers)
    assert read_resp.status_code == 204

    # Badges now show 0 unread
    resp_badges_after = await client.get(f"/me/badges?business_id={biz_b.id}", headers=headers)
    assert resp_badges_after.json()["notifications_unread"] == 0

    # 6. GET /me/app-content?business_id=B -> 200 OK without card
    resp_content = await client.get(f"/me/app-content?business_id={biz_b.id}", headers=headers)
    assert resp_content.status_code == 200
    content_data = resp_content.json()
    assert content_data["business_id"] == str(biz_b.id)
    assert len(content_data["stores"]) == 1
    assert content_data["stores"][0]["title_ru"] == "Керемет ТЦ In Plaza"
    assert content_data["app_texts"]["home_store_note_lead"]["ru"] == "Тратьте баллы в Керемет"


@pytest.mark.asyncio
async def test_inactive_and_nonexistent_business(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Inactive or non-existent business:

    - /me/app-content?business_id=... -> 404
    - /me/promotions?business_id=... -> only global banners (no offers)
    - /me/promotions/{id} for its promo -> 404
    - /me/notifications?business_id=... -> empty items, 0 unread
    - /me/badges?business_id=... -> promotions_new=False, notifications_unread=0
    """
    _user, headers = await create_customer(db_session, "+77011002031")

    inactive_biz = Business(name="Закрытый магазин", status="suspended")
    db_session.add(inactive_biz)
    await db_session.flush()

    global_banner = Promotion(
        title="Общий баннер POSCENTER",
        kind="banner",
        business_id=None,
        is_active=True,
    )
    inactive_promo = Promotion(
        title="Акция закрытого",
        kind="offer",
        business_id=inactive_biz.id,
        is_active=True,
    )
    inactive_notif = Notification(
        business_id=inactive_biz.id,
        user_id=None,
        title="Рассылка закрытого",
        body="Сообщение",
    )
    db_session.add_all([global_banner, inactive_promo, inactive_notif])
    await db_session.commit()

    # 1. Non-existent business UUID
    random_id = uuid.uuid4()
    assert (await client.get(f"/me/app-content?business_id={random_id}", headers=headers)).status_code == 404

    resp_promo_fake = await client.get(f"/me/promotions?business_id={random_id}", headers=headers)
    assert resp_promo_fake.status_code == 200
    assert [b["title"] for b in resp_promo_fake.json()["banners"]] == ["Общий баннер POSCENTER"]
    assert resp_promo_fake.json()["offers"] == []

    resp_notifs_fake = await client.get(f"/me/notifications?business_id={random_id}", headers=headers)
    assert resp_notifs_fake.status_code == 200
    assert resp_notifs_fake.json()["items"] == []
    assert resp_notifs_fake.json()["unread_count"] == 0

    resp_badges_fake = await client.get(f"/me/badges?business_id={random_id}", headers=headers)
    assert resp_badges_fake.status_code == 200
    assert resp_badges_fake.json() == {"promotions_new": False, "notifications_unread": 0}

    # 2. Inactive business
    assert (await client.get(f"/me/app-content?business_id={inactive_biz.id}", headers=headers)).status_code == 404

    resp_promo_inact = await client.get(f"/me/promotions?business_id={inactive_biz.id}", headers=headers)
    assert resp_promo_inact.status_code == 200
    assert [b["title"] for b in resp_promo_inact.json()["banners"]] == ["Общий баннер POSCENTER"]
    assert resp_promo_inact.json()["offers"] == []

    resp_inact_detail = await client.get(
        f"/me/promotions/{inactive_promo.id}?business_id={inactive_biz.id}", headers=headers
    )
    assert resp_inact_detail.status_code == 404

    resp_notifs_inact = await client.get(f"/me/notifications?business_id={inactive_biz.id}", headers=headers)
    assert resp_notifs_inact.status_code == 200
    assert resp_notifs_inact.json()["items"] == []
    assert resp_notifs_inact.json()["unread_count"] == 0

    resp_badges_inact = await client.get(f"/me/badges?business_id={inactive_biz.id}", headers=headers)
    assert resp_badges_inact.status_code == 200
    assert resp_badges_inact.json() == {"promotions_new": False, "notifications_unread": 0}


@pytest.mark.asyncio
async def test_broadcast_created_before_customer_registration_is_not_visible(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Broadcast of business B created before customer registration is not visible."""
    now = utcnow()
    user, headers = await create_customer(db_session, "+77011002032", registered_ago=timedelta(hours=2))

    biz = Business(name="Супермаркет Керемет", status="active")
    db_session.add(biz)
    await db_session.flush()

    old_broadcast = Notification(
        business_id=biz.id,
        user_id=None,
        title="Старая рассылка",
        body="Была создана до регистрации покупателя",
        created_at=now - timedelta(hours=5),
    )
    fresh_broadcast = Notification(
        business_id=biz.id,
        user_id=None,
        title="Свежая рассылка",
        body="Создана после регистрации",
        created_at=now - timedelta(hours=1),
    )
    db_session.add_all([old_broadcast, fresh_broadcast])
    await db_session.commit()

    resp = await client.get(f"/me/notifications?business_id={biz.id}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Свежая рассылка"
    assert resp.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_without_business_id_mode_remains_unchanged(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Without business_id (shared app):

    Shows promotions/notifications only for businesses where the customer has a card (+ globals).
    """
    user, headers = await create_customer(db_session, "+77011002033")

    biz_with_card = Business(name="Магазин с картой", status="active")
    biz_no_card = Business(name="Магазин без карты", status="active")
    db_session.add_all([biz_with_card, biz_no_card])
    await db_session.flush()

    card = Card(business_id=biz_with_card.id, barcode="88880001", phone=user.phone)
    db_session.add(card)
    await db_session.flush()
    db_session.add(UserCard(user_id=user.id, card_id=card.id, bind_method="phone_auto"))

    promo_card = Promotion(title="Оффер карты", kind="offer", business_id=biz_with_card.id, is_active=True)
    promo_no_card = Promotion(title="Оффер чужой", kind="offer", business_id=biz_no_card.id, is_active=True)
    global_banner = Promotion(title="Общий баннер", kind="banner", business_id=None, is_active=True)
    global_offer = Promotion(title="Общий оффер", kind="offer", business_id=None, is_active=True)

    notif_card = Notification(
        business_id=biz_with_card.id,
        user_id=None,
        title="Рассылка с картой",
        body="Видна",
        created_at=user.created_at + timedelta(hours=1),
    )
    notif_no_card = Notification(
        business_id=biz_no_card.id,
        user_id=None,
        title="Рассылка без карты",
        body="Не видна в общем приложении",
        created_at=user.created_at + timedelta(hours=1),
    )
    db_session.add_all([promo_card, promo_no_card, global_banner, global_offer, notif_card, notif_no_card])
    await db_session.commit()

    # Query without business_id
    resp_promo = await client.get("/me/promotions", headers=headers)
    assert resp_promo.status_code == 200
    offers = [o["title"] for o in resp_promo.json()["offers"]]
    # In shared app mode, global offer + promo_card are visible, but promo_no_card is NOT
    assert "Оффер карты" in offers
    assert "Общий оффер" in offers
    assert "Оффер чужой" not in offers

    resp_notifs = await client.get("/me/notifications", headers=headers)
    assert resp_notifs.status_code == 200
    titles = [n["title"] for n in resp_notifs.json()["items"]]
    assert "Рассылка с картой" in titles
    assert "Рассылка без карты" not in titles


@pytest.mark.asyncio
async def test_customer_with_card_sees_everything_as_before(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Customer with card in business B: personal notifications, badges, and app-content work."""
    user, headers = await create_customer(db_session, "+77011002034")

    biz = Business(name="Супермаркет Керемет", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(business_id=biz.id, barcode="88880002", phone=user.phone)
    db_session.add(card)
    await db_session.flush()
    db_session.add(UserCard(user_id=user.id, card_id=card.id, bind_method="phone_auto"))

    notif_personal = Notification(
        business_id=biz.id,
        user_id=user.id,
        kind="accrual",
        title="Начислено 500 баллов",
        body="Керемет. Баланс: 500 баллов.",
        created_at=user.created_at + timedelta(hours=1),
    )
    db_session.add(notif_personal)
    await db_session.commit()

    resp = await client.get(f"/me/notifications?business_id={biz.id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["title"] == "Начислено 500 баллов"
    assert resp.json()["unread_count"] == 1
