"""Integration tests for platform banners in customer apps (Task 2026-11-06)."""
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
    Card,
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
    db: AsyncSession, phone: str = "+77017770099"
) -> tuple[User, dict[str, str]]:
    user = User(phone=phone, language="ru", created_at=utcnow() - timedelta(days=2))
    db.add(user)
    await db.flush()
    session = AuthSession(
        user_id=user.id,
        device_id="dev-platform-banners",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(session)
    await db.commit()
    token = create_access_token(user_id=user.id, session_id=session.id)
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_platform_banners_without_card(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Customer without card in business B:

    - /me/promotions?business_id=B -> only active platform banners;
    - offers of B and banners of B are not visible;
    - GET /me/promotions/{global_banner} -> 200 OK;
    - GET /me/promotions/{banner_B} -> 404;
    - GET /me/promotions/{offer_B} -> 404.
    """
    _user, headers = await create_customer(db_session, "+77011112233")

    biz_b = Business(name="Супермаркет Керемет", status="active")
    db_session.add(biz_b)
    await db_session.flush()

    # Platform banner (business_id is None, kind='banner')
    global_banner = Promotion(
        title="Общий баннер POSCENTER",
        kind="banner",
        business_id=None,
        is_active=True,
        sort_order=10,
    )
    # Platform offer (business_id is None, kind='offer') - should NOT be shown in client app
    global_offer = Promotion(
        title="Общая акция POSCENTER",
        kind="offer",
        business_id=None,
        is_active=True,
    )
    # Banners and offers of business B
    banner_b = Promotion(
        title="Баннер Керемет",
        kind="banner",
        business_id=biz_b.id,
        is_active=True,
        sort_order=5,
    )
    offer_b = Promotion(
        title="Скидка Керемет",
        kind="offer",
        business_id=biz_b.id,
        is_active=True,
    )
    db_session.add_all([global_banner, global_offer, banner_b, offer_b])
    await db_session.commit()

    # User has NO card in biz_b
    resp = await client.get(f"/me/promotions?business_id={biz_b.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Only active global banner is returned
    banner_titles = [b["title"] for b in data["banners"]]
    assert banner_titles == ["Общий баннер POSCENTER"]
    assert data["offers"] == []
    assert data["has_new"] is False

    # GET /me/promotions/{global_banner.id}?business_id=biz_b.id -> 200 OK
    resp_gb = await client.get(
        f"/me/promotions/{global_banner.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_gb.status_code == 200
    assert resp_gb.json()["title"] == "Общий баннер POSCENTER"

    # GET /me/promotions/{banner_b.id}?business_id=biz_b.id -> 404
    resp_bb = await client.get(
        f"/me/promotions/{banner_b.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_bb.status_code == 404
    assert resp_bb.json()["error"]["code"] == "PROMOTION_NOT_FOUND"

    # GET /me/promotions/{offer_b.id}?business_id=biz_b.id -> 404
    resp_ob = await client.get(
        f"/me/promotions/{offer_b.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_ob.status_code == 404
    assert resp_ob.json()["error"]["code"] == "PROMOTION_NOT_FOUND"

    # GET /me/promotions/{global_offer.id}?business_id=biz_b.id -> 404
    resp_go = await client.get(
        f"/me/promotions/{global_offer.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_go.status_code == 404
    assert resp_go.json()["error"]["code"] == "PROMOTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_platform_banners_with_card_and_ordering(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Customer with card in business B:

    - Banners of B and global banners returned together in sort_order;
    - Offers only of B (global offer not shown);
    - Banner of another business C is NOT visible.
    """
    user, headers = await create_customer(db_session, "+77011114455")

    biz_b = Business(name="Супермаркет Керемет", status="active")
    biz_c = Business(name="Другой магазин C", status="active")
    db_session.add_all([biz_b, biz_c])
    await db_session.flush()

    # User has card in biz_b and card in biz_c
    card_b = Card(business_id=biz_b.id, barcode="88880001", phone=user.phone)
    card_c = Card(business_id=biz_c.id, barcode="88880002", phone=user.phone)
    db_session.add_all([card_b, card_c])
    await db_session.flush()

    db_session.add_all([
        UserCard(user_id=user.id, card_id=card_b.id, bind_method="phone_auto"),
        UserCard(user_id=user.id, card_id=card_c.id, bind_method="phone_auto"),
    ])

    # Global banner 1 (sort_order = 20)
    global_banner_1 = Promotion(
        title="Общий баннер 20",
        kind="banner",
        business_id=None,
        is_active=True,
        sort_order=20,
    )
    # Global banner 2 (sort_order = 5)
    global_banner_2 = Promotion(
        title="Общий баннер 5",
        kind="banner",
        business_id=None,
        is_active=True,
        sort_order=5,
    )
    # Global offer
    global_offer = Promotion(
        title="Общий оффер",
        kind="offer",
        business_id=None,
        is_active=True,
    )

    # Business B banner (sort_order = 10)
    banner_b = Promotion(
        title="Баннер Керемет 10",
        kind="banner",
        business_id=biz_b.id,
        is_active=True,
        sort_order=10,
    )
    # Business B offer
    offer_b = Promotion(
        title="Оффер Керемет",
        kind="offer",
        business_id=biz_b.id,
        is_active=True,
    )

    # Business C banner (sort_order = 1)
    banner_c = Promotion(
        title="Баннер Магазин C",
        kind="banner",
        business_id=biz_c.id,
        is_active=True,
        sort_order=1,
    )
    # Business C offer
    offer_c = Promotion(
        title="Оффер Магазин C",
        kind="offer",
        business_id=biz_c.id,
        is_active=True,
    )

    db_session.add_all([
        global_banner_1,
        global_banner_2,
        global_offer,
        banner_b,
        offer_b,
        banner_c,
        offer_c,
    ])
    await db_session.commit()

    # Query with business_id=biz_b.id
    resp = await client.get(f"/me/promotions?business_id={biz_b.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Banners should include:
    # 1. global_banner_2 (sort_order=5)
    # 2. banner_b (sort_order=10)
    # 3. global_banner_1 (sort_order=20)
    # banner_c MUST NOT be present!
    banner_titles = [b["title"] for b in data["banners"]]
    assert banner_titles == ["Общий баннер 5", "Баннер Керемет 10", "Общий баннер 20"]

    # Offers should include only offer_b
    offer_titles = [o["title"] for o in data["offers"]]
    assert offer_titles == ["Оффер Керемет"]
    assert data["has_new"] is True

    # Detail endpoints:
    # 1. Banner B -> 200 OK
    resp_bb = await client.get(
        f"/me/promotions/{banner_b.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_bb.status_code == 200
    assert resp_bb.json()["title"] == "Баннер Керемет 10"

    # 2. Global banner -> 200 OK
    resp_gb = await client.get(
        f"/me/promotions/{global_banner_1.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_gb.status_code == 200
    assert resp_gb.json()["title"] == "Общий баннер 20"

    # 3. Banner C -> 404 NOT FOUND
    resp_bc = await client.get(
        f"/me/promotions/{banner_c.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_bc.status_code == 404
    assert resp_bc.json()["error"]["code"] == "PROMOTION_NOT_FOUND"

    # 4. Global offer -> 404 NOT FOUND
    resp_go = await client.get(
        f"/me/promotions/{global_offer.id}?business_id={biz_b.id}", headers=headers
    )
    assert resp_go.status_code == 404


@pytest.mark.asyncio
async def test_inactive_and_expired_global_banners_not_visible(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """Inactive, expired, or future platform banners must NOT be visible."""
    _user, headers = await create_customer(db_session, "+77011116677")
    now = utcnow()

    biz_b = Business(name="Супермаркет Керемет", status="active")
    db_session.add(biz_b)
    await db_session.flush()

    active_global_banner = Promotion(
        title="Активный баннер",
        kind="banner",
        business_id=None,
        is_active=True,
    )
    inactive_global_banner = Promotion(
        title="Неактивный баннер",
        kind="banner",
        business_id=None,
        is_active=False,
    )
    expired_global_banner = Promotion(
        title="Просроченный баннер",
        kind="banner",
        business_id=None,
        is_active=True,
        ends_at=now - timedelta(days=1),
    )
    future_global_banner = Promotion(
        title="Будущий баннер",
        kind="banner",
        business_id=None,
        is_active=True,
        starts_at=now + timedelta(days=1),
    )
    db_session.add_all([
        active_global_banner,
        inactive_global_banner,
        expired_global_banner,
        future_global_banner,
    ])
    await db_session.commit()

    resp = await client.get(f"/me/promotions?business_id={biz_b.id}", headers=headers)
    assert resp.status_code == 200
    banner_titles = [b["title"] for b in resp.json()["banners"]]
    assert banner_titles == ["Активный баннер"]

    # Detail queries for inactive/expired/future return 404
    for promo in [inactive_global_banner, expired_global_banner, future_global_banner]:
        r = await client.get(
            f"/me/promotions/{promo.id}?business_id={biz_b.id}", headers=headers
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "PROMOTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_nonexistent_or_inactive_business_returns_global_banners(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """When business does not exist or is inactive, returns active platform banners

    without 404 or 500 error.
    """
    user, headers = await create_customer(db_session, "+77011118899")

    active_global_banner = Promotion(
        title="Общий баннер для всех",
        kind="banner",
        business_id=None,
        is_active=True,
    )
    inactive_biz = Business(name="Закрытый магазин", status="inactive")
    db_session.add_all([active_global_banner, inactive_biz])
    await db_session.flush()

    card = Card(business_id=inactive_biz.id, barcode="99990001", phone=user.phone)
    db_session.add(card)
    await db_session.flush()
    db_session.add(UserCard(user_id=user.id, card_id=card.id, bind_method="phone_auto"))
    await db_session.commit()

    # 1. Non-existent business UUID
    random_uuid = uuid.uuid4()
    resp_none = await client.get(f"/me/promotions?business_id={random_uuid}", headers=headers)
    assert resp_none.status_code == 200
    assert len(resp_none.json()["banners"]) == 1
    assert resp_none.json()["banners"][0]["title"] == "Общий баннер для всех"
    assert resp_none.json()["offers"] == []

    # 2. Inactive business
    resp_inact = await client.get(f"/me/promotions?business_id={inactive_biz.id}", headers=headers)
    assert resp_inact.status_code == 200
    assert len(resp_inact.json()["banners"]) == 1
    assert resp_inact.json()["banners"][0]["title"] == "Общий баннер для всех"
    assert resp_inact.json()["offers"] == []


@pytest.mark.asyncio
async def test_without_business_id_shows_all_promotions_and_global_offers(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    """When business_id is omitted (backwards-compatibility / shared app):

    - Shows active promotions for all customer businesses;
    - Shows global banners AND global offers.
    """
    user, headers = await create_customer(db_session, "+77011110011")

    biz = Business(name="Магазин Партнер", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(business_id=biz.id, barcode="77770001", phone=user.phone)
    db_session.add(card)
    await db_session.flush()
    db_session.add(UserCard(user_id=user.id, card_id=card.id, bind_method="phone_auto"))

    gb = Promotion(title="Общий баннер", kind="banner", business_id=None, is_active=True)
    go = Promotion(title="Общий оффер", kind="offer", business_id=None, is_active=True)
    bb = Promotion(title="Баннер Партнера", kind="banner", business_id=biz.id, is_active=True)
    bo = Promotion(title="Оффер Партнера", kind="offer", business_id=biz.id, is_active=True)
    db_session.add_all([gb, go, bb, bo])
    await db_session.commit()

    resp = await client.get("/me/promotions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    banner_titles = {b["title"] for b in data["banners"]}
    assert banner_titles == {"Общий баннер", "Баннер Партнера"}

    offer_titles = {o["title"] for o in data["offers"]}
    assert offer_titles == {"Общий оффер", "Оффер Партнера"}
