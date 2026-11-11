from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.entities import Card, User, UserCard
from app.schemas.admin import CardSearchRequest, UserSearchRequest
from app.schemas.admin_content import NotificationCreateRequest, PromotionCreateRequest
from tests.test_admin_mvp import authenticated_headers, make_admin, make_business


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_card_and_user_search_request_suffix_and_full() -> None:
    # 4-13 digits barcode
    assert CardSearchRequest(barcode="1234").barcode == "1234"
    assert CardSearchRequest(barcode="00001234").barcode == "00001234"
    assert CardSearchRequest(barcode="0123456789012").barcode == "0123456789012"
    with pytest.raises(ValidationError):
        CardSearchRequest(barcode="123")
    with pytest.raises(ValidationError):
        CardSearchRequest(barcode="12345678901234")

    # Phone search accepts full E.164 normalized AND 4-15 raw digits suffix
    assert CardSearchRequest(phone="+7 (701) 123-45-67").phone == "+77011234567"
    assert CardSearchRequest(phone="4567").phone == "4567"
    assert CardSearchRequest(phone="1234567").phone == "1234567"
    with pytest.raises(ValidationError):
        CardSearchRequest(phone="123")

    assert UserSearchRequest(phone="+7 (701) 123-45-67").phone == "+77011234567"
    assert UserSearchRequest(phone="4567").phone == "4567"
    assert UserSearchRequest(phone="1234567").phone == "1234567"
    with pytest.raises(ValidationError):
        UserSearchRequest(phone="123")


def test_date_4_digit_year_validation() -> None:
    now = utcnow()
    future = now + timedelta(days=2)
    # Valid 4-digit years
    promo = PromotionCreateRequest(title="Test", starts_at=future, ends_at=future + timedelta(days=5))
    assert promo.starts_at.year == future.year

    # Invalid year < 1000
    bad_past_year = datetime(999, 5, 1, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        PromotionCreateRequest(title="Test", starts_at=bad_past_year)

    # Invalid year > 9999 via string parsing
    with pytest.raises(ValidationError):
        PromotionCreateRequest.model_validate({"title": "Test", "starts_at": "10000-01-01T00:00:00Z"})

    # Notification scheduled_at year validation
    with pytest.raises(ValidationError):
        NotificationCreateRequest.model_validate(
            {"title": "Note", "body": "Body", "scheduled_at": "10000-01-01T00:00:00Z"}
        )


@pytest.mark.asyncio
async def test_card_search_by_last_4_digits_and_leading_zeros(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    business = await make_business(db_session, "Search Mart")
    admin = await make_admin(db_session, "business_manager", business.id, "mart.mgr")

    # Add 2 cards: one starting with 0000 ending in 4321, one other
    card1 = Card(
        business_id=business.id,
        barcode="0000123454321",
        phone="+77011114321",
        balance=Decimal("150.0000"),
        is_blocked=False,
    )
    card2 = Card(
        business_id=business.id,
        barcode="9999000004321",
        phone="+77022224321",
        balance=Decimal("200.0000"),
        is_blocked=False,
    )
    card3 = Card(
        business_id=business.id,
        barcode="1111222233334",
        phone="+77033339999",
        balance=Decimal("50.0000"),
        is_blocked=False,
    )
    db_session.add_all([card1, card2, card3])
    await db_session.flush()

    auth_headers = await authenticated_headers(db_session, admin)

    # 1. Search by full barcode with leading zeros preserved
    resp = await admin_client.post(
        "/admin/cards/search",
        json={"barcode": "0000123454321"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["barcode"] == "0000123454321"

    # 2. Search by last 4 digits ("4321") - MUST RETURN ALL MATCHES, never auto-select
    resp = await admin_client.post(
        "/admin/cards/search",
        json={"barcode": "4321"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    barcodes = {it["barcode"] for it in items}
    assert barcodes == {"0000123454321", "9999000004321"}

    # 3. Search by last 4 digits of phone ("4321")
    resp = await admin_client.post(
        "/admin/cards/search",
        json={"phone": "4321"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2


@pytest.mark.asyncio
async def test_users_default_list_and_search_by_suffix(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    biz_a = await make_business(db_session, "Biz A")
    biz_b = await make_business(db_session, "Biz B")

    admin_a = await make_admin(db_session, "business_manager", biz_a.id, "mgr.a")

    # Users in system
    user1 = User(phone="+77011234567", language="ru")
    user2 = User(phone="+77029874567", language="kk")
    user3 = User(phone="+77035559999", language="ru")
    db_session.add_all([user1, user2, user3])
    await db_session.flush()

    # Cards in Biz A for user1 and user2
    card_a1 = Card(business_id=biz_a.id, barcode="1000001", phone=user1.phone, balance=Decimal(10))
    card_a2 = Card(business_id=biz_a.id, barcode="1000002", phone=user2.phone, balance=Decimal(20))
    # Card in Biz B for user3 only
    card_b1 = Card(business_id=biz_b.id, barcode="2000001", phone=user3.phone, balance=Decimal(30))
    db_session.add_all([card_a1, card_a2, card_b1])
    await db_session.flush()

    uc1 = UserCard(user_id=user1.id, card_id=card_a1.id)
    uc2 = UserCard(user_id=user2.id, card_id=card_a2.id)
    uc3 = UserCard(user_id=user3.id, card_id=card_b1.id)
    db_session.add_all([uc1, uc2, uc3])
    await db_session.flush()

    auth_headers = await authenticated_headers(db_session, admin_a)

    # 1. GET /admin/users default list: MUST show user1 and user2, but NOT user3 (tenant isolation)
    list_resp = await admin_client.get("/admin/users", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data["items"]) == 2
    user_ids = {it["id"] for it in data["items"]}
    assert str(user1.id) in user_ids
    assert str(user2.id) in user_ids
    assert str(user3.id) not in user_ids

    # 2. PII masking preserved: phone_masked should mask inner digits
    for item in data["items"]:
        assert item["phone_masked"] is not None
        assert "•" in item["phone_masked"] or "*" in item["phone_masked"]

    # 3. POST /admin/users/search by last 4 digits ("4567")
    search_resp = await admin_client.post(
        "/admin/users/search",
        json={"phone": "4567"},
        headers=auth_headers,
    )
    assert search_resp.status_code == 200
    search_items = search_resp.json()["items"]
    assert len(search_items) == 2

    # 4. Search by full phone
    search_full = await admin_client.post(
        "/admin/users/search",
        json={"phone": "+7 (701) 123-45-67"},
        headers=auth_headers,
    )
    assert search_full.status_code == 200
    assert len(search_full.json()["items"]) == 1
    assert search_full.json()["items"][0]["id"] == str(user1.id)


@pytest.mark.asyncio
async def test_dashboard_date_4_digit_year(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    business = await make_business(db_session, "Dash Mart")
    admin = await make_admin(db_session, "business_manager", business.id, "dash.mgr")
    auth_headers = await authenticated_headers(db_session, admin)

    # Valid 4-digit year query
    valid_resp = await admin_client.get(
        "/admin/dashboard?from=2026-10-01T00:00:00Z&to=2026-10-15T23:59:59Z",
        headers=auth_headers,
    )
    assert valid_resp.status_code == 200

    # Invalid year < 1000
    bad_resp1 = await admin_client.get(
        "/admin/dashboard?from=0999-10-01T00:00:00Z&to=2026-10-15T23:59:59Z",
        headers=auth_headers,
    )
    assert bad_resp1.status_code == 422
    assert bad_resp1.json()["error"]["code"] == "ADMIN_INVALID_PERIOD"

    # Invalid year > 9999 or out-of-range ISO date triggers 422
    bad_resp2 = await admin_client.get(
        "/admin/dashboard?from=2026-10-01T00:00:00Z&to=10000-01-01T00:00:00Z",
        headers=auth_headers,
    )
    assert bad_resp2.status_code == 422
