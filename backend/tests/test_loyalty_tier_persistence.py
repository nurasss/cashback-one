"""Persistence of loyalty-tier settings (turnover period, percent) through the admin API.

Every HTTP request below gets its OWN database session (like production), so a value that was not
committed cannot be read back. Requests use the exact body shape the cabinet form sends (all fields).
"""
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session
from app.main import app
from app.models.entities import Business, BusinessLoyaltyTier
from app.services.rate_limiter import _test_limiter, get_rate_limiter
from tests._dual_engine import engine  # noqa: F401
from tests.test_admin_mutations import auth_headers, make_admin, make_business
from tests.test_customer_app import business_with_card, customer


@dataclass
class Env:
    client: AsyncClient
    factory: async_sessionmaker[AsyncSession]
    biz_id: uuid.UUID
    other_biz_id: uuid.UUID
    mgr: dict[str, str]
    other_mgr: dict[str, str]
    super_: dict[str, str]

    def url(self, tier_id: object = None, biz: uuid.UUID | None = None) -> str:
        base = f"/admin/businesses/{biz or self.biz_id}/loyalty-tiers"
        return base if tier_id is None else f"{base}/{tier_id}"

    async def version(self, biz: uuid.UUID | None = None) -> int:
        async with self.factory() as s:
            value = await s.scalar(
                select(Business.loyalty_tiers_version).where(Business.id == (biz or self.biz_id))
            )
        return int(value or 0)

    async def stored(self, tier_id: str) -> BusinessLoyaltyTier:
        async with self.factory() as s:
            tier = await s.scalar(select(BusinessLoyaltyTier).where(BusinessLoyaltyTier.id == uuid.UUID(tier_id)))
        assert tier is not None
        return tier

    async def list(self, headers: dict[str, str] | None = None, biz: uuid.UUID | None = None) -> list[dict]:
        res = await self.client.get(self.url(biz=biz), headers=headers or self.mgr)
        assert res.status_code == 200, res.text
        return res.json()


def form_body(**overrides: object) -> dict[str, object]:
    """The exact payload of admin/src/pages/StatusesPage.tsx (every field is sent, also on edit)."""
    body: dict[str, object] = {
        "level": 1,
        "name_ru": "Нет-нет заглядывает",
        "name_kk": "Жиі кірмейді",
        "description_ru": None,
        "description_kk": None,
        "turnover_period_months": 6,
        "min_turnover": 0,
        "max_turnover": 100000,
        "percent": 2,
        "image_url": None,
        "is_active": True,
    }
    body.update(overrides)
    return body


@pytest.fixture
async def env(engine) -> AsyncGenerator[Env, None]:  # type: ignore[no-untyped-def]  # noqa: F811
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s0:
        biz = await make_business(s0, "Persist A")
        other = await make_business(s0, "Persist B")
        mgr = await make_admin(s0, "business_manager", biz.id, "persist-mgr")
        other_mgr = await make_admin(s0, "business_manager", other.id, "persist-other-mgr")
        sup = await make_admin(s0, "superadmin", None, "persist-super")
        mgr_h = await auth_headers(s0, mgr)
        other_h = await auth_headers(s0, other_mgr)
        sup_h = await auth_headers(s0, sup)
        await s0.commit()
        ids = (biz.id, other.id)

    async def fresh_session():  # type: ignore[no-untyped-def]
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = fresh_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
        yield Env(client, factory, ids[0], ids[1], mgr_h, other_h, sup_h)
    app.dependency_overrides.clear()


async def create_tier(env: Env, **overrides: object) -> dict:
    res = await env.client.post(env.url(), headers=env.mgr, json=form_body(**overrides))
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------------------------
# 1. Turnover period
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_period_survives_create_full_edit_and_reread_in_new_sessions(env: Env) -> None:
    created = await create_tier(env, turnover_period_months=6)
    tier_id = created["id"]
    assert (await env.list())[0]["turnover_period_months"] == 6
    version = await env.version()

    # Edit exactly like the form does: every field is sent, only the period differs.
    res = await env.client.patch(env.url(tier_id), headers=env.mgr, json=form_body(turnover_period_months=3))
    assert res.status_code == 200, res.text
    assert res.json()["turnover_period_months"] == 3
    after = (await env.list())[0]
    assert after["turnover_period_months"] == 3
    assert (after["name_ru"], after["name_kk"], after["level"], after["is_active"]) == (
        "Нет-нет заглядывает", "Жиі кірмейді", 1, True)
    assert (after["percent"], after["min_turnover"], after["max_turnover"]) == ("2.00", "0.00", "100000.00")
    assert await env.version() == version + 1

    # The same edit repeated and then a different one: the last write wins and survives a re-read.
    for months in (3, 12, 1, 36):
        res = await env.client.patch(env.url(tier_id), headers=env.mgr, json=form_body(turnover_period_months=months))
        assert res.status_code == 200, res.text
        assert (await env.list())[0]["turnover_period_months"] == months
        assert (await env.stored(tier_id)).turnover_period_months == months


@pytest.mark.asyncio
async def test_partial_patch_changes_only_the_period_and_keeps_everything_else(env: Env) -> None:
    tier = await create_tier(env, percent=2.5, description_ru="Описание", image_url=None)
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json={"turnover_period_months": 1})
    assert res.status_code == 200, res.text
    stored = await env.stored(tier["id"])
    assert stored.turnover_period_months == 1
    assert stored.percent == Decimal("2.50")  # not reset to a default
    assert stored.min_turnover == Decimal("0.00") and stored.max_turnover == Decimal("100000.00")
    assert stored.name_ru == "Нет-нет заглядывает" and stored.description_ru == "Описание" and stored.is_active is True

    # ...and the opposite: a percent-only patch does not touch the period.
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json={"percent": 3.75})
    assert res.status_code == 200, res.text
    stored = await env.stored(tier["id"])
    assert (stored.turnover_period_months, stored.percent) == (1, Decimal("3.75"))


@pytest.mark.asyncio
async def test_period_of_every_status_can_be_changed_one_by_one(env: Env) -> None:
    ids = []
    for level, lo, hi, pct in ((1, 0, 100000, 2), (2, 100000, 200000, 3), (3, 200000, None, 4)):
        ids.append((await create_tier(env, level=level, name_ru=f"L{level}", name_kk=f"L{level}",
                                      min_turnover=lo, max_turnover=hi, percent=pct))["id"])
    for months in (1, 6, 24):
        for tier_id, (level, lo, hi, pct) in zip(
                ids, ((1, 0, 100000, 2), (2, 100000, 200000, 3), (3, 200000, None, 4)), strict=True):
            res = await env.client.patch(
                env.url(tier_id), headers=env.mgr,
                json=form_body(level=level, name_ru=f"L{level}", name_kk=f"L{level}", min_turnover=lo,
                               max_turnover=hi, percent=pct, turnover_period_months=months))
            assert res.status_code == 200, res.text
        assert [t["turnover_period_months"] for t in await env.list()] == [months] * 3


@pytest.mark.asyncio
async def test_conflicting_range_change_is_all_or_nothing(env: Env) -> None:
    # Lifetime turnover: ranges conflict whatever the historical period value is, and a refused edit leaves nothing.
    a = await create_tier(env, level=1, name_ru="A", name_kk="A", min_turnover=0, max_turnover=100000,
                          turnover_period_months=6)
    b = await create_tier(env, level=2, name_ru="B", name_kk="B", min_turnover=100000, max_turnover=150000,
                          turnover_period_months=3)
    version = await env.version()
    res = await env.client.patch(env.url(b["id"]), headers=env.mgr, json=form_body(
        level=2, name_ru="B", name_kk="B", min_turnover=50000, max_turnover=150000, turnover_period_months=3))
    assert res.status_code == 409
    stored = await env.stored(b["id"])
    assert stored.min_turnover == 100000  # the failed edit left nothing behind
    assert await env.version() == version
    assert (await env.stored(a["id"])).turnover_period_months == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -1, 37, 3.5, "abc", "", None, [6], {"v": 6}])
async def test_invalid_period_is_rejected_and_nothing_is_stored(env: Env, bad: object) -> None:
    tier = await create_tier(env)
    version = await env.version()
    for body in ({"turnover_period_months": bad}, form_body(turnover_period_months=bad)):
        res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json=body)
        assert res.status_code == 422, (bad, res.text)
    assert (await env.stored(tier["id"])).turnover_period_months == 6
    assert await env.version() == version
    res = await env.client.post(env.url(), headers=env.mgr, json=form_body(level=2, turnover_period_months=bad))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_boolean_is_not_accepted_for_numeric_fields(env: Env) -> None:
    """JSON `true` must not silently become 1 month / 1 percent."""
    tier = await create_tier(env)
    for field in ("turnover_period_months", "percent", "min_turnover", "level"):
        res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json={field: True})
        assert res.status_code == 422, (field, res.text)
    stored = await env.stored(tier["id"])
    assert (stored.turnover_period_months, stored.percent, stored.level) == (6, Decimal("2.00"), 1)


# ---------------------------------------------------------------------------------------------
# 2. Percent
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("value,expected", [(0, "0.00"), (0.5, "0.50"), (2.5, "2.50"), (33.33, "33.33"),
                                            ("4.1", "4.10"), (100, "100.00")])
async def test_percent_round_trips_exactly(env: Env, value: object, expected: str) -> None:
    tier = await create_tier(env, percent=2)
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json=form_body(percent=value))
    assert res.status_code == 200, res.text
    assert res.json()["percent"] == expected
    assert (await env.list())[0]["percent"] == expected
    assert str((await env.stored(tier["id"])).percent) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-0.01, -1, 100.01, 101, "abc", "", None, "NaN", "Infinity"])
async def test_percent_out_of_range_or_not_a_number_is_rejected(env: Env, bad: object) -> None:
    tier = await create_tier(env, percent=2)
    version = await env.version()
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json={"percent": bad})
    assert res.status_code == 422, (bad, res.text)
    res = await env.client.post(env.url(), headers=env.mgr, json=form_body(level=2, percent=bad))
    assert res.status_code == 422
    assert (await env.stored(tier["id"])).percent == Decimal("2.00")
    assert await env.version() == version


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [2.555, "2.555", 0.001, 0.30000000000000004, 99.999])
async def test_percent_with_more_than_two_decimals_is_rejected_not_rounded(env: Env, value: object) -> None:
    """A value that cannot be stored exactly must be refused, never rounded in silence (2.555 -> 2.56)."""
    tier = await create_tier(env, percent=2)
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json={"percent": value})
    assert res.status_code == 422, (value, res.text)
    res = await env.client.post(env.url(), headers=env.mgr, json=form_body(level=2, percent=value))
    assert res.status_code == 422
    assert (await env.stored(tier["id"])).percent == Decimal("2.00")


@pytest.mark.asyncio
async def test_turnover_amount_beyond_column_range_is_rejected(env: Env) -> None:
    """Numeric(14,2): at most 12 integer digits and 2 decimals. More must be a 422, not a database error."""
    tier = await create_tier(env, min_turnover=0, max_turnover=None)
    for body in ({"min_turnover": 1e14}, {"min_turnover": "1000000000000.00"}, {"min_turnover": 100.123},
                 {"max_turnover": "1000000000000.00"}, {"max_turnover": 500000.005}):
        res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json=body)
        assert res.status_code == 422, (body, res.text)
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr,
                                 json={"min_turnover": "999999999999.98", "max_turnover": "999999999999.99"})
    assert res.status_code == 200, res.text
    stored = await env.stored(tier["id"])
    assert (stored.min_turnover, stored.max_turnover) == (Decimal("999999999999.98"), Decimal("999999999999.99"))


@pytest.mark.asyncio
async def test_percent_change_reaches_the_customer_app_and_changes_its_etag_and_version(env: Env) -> None:
    async with env.factory() as s:
        user, cust_hdr = await customer(s, "+77015550777")
        biz, _card = await business_with_card(s, user, name="Persist App", barcode="0123456789555")
        other_user, other_hdr = await customer(s, "+77015550778")
        other_biz, _ = await business_with_card(s, other_user, name="Persist App 2", barcode="0123456789556")
    admin_headers = env.super_
    res = await env.client.post(env.url(biz=biz.id), headers=admin_headers, json=form_body())
    assert res.status_code == 201, res.text
    tier_id = res.json()["id"]

    first = await env.client.get(f"/me/app-content?business_id={biz.id}", headers=cust_hdr)
    assert first.status_code == 200
    assert first.json()["loyalty_tiers"][0]["percent"] == "2.00"
    assert first.json()["loyalty_tiers"][0]["turnover_period_months"] == 6
    etag, version = first.headers["etag"], first.json()["loyalty_tiers_version"]

    res = await env.client.patch(env.url(tier_id, biz=biz.id), headers=admin_headers,
                                 json=form_body(percent=3.5, turnover_period_months=2))
    assert res.status_code == 200, res.text
    second = await env.client.get(f"/me/app-content?business_id={biz.id}", headers=cust_hdr)
    assert second.status_code == 200
    tier = second.json()["loyalty_tiers"][0]
    assert (tier["percent"], tier["turnover_period_months"]) == ("3.50", 2)
    assert second.headers["etag"] != etag
    assert second.json()["loyalty_tiers_version"] == version + 1
    # The old ETag must not be answered with 304 any more.
    revalidate = await env.client.get(f"/me/app-content?business_id={biz.id}",
                                      headers={**cust_hdr, "If-None-Match": etag})
    assert revalidate.status_code == 200

    # A customer of another business never sees these tiers.
    foreign = await env.client.get(f"/me/app-content?business_id={other_biz.id}", headers=other_hdr)
    assert foreign.status_code == 200 and foreign.json()["loyalty_tiers"] == []


# ---------------------------------------------------------------------------------------------
# Tenant isolation and permissions
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_business_manager_cannot_read_or_change_tiers_and_nothing_changes(env: Env) -> None:
    tier = await create_tier(env, percent=2)
    version = await env.version()
    patch = {"turnover_period_months": 1, "percent": 9}
    for headers in (env.other_mgr,):
        assert (await env.client.get(env.url(), headers=headers)).status_code == 404
        assert (await env.client.patch(env.url(tier["id"]), headers=headers, json=patch)).status_code == 404
        assert (await env.client.delete(env.url(tier["id"]), headers=headers)).status_code == 404
        assert (await env.client.post(env.url(), headers=headers, json=form_body(level=2))).status_code == 404
    # Own business path + foreign tier id (and the reverse) is not found either.
    assert (await env.client.patch(env.url(tier["id"], biz=env.other_biz_id), headers=env.other_mgr,
                                   json=patch)).status_code == 404
    assert (await env.client.patch(env.url(tier["id"], biz=env.other_biz_id), headers=env.super_,
                                   json=patch)).status_code == 404
    # No credentials.
    res = await env.client.patch(env.url(tier["id"]), headers={k: v for k, v in env.mgr.items()
                                                                  if k != "Authorization"}, json=patch)
    assert res.status_code in (401, 403)
    stored = await env.stored(tier["id"])
    assert (stored.turnover_period_months, stored.percent) == (6, Decimal("2.00"))
    assert await env.version() == version
    assert await env.list(env.other_mgr, biz=env.other_biz_id) == []


@pytest.mark.asyncio
async def test_superadmin_edits_any_business_and_each_business_keeps_its_own_values(env: Env) -> None:
    a = await create_tier(env, percent=2, turnover_period_months=6)
    res = await env.client.post(env.url(biz=env.other_biz_id), headers=env.super_,
                                json=form_body(percent=4, turnover_period_months=12))
    assert res.status_code == 201, res.text
    b_id = res.json()["id"]
    res = await env.client.patch(env.url(b_id, biz=env.other_biz_id), headers=env.super_,
                                 json={"turnover_period_months": 2})
    assert res.status_code == 200, res.text
    assert (await env.stored(a["id"])).turnover_period_months == 6
    stored_b = await env.stored(b_id)
    assert (stored_b.turnover_period_months, stored_b.percent) == (2, Decimal("4.00"))
