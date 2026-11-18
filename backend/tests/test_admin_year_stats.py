"""Tests for unrestricted-period admin dashboard statistics and backward-compatible /admin/me contract."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings, settings
from app.db.session import get_session
from app.main import app
from app.models.entities import Agent, Card, Transaction, User, UserCard
from app.schemas.admin import AdminIdentity, AdminMeResponse
from app.services.rate_limiter import _test_limiter, get_rate_limiter
from tests._dual_engine import engine  # noqa: F401
from tests.test_admin_mutations import auth_headers, make_admin, make_business

ASTANA_TZ = timezone(timedelta(hours=5))


def test_settings_and_admin_me_schema_unrestricted_compatibility_contract() -> None:
    assert settings.admin_max_stats_period_days == 90

    default_cfg = Settings(_env_file=None)  # type: ignore[call-arg]
    assert default_cfg.admin_max_stats_period_days == 90
    assert Settings(_env_file=None, admin_max_stats_period_days=365).admin_max_stats_period_days == 365  # type: ignore[call-arg]
    assert Settings(_env_file=None, admin_max_stats_period_days=1).admin_max_stats_period_days == 1  # type: ignore[call-arg]

    for invalid_days in (0, 366):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, admin_max_stats_period_days=invalid_days)  # type: ignore[call-arg]

    identity = AdminIdentity(
        id=uuid.uuid4(),
        login="unrestricted.stats.check",
        role="superadmin",
        business=None,
    )
    me_default = AdminMeResponse(admin=identity, admin_max_stats_period_days=90)
    assert me_default.admin_stats_unlimited_period is True
    assert me_default.admin_max_stats_period_days == 90

    me_explicit = AdminMeResponse(
        admin=identity,
        admin_stats_unlimited_period=True,
        admin_max_stats_period_days=365,
    )
    assert me_explicit.admin_stats_unlimited_period is True
    assert me_explicit.admin_max_stats_period_days == 365

    for invalid_days in (0, 366):
        with pytest.raises(ValidationError):
            AdminMeResponse(admin=identity, admin_max_stats_period_days=invalid_days)


def _astana_period(start_date: tuple[int, int, int], end_date: tuple[int, int, int]) -> dict[str, str]:
    start_utc = datetime(*start_date, 0, 0, 0, tzinfo=ASTANA_TZ).astimezone(UTC)
    end_utc = datetime(*end_date, 23, 59, 59, 999000, tzinfo=ASTANA_TZ).astimezone(UTC)
    return {
        "from": start_utc.isoformat().replace("+00:00", "Z"),
        "to": end_utc.isoformat().replace("+00:00", "Z"),
    }


async def _seed_stats(db: AsyncSession) -> dict[str, object]:
    now = datetime.now(UTC).replace(microsecond=0)
    biz_a = await make_business(db, "Unrestricted Stats Alpha")
    biz_b = await make_business(db, "Unrestricted Stats Beta")

    user_a1 = User(phone="+77011110001", language="ru", created_at=now - timedelta(days=4000))
    user_a2 = User(phone="+77011110002", language="ru", created_at=now - timedelta(days=4000))
    user_deleted = User(
        phone="+77011110003",
        language="ru",
        created_at=now - timedelta(days=4000),
        deleted_at=now - timedelta(days=10),
    )
    user_shared = User(phone="+77011110004", language="kk", created_at=now - timedelta(days=4000))
    user_b_only = User(phone="+77011110005", language="ru", created_at=now - timedelta(days=4000))
    db.add_all([user_a1, user_a2, user_deleted, user_shared, user_b_only])
    await db.flush()

    card_a1 = Card(business_id=biz_a.id, barcode="1000000000001", phone=user_a1.phone, balance=Decimal("10.0000"), updated_at=now)
    card_a2_blocked = Card(
        business_id=biz_a.id, barcode="1000000000002", phone=user_a2.phone, balance=Decimal("20.0000"), is_blocked=True, updated_at=now
    )
    card_a3_deleted = Card(
        business_id=biz_a.id, barcode="1000000000003", phone=user_deleted.phone, balance=Decimal("5.0000"), updated_at=now
    )
    card_a4_shared = Card(
        business_id=biz_a.id, barcode="1000000000004", phone=user_shared.phone, balance=Decimal("15.0000"), updated_at=now
    )
    card_b1_shared = Card(
        business_id=biz_b.id, barcode="2000000000001", phone=user_shared.phone, balance=Decimal("30.0000"), updated_at=now
    )
    card_b2 = Card(
        business_id=biz_b.id, barcode="2000000000002", phone=user_b_only.phone, balance=Decimal("40.0000"), updated_at=now
    )
    db.add_all([card_a1, card_a2_blocked, card_a3_deleted, card_a4_shared, card_b1_shared, card_b2])
    await db.flush()

    db.add_all([
        UserCard(user_id=user_a1.id, card_id=card_a1.id, bind_method="phone_auto", bound_at=now),
        UserCard(user_id=user_a2.id, card_id=card_a2_blocked.id, bind_method="phone_auto", bound_at=now),
        UserCard(user_id=user_deleted.id, card_id=card_a3_deleted.id, bind_method="phone_auto", bound_at=now),
        UserCard(user_id=user_shared.id, card_id=card_a4_shared.id, bind_method="phone_auto", bound_at=now),
        UserCard(user_id=user_shared.id, card_id=card_b1_shared.id, bind_method="phone_auto", bound_at=now),
        UserCard(user_id=user_b_only.id, card_id=card_b2.id, bind_method="phone_auto", bound_at=now),
    ])

    # Multi-year UTC+5 boundary timestamps from 2015 through 2026:
    # 2016-01-01 00:00:00 Astana == 2015-12-31T19:00:00Z
    # 2021-01-01 00:00:00 Astana == 2020-12-31T19:00:00Z
    # 2024-01-01 00:00:00 Astana == 2023-12-31T19:00:00Z
    # 2025-01-01 00:00:00 Astana == 2024-12-31T19:00:00Z
    # 2025-12-31 23:59:59.999999 Astana == 2025-12-31T18:59:59.999999Z
    tx_rows = [
        # Strictly before 2016 (2015-12-31 23:59:59.999999 Astana)
        (card_a1.id, "tx-a-2015-end", "accrual", datetime(2015, 12, 31, 18, 59, 59, 999999, tzinfo=UTC)),
        # 2016..2020 (inside 10y 2016..2025, outside 5y 2021..2025)
        (card_a1.id, "tx-a-2016-start", "accrual", datetime(2015, 12, 31, 19, 0, 0, tzinfo=UTC)),
        (card_a4_shared.id, "tx-a-2018-mid", "accrual", datetime(2018, 6, 15, 12, 0, 0, tzinfo=UTC)),
        (card_b1_shared.id, "tx-b-2019-mid", "accrual", datetime(2019, 9, 1, 8, 0, 0, tzinfo=UTC)),
        # 2021..2023 (inside 5y 2021..2025, outside 2y 2024..2025)
        (card_a1.id, "tx-a-2021-start", "accrual", datetime(2020, 12, 31, 19, 0, 0, tzinfo=UTC)),
        (card_a1.id, "tx-a-2023-end", "accrual", datetime(2023, 12, 31, 18, 59, 59, 999999, tzinfo=UTC)),
        # 2024 (leap year, 366d)
        (card_a1.id, "tx-a-2024-start", "accrual", datetime(2023, 12, 31, 19, 0, 0, tzinfo=UTC)),
        (card_a2_blocked.id, "tx-a-2024-leap-day", "accrual", datetime(2024, 2, 29, 12, 0, 0, tzinfo=UTC)),
        (card_a4_shared.id, "tx-a-2024-mid", "redemption", datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)),
        (card_a1.id, "tx-a-2024-end", "accrual", datetime(2024, 12, 31, 18, 59, 59, 999999, tzinfo=UTC)),
        # 2025 (regular year, 365d)
        (card_a1.id, "tx-a-2025-start", "accrual", datetime(2024, 12, 31, 19, 0, 0, tzinfo=UTC)),
        (card_a4_shared.id, "tx-a-2025-mid", "accrual", datetime(2025, 7, 1, 8, 30, 0, tzinfo=UTC)),
        (card_a1.id, "tx-a-2025-end", "redemption", datetime(2025, 12, 31, 18, 59, 59, 999999, tzinfo=UTC)),
        # 2026 (strictly after 2025)
        (card_a1.id, "tx-a-2026-start", "accrual", datetime(2025, 12, 31, 19, 0, 0, tzinfo=UTC)),
        # Business B transactions
        (card_b1_shared.id, "tx-b-2024-1", "accrual", datetime(2024, 1, 15, 5, 0, 0, tzinfo=UTC)),
        (card_b2.id, "tx-b-2024-leap", "accrual", datetime(2024, 2, 29, 19, 30, 0, tzinfo=UTC)),  # 2024-03-01 00:30 Astana
        (card_b2.id, "tx-b-2025-1", "accrual", datetime(2025, 3, 10, 12, 0, 0, tzinfo=UTC)),
        (card_b1_shared.id, "tx-b-recent", "accrual", now - timedelta(days=5)),
    ]
    for cid, ext_id, tx_type, ts in tx_rows:
        db.add(
            Transaction(
                card_id=cid,
                external_id=ext_id,
                type=tx_type,
                amount=Decimal("10.0000"),
                balance_after=Decimal("10.0000"),
                occurred_at=ts,
            )
        )

    db.add_all([
        Agent(business_id=biz_a.id, key_hash="hash-unrestricted-a1", status="active", last_seen_at=now),
        Agent(business_id=biz_b.id, key_hash="hash-unrestricted-b1", status="active", last_seen_at=now - timedelta(days=2)),
    ])

    mgr_a = await make_admin(db, "business_manager", biz_a.id, "unrestricted-mgr-a")
    sup = await make_admin(db, "superadmin", None, "unrestricted-super")
    headers_mgr_a = await auth_headers(db, mgr_a)
    headers_sup = await auth_headers(db, sup)
    await db.commit()
    return {
        "biz_a": biz_a.id,
        "biz_b": biz_b.id,
        "mgr_a": headers_mgr_a,
        "sup": headers_sup,
        "total_tx": len(tx_rows),
        "biz_a_total_tx": 13,
    }


@pytest.fixture
async def stats_env(engine: AsyncEngine):  # noqa: F811
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as seed_session:
        seeded = await _seed_stats(seed_session)

    async def fresh_session():  # type: ignore[no-untyped-def]
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = fresh_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
        yield client, factory, engine, seeded
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_me_contract_and_multi_year_periods_across_engines(stats_env) -> None:  # type: ignore[no-untyped-def]
    client, factory, _engine, seeded = stats_env
    mgr_headers = seeded["mgr_a"]
    sup_headers = seeded["sup"]
    biz_a = seeded["biz_a"]
    biz_b = seeded["biz_b"]

    # 1. /admin/me reports unlimited flag + legacy positive int compatibility field for both roles
    for hdr in (mgr_headers, sup_headers):
        me = await client.get("/admin/me", headers=hdr)
        assert me.status_code == 200, me.text
        payload = me.json()
        assert payload["admin_stats_unlimited_period"] is True
        assert payload["admin_max_stats_period_days"] == settings.admin_max_stats_period_days == 90

    async with factory() as verify_db:
        async def expected_tx_count(
            period_from: datetime, period_to: datetime, biz_id: uuid.UUID | None
        ) -> int:
            stmt = (
                select(func.count(Transaction.id))
                .select_from(Transaction)
                .join(Card, Card.id == Transaction.card_id)
                .where(Transaction.occurred_at >= period_from, Transaction.occurred_at <= period_to)
            )
            if biz_id is not None:
                stmt = stmt.where(Card.business_id == biz_id)
            return int(await verify_db.scalar(stmt) or 0)

        # 2. Check 365d, 366d (leap + cross-year), 367d, 2y (731d), 5y (1826d), 10y (3653d), full history
        astana_today = (datetime.now(UTC) + timedelta(hours=5)).date()
        scenarios = [
            # (label, start, end, expected_days, expected_all_tx, expected_biz_a_tx)
            ("365d_regular_2025", (2025, 1, 1), (2025, 12, 31), 365, 4, 3),
            ("366d_leap_2024", (2024, 1, 1), (2024, 12, 31), 366, 6, 4),
            ("366d_cross_year", (2024, 3, 1), (2025, 3, 1), 366, 4, 3),
            ("367d_leap_plus_1", (2024, 1, 1), (2025, 1, 1), 367, 7, 5),
            ("367d_reg_plus_2", (2025, 1, 1), (2026, 1, 2), 367, 5, 4),
            ("2y_2024_2025", (2024, 1, 1), (2025, 12, 31), 731, 10, 7),
            ("5y_2021_2025", (2021, 1, 1), (2025, 12, 31), 1826, 12, 9),
            ("10y_2016_2025", (2016, 1, 1), (2025, 12, 31), 3653, 15, 11),
            # Production (owner decision 18.11) rejects periods ending after today in Astana; every seeded
            # transaction is dated before 2026, so ending "today" still covers the whole history.
            (
                "full_history",
                (2015, 12, 31),
                astana_today.timetuple()[:3],
                (astana_today - date(2015, 12, 31)).days + 1,
                int(seeded["total_tx"]),
                int(seeded["biz_a_total_tx"]),
            ),
        ]

        for label, start_d, end_d, expected_days, expected_all, expected_a in scenarios:
            params = _astana_period(start_d, end_d)
            r_all = await client.get("/admin/dashboard", headers=sup_headers, params=params)
            assert r_all.status_code == 200, f"{label}: {r_all.text}"
            d_all = r_all.json()
            assert d_all["period_days"] == expected_days, label
            assert d_all["transactions"] == expected_all, label
            assert d_all["transactions"] == await expected_tx_count(
                datetime.fromisoformat(d_all["period_from"]),
                datetime.fromisoformat(d_all["period_to"]),
                None,
            ), label
            assert d_all["customers_with_business_cards"] == 4
            assert d_all["cards"] == 6
            assert d_all["unblocked_cards"] == 5

            # Tenant-scoped manager vs superadmin filtered to biz_a must match identically
            for hdr, biz_params in (
                (sup_headers, {**params, "business_id": str(biz_a)}),
                (mgr_headers, params),
                (mgr_headers, {**params, "business_id": str(biz_a)}),
            ):
                r_biz = await client.get("/admin/dashboard", headers=hdr, params=biz_params)
                assert r_biz.status_code == 200, f"{label} biz_a: {r_biz.text}"
                d_biz = r_biz.json()
                assert d_biz["business_id"] == str(biz_a)
                assert d_biz["period_days"] == expected_days
                assert d_biz["transactions"] == expected_a
                assert d_biz["customers_with_business_cards"] == 3
                assert d_biz["cards"] == 4
                assert d_biz["unblocked_cards"] == 3

        # 3. Exact Astana UTC+5 boundaries on 10-year and full-history edges
        r_10y = await client.get("/admin/dashboard", headers=sup_headers, params=_astana_period((2016, 1, 1), (2025, 12, 31)))
        assert r_10y.status_code == 200
        assert r_10y.json()["period_from"] == "2015-12-31T19:00:00Z"
        assert r_10y.json()["period_to"] == "2025-12-31T18:59:59.999999Z"

        # 4. Out-of-history empty past range returns 0 transactions while preserving snapshot counts
        for empty_start, empty_end, empty_days in (((2010, 1, 1), (2012, 12, 31), 1096),):
            r_empty = await client.get(
                "/admin/dashboard",
                headers=sup_headers,
                params=_astana_period(empty_start, empty_end),
            )
            assert r_empty.status_code == 200, r_empty.text
            d_empty = r_empty.json()
            assert d_empty["period_days"] == empty_days
            assert d_empty["transactions"] == 0
            assert d_empty["cards"] == 6
            assert d_empty["unblocked_cards"] == 5
            assert d_empty["customers_with_business_cards"] == 4

        # 4b. Owner decision 18.11: a period ending after today (Astana) is rejected
        r_future = await client.get(
            "/admin/dashboard",
            headers=sup_headers,
            params=_astana_period((2030, 1, 1), (2035, 12, 31)),
        )
        assert r_future.status_code == 422, r_future.text
        assert r_future.json()["error"]["reason"] == "PERIOD_AFTER_REPORT_DATE"

        # 5. Manager cannot peek into foreign business_id even on a valid 10-year range -> 404
        r_foreign = await client.get(
            "/admin/dashboard",
            headers=mgr_headers,
            params={**_astana_period((2016, 1, 1), (2025, 12, 31)), "business_id": str(biz_b)},
        )
        assert r_foreign.status_code == 404
        assert r_foreign.json()["error"]["code"] == "ADMIN_RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_period_validation_preserves_date_checks_and_ignores_legacy_limit(
    stats_env, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    client, _factory, _engine, seeded = stats_env
    sup_headers = seeded["sup"]

    # Even if legacy setting is tightened to 1 day, /admin/dashboard stays unrestricted
    monkeypatch.setattr(settings, "admin_max_stats_period_days", 1)
    res_10y_with_legacy_1 = await client.get(
        "/admin/dashboard",
        headers=sup_headers,
        params=_astana_period((2016, 1, 1), (2025, 12, 31)),
    )
    assert res_10y_with_legacy_1.status_code == 200, res_10y_with_legacy_1.text
    assert res_10y_with_legacy_1.json()["period_days"] == 3653

    # Preserved 1d, 30d, 90d and omitted defaults
    for start_d, end_d, expected_days in (
        ((2024, 2, 29), (2024, 2, 29), 1),
        ((2025, 1, 1), (2025, 1, 30), 30),
        ((2025, 1, 1), (2025, 3, 31), 90),
    ):
        res = await client.get("/admin/dashboard", headers=sup_headers, params=_astana_period(start_d, end_d))
        assert res.status_code == 200, res.text
        assert res.json()["period_days"] == expected_days

    res_default = await client.get("/admin/dashboard", headers=sup_headers)
    assert res_default.status_code == 200
    assert res_default.json()["period_days"] == 31
    assert res_default.json()["transactions"] == 1  # tx-b-recent

    # end < start -> ADMIN_INVALID_PERIOD (different days and same-day instant ordering)
    res_inverted_day = await client.get(
        "/admin/dashboard",
        headers=sup_headers,
        params=_astana_period((2025, 5, 10), (2025, 5, 9)),
    )
    assert res_inverted_day.status_code == 422
    assert res_inverted_day.json()["error"]["code"] == "ADMIN_INVALID_PERIOD"

    res_inverted_same_day = await client.get(
        "/admin/dashboard",
        headers=sup_headers,
        params={"from": "2025-05-10T10:00:00Z", "to": "2025-05-10T09:59:59Z"},
    )
    assert res_inverted_same_day.status_code == 422
    assert res_inverted_same_day.json()["error"]["code"] == "ADMIN_INVALID_PERIOD"

    # Naive timestamp without timezone -> ADMIN_INVALID_PERIOD
    res_naive = await client.get(
        "/admin/dashboard",
        headers=sup_headers,
        params={"from": "2025-01-01T00:00:00", "to": "2025-12-31T23:59:59"},
    )
    assert res_naive.status_code == 422
    assert res_naive.json()["error"]["code"] == "ADMIN_INVALID_PERIOD"

    # Non-4-digit year -> ADMIN_INVALID_PERIOD
    res_short_year = await client.get(
        "/admin/dashboard",
        headers=sup_headers,
        params={"from": "0999-01-01T00:00:00Z", "to": "2025-12-31T18:59:59Z"},
    )
    assert res_short_year.status_code == 422
    assert res_short_year.json()["error"]["code"] == "ADMIN_INVALID_PERIOD"


@pytest.mark.asyncio
async def test_dashboard_query_count_is_constant_for_1d_366d_and_10y(stats_env) -> None:  # type: ignore[no-untyped-def]
    client, _factory, db_eng, seeded = stats_env
    sup_headers = seeded["sup"]
    biz_a = seeded["biz_a"]

    executed_sql: list[str] = []

    def _count_queries(_conn, _cursor, statement, _parameters, _context, _executemany):  # type: ignore[no-untyped-def]
        executed_sql.append(statement)

    event.listen(db_eng.sync_engine, "before_cursor_execute", _count_queries)
    try:
        executed_sql.clear()
        r_1d = await client.get(
            "/admin/dashboard",
            headers=sup_headers,
            params=_astana_period((2024, 2, 29), (2024, 2, 29)),
        )
        assert r_1d.status_code == 200
        count_1d_all = len(executed_sql)

        executed_sql.clear()
        r_366d = await client.get(
            "/admin/dashboard",
            headers=sup_headers,
            params=_astana_period((2024, 1, 1), (2024, 12, 31)),
        )
        assert r_366d.status_code == 200
        count_366d_all = len(executed_sql)

        executed_sql.clear()
        r_10y = await client.get(
            "/admin/dashboard",
            headers=sup_headers,
            params=_astana_period((2016, 1, 1), (2025, 12, 31)),
        )
        assert r_10y.status_code == 200
        count_10y_all = len(executed_sql)

        executed_sql.clear()
        r_10y_biz = await client.get(
            "/admin/dashboard",
            headers=sup_headers,
            params={**_astana_period((2016, 1, 1), (2025, 12, 31)), "business_id": str(biz_a)},
        )
        assert r_10y_biz.status_code == 200
        count_10y_biz = len(executed_sql)
    finally:
        event.remove(db_eng.sync_engine, "before_cursor_execute", _count_queries)

    assert count_1d_all == count_366d_all == count_10y_all <= 6
    assert count_10y_biz <= 7
