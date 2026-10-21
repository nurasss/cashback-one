import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_types import AdminRole
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser
from app.models.entities import Business, Card, User, UserCard
from app.services.admin_security import (
    admin_refresh_token_hash,
    create_admin_access_token,
    generate_admin_refresh_token,
    hash_admin_password,
    normalize_admin_login,
)
from app.services.rate_limiter import _test_limiter, get_rate_limiter

ORIGIN_HEADERS = {"Origin": "https://admin.test", "X-Admin-Request": "1"}
TEST_PASSWORD = "test-fixture-passphrase-123"


@pytest.fixture(autouse=True)
def reset_admin_test_limiter() -> None:
    _test_limiter.reset()


@pytest.fixture
async def admin_client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
        yield client
    app.dependency_overrides.clear()


async def make_business(db: AsyncSession, name: str) -> Business:
    business = Business(name=name, status="active", colors={"primary_color": "#155d4a"}, barcode_prefixes=["012"])
    db.add(business)
    await db.flush()
    return business


async def make_admin(db: AsyncSession, role: AdminRole, business_id: uuid.UUID | None, login: str) -> AdminUser:
    admin = AdminUser(
        login=normalize_admin_login(login),
        password_hash=hash_admin_password(TEST_PASSWORD),
        role=role,
        business_id=business_id,
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    return admin


async def authenticated_headers(db: AsyncSession, admin: AdminUser) -> dict[str, str]:
    session = AdminSession(
        admin_user_id=admin.id,
        refresh_token_hash=admin_refresh_token_hash(generate_admin_refresh_token()),
        expires_at=datetime.now(UTC).replace(microsecond=0) + timedelta(hours=8),
    )
    db.add(session)
    await db.flush()
    return {**ORIGIN_HEADERS, "Authorization": f"Bearer {create_admin_access_token(admin.id, session.id)}"}


async def make_card(
    db: AsyncSession,
    business_id: uuid.UUID,
    barcode: str,
    phone: str | None = None,
    balance: Decimal = Decimal("125.5000"),
    is_blocked: bool = False,
    updated_at: datetime | None = None,
) -> Card:
    card = Card(
        business_id=business_id,
        barcode=barcode,
        phone=phone,
        full_name="Fixture Customer",
        balance=balance,
        is_blocked=is_blocked,
    )
    if updated_at is not None:
        card.updated_at = updated_at
    db.add(card)
    await db.flush()
    return card


@pytest.mark.asyncio
async def test_admin_cards_list_limit_and_offset_bounds(admin_client: AsyncClient, db_session: AsyncSession):
    business = await make_business(db_session, "Limit Test Business")
    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.bounds")
    headers = await authenticated_headers(db_session, superadmin)

    # 1. Default pagination: limit=25, offset=0
    res = await admin_client.get("/admin/cards", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["limit"] == 25
    assert data["offset"] == 0
    assert data["items"] == []
    assert data["has_more"] is False

    # 2. Limit boundary checks: max allowed limit is 30
    res_30 = await admin_client.get("/admin/cards?limit=30", headers=headers)
    assert res_30.status_code == 200
    assert res_30.json()["limit"] == 30

    # Limit > 30 must fail validation with 422
    res_31 = await admin_client.get("/admin/cards?limit=31", headers=headers)
    assert res_31.status_code == 422

    res_100 = await admin_client.get("/admin/cards?limit=100", headers=headers)
    assert res_100.status_code == 422

    # Limit < 1 must fail validation with 422
    res_0 = await admin_client.get("/admin/cards?limit=0", headers=headers)
    assert res_0.status_code == 422

    # Negative offset must fail validation with 422
    res_neg = await admin_client.get("/admin/cards?offset=-1", headers=headers)
    assert res_neg.status_code == 422

    # Offset > 100_000 must fail validation with 422
    res_huge = await admin_client.get("/admin/cards?offset=100001", headers=headers)
    assert res_huge.status_code == 422

    # Existing POST /admin/cards/search must still allow limit up to 100
    await make_card(db_session, business.id, "0123456789012", "+77001234567")
    search_res = await admin_client.post(
        "/admin/cards/search?limit=100",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert search_res.status_code == 200
    assert search_res.json()["limit"] == 100


@pytest.mark.asyncio
async def test_admin_cards_list_pagination_0_cards(admin_client: AsyncClient, db_session: AsyncSession):
    await make_business(db_session, "Empty Business")
    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.empty")
    headers = await authenticated_headers(db_session, superadmin)

    res = await admin_client.get("/admin/cards", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["limit"] == 25
    assert data["offset"] == 0
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_admin_cards_list_pagination_25_cards(admin_client: AsyncClient, db_session: AsyncSession):
    business = await make_business(db_session, "25 Cards Business")
    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.25")
    headers = await authenticated_headers(db_session, superadmin)

    for i in range(25):
        await make_card(db_session, business.id, f"{1000000000 + i}")

    # Exactly 25 cards: first page must have 25 items and has_more=False
    res = await admin_client.get("/admin/cards?limit=25&offset=0", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 25
    assert data["has_more"] is False
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_admin_cards_list_pagination_26_cards_no_overlap(admin_client: AsyncClient, db_session: AsyncSession):
    business = await make_business(db_session, "26 Cards Business")
    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.26")
    headers = await authenticated_headers(db_session, superadmin)

    base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
    for i in range(26):
        await make_card(
            db_session,
            business.id,
            f"000000{100000 + i}",
            updated_at=base_time + timedelta(minutes=i),
        )

    # Page 1: limit 25, offset 0 -> 25 items, has_more=True
    res1 = await admin_client.get("/admin/cards?limit=25&offset=0", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["items"]) == 25
    assert data1["has_more"] is True

    # Page 2: limit 25, offset 25 -> 1 item, has_more=False (last page)
    res2 = await admin_client.get("/admin/cards?limit=25&offset=25", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 1
    assert data2["has_more"] is False

    # Check zero intersection of items
    page1_ids = {item["id"] for item in data1["items"]}
    page2_ids = {item["id"] for item in data2["items"]}
    assert len(page1_ids) == 25
    assert len(page2_ids) == 1
    assert page1_ids.isdisjoint(page2_ids)

    # Leading zeros preserved
    assert all(item["barcode"].startswith("000000") for item in data1["items"])
    assert all(item["barcode"].startswith("000000") for item in data2["items"])


@pytest.mark.asyncio
async def test_admin_cards_list_pagination_over_50_cards(admin_client: AsyncClient, db_session: AsyncSession):
    business = await make_business(db_session, "55 Cards Business")
    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.55")
    headers = await authenticated_headers(db_session, superadmin)

    base_time = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    created_cards = []
    for i in range(55):
        c = await make_card(
            db_session,
            business.id,
            f"CARD{i:08d}",
            updated_at=base_time + timedelta(seconds=i),
        )
        created_cards.append(c)

    # Page 1: 25 items, has_more=True
    res1 = await admin_client.get("/admin/cards?limit=25&offset=0", headers=headers)
    assert res1.status_code == 200
    d1 = res1.json()
    assert len(d1["items"]) == 25
    assert d1["has_more"] is True

    # Page 2: 25 items, has_more=True
    res2 = await admin_client.get("/admin/cards?limit=25&offset=25", headers=headers)
    assert res2.status_code == 200
    d2 = res2.json()
    assert len(d2["items"]) == 25
    assert d2["has_more"] is True

    # Page 3: 5 items, has_more=False
    res3 = await admin_client.get("/admin/cards?limit=25&offset=50", headers=headers)
    assert res3.status_code == 200
    d3 = res3.json()
    assert len(d3["items"]) == 5
    assert d3["has_more"] is False

    # Disjoint check
    ids1 = {x["id"] for x in d1["items"]}
    ids2 = {x["id"] for x in d2["items"]}
    ids3 = {x["id"] for x in d3["items"]}
    assert len(ids1) == 25
    assert len(ids2) == 25
    assert len(ids3) == 5
    assert ids1.isdisjoint(ids2)
    assert ids1.isdisjoint(ids3)
    assert ids2.isdisjoint(ids3)
    assert len(ids1 | ids2 | ids3) == 55

    # Check stable sorting: newest first (i=54 was the most recent updated_at)
    assert d1["items"][0]["barcode"] == "CARD00000054"


@pytest.mark.asyncio
async def test_admin_cards_list_manager_scope_and_superadmin_filter(
    admin_client: AsyncClient, db_session: AsyncSession
):
    business_a = await make_business(db_session, "Business Alpha")
    business_b = await make_business(db_session, "Business Beta")

    # Create 3 cards for business A and 2 cards for business B
    user_a = User(phone="+77001112233", language="ru")
    db_session.add(user_a)
    await db_session.flush()

    card_a1 = await make_card(db_session, business_a.id, "000100000001", user_a.phone)
    await make_card(db_session, business_a.id, "000100000002")
    await make_card(db_session, business_a.id, "000100000003")

    user_card = UserCard(user_id=user_a.id, card_id=card_a1.id, bind_method="manual_barcode")
    db_session.add(user_card)
    await db_session.flush()

    await make_card(db_session, business_b.id, "000200000001")
    await make_card(db_session, business_b.id, "000200000002")

    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.scope")
    manager_a = await make_admin(db_session, "business_manager", business_a.id, "manager.alpha")

    s_headers = await authenticated_headers(db_session, superadmin)
    m_headers = await authenticated_headers(db_session, manager_a)

    # 1. Superadmin without business_id: sees all 5 cards across businesses
    s_all = await admin_client.get("/admin/cards", headers=s_headers)
    assert s_all.status_code == 200
    assert len(s_all.json()["items"]) == 5

    # 2. Superadmin with business_id=A: sees only 3 cards
    s_filt_a = await admin_client.get(f"/admin/cards?business_id={business_a.id}", headers=s_headers)
    assert s_filt_a.status_code == 200
    items_a = s_filt_a.json()["items"]
    assert len(items_a) == 3
    assert all(it["business_id"] == str(business_a.id) for it in items_a)

    # Check fields in card item
    item_bound = next(it for it in items_a if it["id"] == str(card_a1.id))
    assert item_bound["barcode"] == "000100000001"
    assert item_bound["business_name"] == "Business Alpha"
    assert item_bound["balance"] == "125.5000"
    assert item_bound["is_blocked"] is False
    assert item_bound["phone_masked"] is not None
    assert item_bound["bind_method"] == "manual_barcode"

    # 3. Superadmin with business_id=B: sees only 2 cards
    s_filt_b = await admin_client.get(f"/admin/cards?business_id={business_b.id}", headers=s_headers)
    assert s_filt_b.status_code == 200
    assert len(s_filt_b.json()["items"]) == 2

    # 4. Business Manager A without business_id: automatically scoped to business A (3 cards)
    m_res = await admin_client.get("/admin/cards", headers=m_headers)
    assert m_res.status_code == 200
    m_items = m_res.json()["items"]
    assert len(m_items) == 3
    assert all(it["business_id"] == str(business_a.id) for it in m_items)

    # 5. Business Manager A specifying their own business_id: succeeds (3 cards)
    m_own = await admin_client.get(f"/admin/cards?business_id={business_a.id}", headers=m_headers)
    assert m_own.status_code == 200
    assert len(m_own.json()["items"]) == 3

    # 6. Business Manager A specifying foreign business_id B: returns 404 (does NOT disclose foreign cards)
    m_foreign = await admin_client.get(f"/admin/cards?business_id={business_b.id}", headers=m_headers)
    assert m_foreign.status_code == 404
    assert m_foreign.json()["error"]["code"] == "ADMIN_RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_admin_cards_search_contract_preserved(admin_client: AsyncClient, db_session: AsyncSession):
    business = await make_business(db_session, "Search Preserved Business")
    superadmin = await make_admin(db_session, "superadmin", None, "superadmin.search")
    headers = await authenticated_headers(db_session, superadmin)

    await make_card(db_session, business.id, "0123456789012", "+77009876543")

    # Search without barcode and without phone must still fail validation with 422
    empty_search = await admin_client.post("/admin/cards/search", json={}, headers=headers)
    assert empty_search.status_code == 422

    # Valid barcode search works
    valid_search = await admin_client.post(
        "/admin/cards/search", json={"barcode": "0123456789012"}, headers=headers
    )
    assert valid_search.status_code == 200
    assert len(valid_search.json()["items"]) == 1
    assert valid_search.json()["items"][0]["barcode"] == "0123456789012"
