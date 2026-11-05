"""Integration tests for Customer API multi-tenant business filtering (Task I-backend)."""
import uuid
from datetime import timedelta
from decimal import Decimal

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
    db: AsyncSession, phone: str = "+77017770011"
) -> tuple[User, dict[str, str]]:
    user = User(phone=phone, language="ru", created_at=utcnow() - timedelta(days=2))
    db.add(user)
    await db.flush()
    session = AuthSession(
        user_id=user.id,
        device_id="dev-multi",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(session)
    await db.commit()
    token = create_access_token(user_id=user.id, session_id=session.id)
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_cards_with_and_without_business_id(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    user, headers = await create_customer(db_session, "+77017770022")

    # Business A (Keremet) with card A
    biz_a = Business(name="Керемет", android_app_id="kz.cashbackone.keremet", status="active")
    # Business B (Magnum) with card B
    biz_b = Business(name="Magnum", android_app_id=None, status="active")
    # Business C (Empty for user)
    biz_c = Business(name="Empty Shop", status="active")
    db_session.add_all([biz_a, biz_b, biz_c])
    await db_session.flush()

    card_a = Card(business_id=biz_a.id, barcode="11110001", phone=user.phone, balance=Decimal(100))
    card_b = Card(business_id=biz_b.id, barcode="22220002", phone=user.phone, balance=Decimal(200))
    db_session.add_all([card_a, card_b])
    await db_session.flush()

    db_session.add_all([
        UserCard(user_id=user.id, card_id=card_a.id, bind_method="phone_auto"),
        UserCard(user_id=user.id, card_id=card_b.id, bind_method="phone_auto"),
    ])
    await db_session.commit()

    # 1. Without business_id -> returns both cards
    resp_all = await client.get("/me/cards", headers=headers)
    assert resp_all.status_code == 200
    all_data = resp_all.json()
    assert len(all_data) == 2
    returned_barcodes = {c["barcode"] for c in all_data}
    assert returned_barcodes == {"11110001", "22220002"}

    # 2. With business_id=biz_a.id -> returns only card A
    resp_a = await client.get(f"/me/cards?business_id={biz_a.id}", headers=headers)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert len(data_a) == 1
    assert data_a[0]["barcode"] == "11110001"
    assert data_a[0]["business"]["id"] == str(biz_a.id)

    # 3. With business_id=biz_c.id (no card) -> returns empty list (not 404)
    resp_c = await client.get(f"/me/cards?business_id={biz_c.id}", headers=headers)
    assert resp_c.status_code == 200
    assert resp_c.json() == []


@pytest.mark.asyncio
async def test_bind_card_foreign_business_returns_404_not_found(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    user, headers = await create_customer(db_session, "+77017770033")

    biz_keremet = Business(name="Керемет", android_app_id="kz.cashbackone.keremet", status="active")
    biz_other = Business(name="Другой Магазин", status="active")
    db_session.add_all([biz_keremet, biz_other])
    await db_session.flush()

    # Card belongs to biz_keremet
    card = Card(
        business_id=biz_keremet.id,
        barcode="33330001",
        phone=user.phone,
        balance=Decimal(50),
    )
    db_session.add(card)
    await db_session.commit()

    # 1. Attempt to bind to biz_other with business_id in query param -> 404 CARD_NOT_FOUND
    resp_wrong_query = await client.post(
        f"/me/cards/bind?business_id={biz_other.id}",
        headers=headers,
        json={"barcode": "33330001"},
    )
    assert resp_wrong_query.status_code == 404
    assert resp_wrong_query.json()["error"]["code"] == "CARD_NOT_FOUND"

    # 2. Attempt to bind with wrong business_id in body -> 404 CARD_NOT_FOUND
    resp_wrong_body = await client.post(
        "/me/cards/bind",
        headers=headers,
        json={"barcode": "33330001", "business_id": str(biz_other.id)},
    )
    assert resp_wrong_body.status_code == 404
    assert resp_wrong_body.json()["error"]["code"] == "CARD_NOT_FOUND"

    # 3. Bind with correct business_id in query param -> succeeds 200
    resp_correct = await client.post(
        f"/me/cards/bind?business_id={biz_keremet.id}",
        headers=headers,
        json={"barcode": "33330001"},
    )
    assert resp_correct.status_code == 200
    assert resp_correct.json()["barcode"] == "33330001"
    assert resp_correct.json()["business"]["id"] == str(biz_keremet.id)


@pytest.mark.asyncio
async def test_promotions_and_detail_with_and_without_business_id(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    user, headers = await create_customer(db_session, "+77017770044")

    biz_a = Business(name="Магазин А", status="active")
    biz_b = Business(name="Магазин Б", status="active")
    biz_c = Business(name="Магазин В", status="active")
    db_session.add_all([biz_a, biz_b, biz_c])
    await db_session.flush()

    # User has cards in A and B
    card_a = Card(business_id=biz_a.id, barcode="44440001", phone=user.phone)
    card_b = Card(business_id=biz_b.id, barcode="44440002", phone=user.phone)
    db_session.add_all([card_a, card_b])
    await db_session.flush()

    db_session.add_all([
        UserCard(user_id=user.id, card_id=card_a.id, bind_method="phone_auto"),
        UserCard(user_id=user.id, card_id=card_b.id, bind_method="phone_auto"),
    ])

    promo_global = Promotion(title="Общая акция", kind="offer", business_id=None, is_active=True)
    promo_a = Promotion(title="Акция А", kind="offer", business_id=biz_a.id, is_active=True)
    promo_b = Promotion(title="Акция Б", kind="offer", business_id=biz_b.id, is_active=True)
    db_session.add_all([promo_global, promo_a, promo_b])
    await db_session.commit()

    # 1. GET /me/promotions without business_id -> all visible promotions
    resp_all = await client.get("/me/promotions", headers=headers)
    assert resp_all.status_code == 200
    all_titles = {o["title"] for o in resp_all.json()["offers"]}
    assert all_titles == {"Общая акция", "Акция А", "Акция Б"}

    # 2. GET /me/promotions with business_id=biz_a.id -> only promo A
    resp_a = await client.get(f"/me/promotions?business_id={biz_a.id}", headers=headers)
    assert resp_a.status_code == 200
    a_titles = {o["title"] for o in resp_a.json()["offers"]}
    assert a_titles == {"Акция А"}

    # 3. GET /me/promotions with business_id=biz_c.id (no card) -> empty list (not 404)
    resp_c = await client.get(f"/me/promotions?business_id={biz_c.id}", headers=headers)
    assert resp_c.status_code == 200
    assert resp_c.json()["banners"] == []
    assert resp_c.json()["offers"] == []
    assert resp_c.json()["has_new"] is False

    # 4. Detail GET /me/promotions/{id} without business_id
    detail_resp = await client.get(f"/me/promotions/{promo_a.id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Акция А"

    # 5. Detail GET /me/promotions/{id} with matching business_id
    detail_resp_match = await client.get(
        f"/me/promotions/{promo_a.id}?business_id={biz_a.id}", headers=headers
    )
    assert detail_resp_match.status_code == 200
    assert detail_resp_match.json()["title"] == "Акция А"

    # 6. Detail GET /me/promotions/{id} with foreign business_id -> 404 PROMOTION_NOT_FOUND
    detail_resp_foreign = await client.get(
        f"/me/promotions/{promo_a.id}?business_id={biz_b.id}", headers=headers
    )
    assert detail_resp_foreign.status_code == 404
    assert detail_resp_foreign.json()["error"]["code"] == "PROMOTION_NOT_FOUND"

    # 7. Detail GET /me/promotions/{id} with business where user has no card -> 404
    detail_resp_no_card = await client.get(
        f"/me/promotions/{promo_a.id}?business_id={biz_c.id}", headers=headers
    )
    assert detail_resp_no_card.status_code == 404

    # 8. POST /me/promotions/seen with business_id
    seen_resp = await client.post(f"/me/promotions/seen?business_id={biz_a.id}", headers=headers)
    assert seen_resp.status_code == 204


@pytest.mark.asyncio
async def test_notifications_and_badges_with_and_without_business_id(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    user, headers = await create_customer(db_session, "+77017770055")

    biz_a = Business(name="Магазин А", status="active")
    biz_b = Business(name="Магазин Б", status="active")
    biz_c = Business(name="Магазин В", status="active")
    db_session.add_all([biz_a, biz_b, biz_c])
    await db_session.flush()

    card_a = Card(business_id=biz_a.id, barcode="55550001", phone=user.phone)
    card_b = Card(business_id=biz_b.id, barcode="55550002", phone=user.phone)
    db_session.add_all([card_a, card_b])
    await db_session.flush()

    db_session.add_all([
        UserCard(user_id=user.id, card_id=card_a.id, bind_method="phone_auto"),
        UserCard(user_id=user.id, card_id=card_b.id, bind_method="phone_auto"),
    ])

    notif_a = Notification(
        business_id=biz_a.id,
        user_id=user.id,
        kind="accrual",
        title="Начислено в А",
        body="Вам начислено 100 баллов в А",
    )
    notif_b = Notification(
        business_id=biz_b.id,
        user_id=user.id,
        kind="accrual",
        title="Начислено в Б",
        body="Вам начислено 200 баллов в Б",
    )
    promo_a = Promotion(title="Оффер А", kind="offer", business_id=biz_a.id, is_active=True)
    db_session.add_all([notif_a, notif_b, promo_a])
    await db_session.commit()

    # 1. Notifications without business_id -> all notifications
    resp_all_notifs = await client.get("/me/notifications", headers=headers)
    assert resp_all_notifs.status_code == 200
    titles = {n["title"] for n in resp_all_notifs.json()["items"]}
    assert titles == {"Начислено в А", "Начислено в Б"}

    # 2. Notifications with business_id=biz_a.id -> only biz_a notifications
    resp_a_notifs = await client.get(
        f"/me/notifications?business_id={biz_a.id}", headers=headers
    )
    assert resp_a_notifs.status_code == 200
    a_titles = {n["title"] for n in resp_a_notifs.json()["items"]}
    assert a_titles == {"Начислено в А"}
    assert resp_a_notifs.json()["unread_count"] == 1

    # 3. Notifications with business_id=biz_c.id (no card) -> empty list (not 404)
    resp_c_notifs = await client.get(
        f"/me/notifications?business_id={biz_c.id}", headers=headers
    )
    assert resp_c_notifs.status_code == 200
    assert resp_c_notifs.json()["items"] == []
    assert resp_c_notifs.json()["unread_count"] == 0

    # 4. POST /me/notifications/read with business_id -> 204
    read_resp = await client.post(
        f"/me/notifications/read?business_id={biz_a.id}", headers=headers
    )
    assert read_resp.status_code == 204

    # 5. Badges without business_id
    badges_all = await client.get("/me/badges", headers=headers)
    assert badges_all.status_code == 200
    assert badges_all.json()["promotions_new"] is True

    # 6. Badges with business_id=biz_a.id
    badges_a = await client.get(f"/me/badges?business_id={biz_a.id}", headers=headers)
    assert badges_a.status_code == 200
    assert badges_a.json()["promotions_new"] is True

    # 7. Badges with business_id=biz_b.id (no promo for b)
    badges_b = await client.get(f"/me/badges?business_id={biz_b.id}", headers=headers)
    assert badges_b.status_code == 200
    assert badges_b.json()["promotions_new"] is False

    # 8. Badges with business_id=biz_c.id (no card in c)
    badges_c = await client.get(f"/me/badges?business_id={biz_c.id}", headers=headers)
    assert badges_c.status_code == 200
    assert badges_c.json() == {"promotions_new": False, "notifications_unread": 0}
