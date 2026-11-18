"""`total` on the admin card list (GET /admin/cards) and card search (POST /admin/cards/search).

total = exact number of cards matching the SAME tenant scope, business filter and search as `items`.
"""
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session
from app.main import app
from app.models.entities import Card, User, UserCard
from app.services.rate_limiter import _test_limiter, get_rate_limiter
from tests._dual_engine import engine  # noqa: F401
from tests.test_admin_mutations import auth_headers, make_admin, make_business

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


async def seed(db: AsyncSession):  # type: ignore[no-untyped-def]
    biz_a = await make_business(db, "Cards A")
    biz_b = await make_business(db, "Cards B")
    # A: 7 cards, B: 3 cards. All ten phones share the suffix 5551234; barcodes share the suffix 1234 except one
    # card per business, which share the suffix 3333 (the same suffix exists in both tenants on purpose).
    cards_a, cards_b = [], []
    for i in range(7):
        barcode = f"{i}00001234" if i < 6 else "880003333"
        card = Card(business_id=biz_a.id, barcode=barcode, phone=f"+7{i}015551234", balance=Decimal("1.0000"),
                    updated_at=NOW - timedelta(minutes=i))
        db.add(card)
        cards_a.append(card)
    for i in range(3):
        barcode = f"{i + 7}00001234" if i < 2 else "990003333"
        card = Card(business_id=biz_b.id, barcode=barcode, phone=f"+7{i + 7}015551234",
                    balance=Decimal("2.0000"), updated_at=NOW - timedelta(minutes=i))
        db.add(card)
        cards_b.append(card)
    await db.flush()
    # Bind some cards to customers: the join must never multiply rows.
    for card in cards_a[:3] + cards_b[:1]:
        user = User(phone=card.phone, language="ru", created_at=NOW)
        db.add(user)
        await db.flush()
        db.add(UserCard(user_id=user.id, card_id=card.id, bind_method="phone_auto", bound_at=NOW))
    mgr_a = await make_admin(db, "business_manager", biz_a.id, "cards-mgr-a")
    mgr_b = await make_admin(db, "business_manager", biz_b.id, "cards-mgr-b")
    biz_c = await make_business(db, "Cards C (no cards)")
    mgr_c = await make_admin(db, "business_manager", biz_c.id, "cards-mgr-c")
    sup = await make_admin(db, "superadmin", None, "cards-super")
    headers = {
        "a": await auth_headers(db, mgr_a),
        "b": await auth_headers(db, mgr_b),
        "c": await auth_headers(db, mgr_c),
        "s": await auth_headers(db, sup),
    }
    await db.commit()
    return biz_a, biz_b, headers


@pytest.fixture
async def cards_env(engine):  # type: ignore[no-untyped-def]  # noqa: F811
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s0:
        biz_a, biz_b, headers = await seed(s0)
        ids = (biz_a.id, biz_b.id)

    async def fresh_session():  # type: ignore[no-untyped-def]
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = fresh_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
        yield client, SimpleNamespace(id=ids[0]), SimpleNamespace(id=ids[1]), headers
    app.dependency_overrides.clear()


async def get_page(client: AsyncClient, headers: dict[str, str], **params: object) -> dict:
    res = await client.get("/admin/cards", headers=headers, params=params)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_list_total_is_exact_on_every_page_and_old_fields_are_unchanged(cards_env) -> None:  # type: ignore[no-untyped-def]
    mutation_client, biz_a, _biz_b, h = cards_env
    seen: list[str] = []
    for offset, expected_len, has_more in ((0, 3, True), (3, 3, True), (6, 1, False)):
        page = await get_page(mutation_client, h["a"], limit=3, offset=offset)
        assert page["total"] == 7
        assert (page["limit"], page["offset"], page["has_more"]) == (3, offset, has_more)
        assert len(page["items"]) == expected_len
        assert {item["business_id"] for item in page["items"]} == {str(biz_a.id)}
        seen += [item["barcode"] for item in page["items"]]
    assert seen == [f"{i}00001234" for i in range(6)] + ["880003333"]  # same order as before: newest update first, no repeats

    # An unavailable page (after the last one) is empty, but total tells how many pages there really are.
    beyond = await get_page(mutation_client, h["a"], limit=3, offset=30)
    assert (beyond["items"], beyond["total"], beyond["has_more"]) == ([], 7, False)
    at_limit = await get_page(mutation_client, h["a"], limit=30, offset=100_000)
    assert (at_limit["items"], at_limit["total"]) == ([], 7)

    # Default page size and the existing size limit are kept.
    default = await get_page(mutation_client, h["a"])
    assert default["limit"] == 25 and len(default["items"]) == 7 and default["total"] == 7
    assert (await mutation_client.get("/admin/cards", headers=h["a"], params={"limit": 31})).status_code == 422
    assert (await mutation_client.get("/admin/cards", headers=h["a"], params={"limit": 0})).status_code == 422
    assert (await mutation_client.get("/admin/cards", headers=h["a"], params={"offset": -1})).status_code == 422


@pytest.mark.asyncio
async def test_list_total_follows_role_and_business_filter_without_leaking_other_tenants(cards_env) -> None:  # type: ignore[no-untyped-def]
    mutation_client, biz_a, biz_b, h = cards_env
    assert (await get_page(mutation_client, h["b"]))["total"] == 3
    assert (await get_page(mutation_client, h["a"]))["total"] == 7
    assert (await get_page(mutation_client, h["a"], business_id=str(biz_a.id)))["total"] == 7
    # A manager asking for another business gets the same "not found" as before, not a count.
    res = await mutation_client.get("/admin/cards", headers=h["a"], params={"business_id": str(biz_b.id)})
    assert res.status_code == 404 and "total" not in res.text
    # Superadmin: all cards, or one business.
    assert (await get_page(mutation_client, h["s"], limit=1))["total"] == 10
    assert (await get_page(mutation_client, h["s"], business_id=str(biz_b.id)))["total"] == 3
    assert (await get_page(mutation_client, h["s"], business_id=str(uuid.uuid4())))["total"] == 0


@pytest.mark.asyncio
async def test_list_total_for_a_business_without_cards_is_zero(cards_env) -> None:  # type: ignore[no-untyped-def]
    mutation_client, _a, _b, h = cards_env
    page = await get_page(mutation_client, h["c"])
    assert page == {"items": [], "limit": 25, "offset": 0, "has_more": False, "total": 0}


@pytest.mark.asyncio
async def test_search_total_uses_the_same_filters_as_items(cards_env) -> None:  # type: ignore[no-untyped-def]
    mutation_client, _biz_a, biz_b, h = cards_env

    async def search(headers: dict[str, str], body: dict, **params: object) -> dict:
        res = await mutation_client.post("/admin/cards/search", headers=headers, json=body, params=params)
        assert res.status_code == 200, res.text
        return res.json()

    # Suffix 3333 exists in both tenants: a manager counts only their own card, a superadmin sees both.
    only_a = await search(h["a"], {"barcode": "3333"})
    assert only_a["total"] == 1 and [i["barcode"] for i in only_a["items"]] == ["880003333"]
    assert (await search(h["b"], {"barcode": "3333"}))["total"] == 1
    both = await search(h["s"], {"barcode": "3333"})
    assert both["total"] == 2 and len(both["items"]) == 2
    assert (await search(h["s"], {"barcode": "3333", "business_id": str(biz_b.id)}))["total"] == 1
    # Several pages of one search: total is the same on every page, items and has_more behave as before.
    pages = [await search(h["s"], {"barcode": "1234"}, limit=3, offset=o) for o in (0, 3, 6)]
    assert [p["total"] for p in pages] == [8, 8, 8]
    assert [len(p["items"]) for p in pages] == [3, 3, 2]
    assert [p["has_more"] for p in pages] == [True, True, False]
    phone_pages = [await search(h["s"], {"phone": "5551234"}, limit=4, offset=o) for o in (0, 4, 8)]
    assert [p["total"] for p in phone_pages] == [10, 10, 10]
    assert [len(p["items"]) for p in phone_pages] == [4, 4, 2]
    assert (await search(h["a"], {"phone": "5551234"}))["total"] == 7
    assert (await search(h["b"], {"phone": "5551234"}))["total"] == 3
    # No match, and a manager asking about another business.
    nothing = await search(h["a"], {"barcode": "9999999999"})
    assert (nothing["items"], nothing["total"], nothing["has_more"]) == ([], 0, False)
    res = await mutation_client.post("/admin/cards/search", headers=h["a"],
                                     json={"barcode": "3333", "business_id": str(biz_b.id)})
    assert res.status_code == 404 and "total" not in res.text
    # Existing contract kept: a search needs a barcode or phone (the plain list is GET /admin/cards).
    res = await mutation_client.post("/admin/cards/search", headers=h["a"], json={})
    assert res.status_code == 422
    # Beyond the last page of a search.
    far = await search(h["a"], {"barcode": "3333"}, limit=3, offset=90)
    assert (far["items"], far["total"], far["has_more"]) == ([], 1, False)


@pytest.mark.asyncio
async def test_total_does_not_expose_extra_personal_data(cards_env) -> None:  # type: ignore[no-untyped-def]
    mutation_client, _a, _b, h = cards_env
    page = await get_page(mutation_client, h["a"], limit=7)
    for item in page["items"]:
        assert "phone" not in item
        assert item["phone_masked"] == "••••1234"  # masked to the last four digits, as before
    assert set(page) == {"items", "limit", "offset", "has_more", "total"}
