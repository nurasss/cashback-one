"""Tests for store coordinates, loyalty tiers CRUD, and customer app contracts."""
import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.main import app
from app.services.media_storage import InMemoryMediaStorage, get_media_storage
from app.services.rate_limiter import _test_limiter, get_rate_limiter
from tests.test_admin_mutations import (
    auth_headers,
    make_admin,
    make_business,
    mutation_client,  # noqa: F401
)
from tests.test_customer_app import business_with_card, customer


@pytest.mark.asyncio
async def test_store_coordinates_validation_and_lifecycle(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    superadmin = await make_admin(db_session, "superadmin", None, "coord-super")
    biz = await make_business(db_session, "Biz Coord")
    super_headers = await auth_headers(db_session, superadmin)
    await db_session.commit()

    # 1. Reject single coordinate on creation
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=super_headers,
        json={
            "title_ru": "Магазин 1",
            "title_kk": "1-дүкен",
            "address_ru": "ул. Абая, 1",
            "address_kk": "Абай к-сі, 1",
            "latitude": 43.238949,
        },
    )
    assert res.status_code == 422

    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=super_headers,
        json={
            "title_ru": "Магазин 1",
            "title_kk": "1-дүкен",
            "address_ru": "ул. Абая, 1",
            "address_kk": "Абай к-сі, 1",
            "longitude": 76.889709,
        },
    )
    assert res.status_code == 422

    # 2. Reject out-of-range coordinates
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=super_headers,
        json={
            "title_ru": "Магазин 1",
            "title_kk": "1-дүкен",
            "address_ru": "ул. Абая, 1",
            "address_kk": "Абай к-сі, 1",
            "latitude": 95.0,
            "longitude": 76.0,
        },
    )
    assert res.status_code == 422

    # 3. Create store with valid coordinates
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=super_headers,
        json={
            "title_ru": "Магазин 1",
            "title_kk": "1-дүкен",
            "address_ru": "ул. Абая, 1",
            "address_kk": "Абай к-сі, 1",
            "latitude": 43.238949,
            "longitude": 76.889709,
        },
    )
    assert res.status_code == 201
    store = res.json()
    assert store["latitude"] == pytest.approx(43.238949)
    assert store["longitude"] == pytest.approx(76.889709)
    store_id = store["id"]

    # 4. Partial update latitude without longitude leaves pair valid
    res = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/stores/{store_id}",
        headers=super_headers,
        json={"latitude": 43.250000},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["latitude"] == pytest.approx(43.250000)
    assert updated["longitude"] == pytest.approx(76.889709)

    # 5. Clear coordinates explicitly with both null
    res = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/stores/{store_id}",
        headers=super_headers,
        json={"latitude": None, "longitude": None},
    )
    assert res.status_code == 200
    cleared = res.json()
    assert cleared["latitude"] is None
    assert cleared["longitude"] is None

    # 6. Reject setting only one coordinate to null on store that currently has none
    res = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/stores/{store_id}",
        headers=super_headers,
        json={"latitude": 43.123456},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_loyalty_tiers_lifecycle_and_versioning(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    superadmin = await make_admin(db_session, "superadmin", None, "tier-super")
    biz = await make_business(db_session, "Biz Tiers")
    other_biz = await make_business(db_session, "Other Biz")
    manager = await make_admin(db_session, "business_manager", biz.id, "tier-manager")
    other_manager = await make_admin(db_session, "business_manager", other_biz.id, "other-manager")

    super_headers = await auth_headers(db_session, superadmin)
    mgr_headers = await auth_headers(db_session, manager)
    other_mgr_headers = await auth_headers(db_session, other_manager)
    await db_session.commit()

    # 1. Superadmin can also create tiers
    res = await mutation_client.get(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=super_headers,
    )
    assert res.status_code == 200
    assert res.json() == []

    # 2. Manager creates Level 1 tier
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 1,
            "priority": 1,
            "name_ru": "Нет-нет заглядывает",
            "name_kk": "Нет-нет заглядывает",
            "description_ru": "Стартовый кэшбэк",
            "description_kk": "Бастапқы кэшбэк",
            "turnover_period_months": 6,
            "min_turnover": 0.0,
            "max_turnover": 100000.0,
            "percent": 2.0,
        },
    )
    assert res.status_code == 201, res.text
    t1 = res.json()
    assert t1["level"] == 1
    assert t1["turnover_period_months"] == 6
    assert float(t1["percent"]) == 2.0
    t1_id = t1["id"]

    # 2. Reject duplicate level or duplicate priority
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 1,
            "priority": 2,
            "name_ru": "Дубликат",
            "name_kk": "Дубликат",
            "turnover_period_months": 6,
            "min_turnover": 50000.0,
            "percent": 2.5,
        },
    )
    assert res.status_code == 409

    # 3. Reject invalid turnover_period_months (e.g. 0 or 40)
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 2,
            "priority": 2,
            "name_ru": "Уровень 2",
            "name_kk": "Деңгей 2",
            "turnover_period_months": 0,
            "min_turnover": 100000.0,
            "percent": 3.0,
        },
    )
    assert res.status_code == 422

    # 4. Create Level 2 and Level 3 tiers
    res2 = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 2,
            "priority": 2,
            "name_ru": "Продуктовый эксперт",
            "name_kk": "Продуктовый эксперт",
            "turnover_period_months": 6,
            "min_turnover": 100000.0,
            "max_turnover": 200000.0,
            "percent": 3.0,
        },
    )
    assert res2.status_code == 201

    res3 = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 3,
            "priority": 3,
            "name_ru": "Шоппинг-босс",
            "name_kk": "Шоппинг-босс",
            "turnover_period_months": 6,
            "min_turnover": 200000.0,
            "max_turnover": None,
            "percent": 4.0,
        },
    )
    assert res3.status_code == 201

    # 5. List tiers
    res = await mutation_client.get(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 3
    assert [i["level"] for i in items] == [1, 2, 3]

    # 6. Scoping: other manager cannot view or mutate tiers
    res = await mutation_client.get(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=other_mgr_headers,
    )
    assert res.status_code == 404

    # 7. Update tier
    res = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/loyalty-tiers/{t1_id}",
        headers=mgr_headers,
        json={"percent": 2.5},
    )
    assert res.status_code == 200
    assert float(res.json()["percent"]) == 2.5

    # 8. Delete tier
    res = await mutation_client.delete(
        f"/admin/businesses/{biz.id}/loyalty-tiers/{t1_id}",
        headers=mgr_headers,
    )
    assert res.status_code == 204

    # Remaining list has 2 items
    res = await mutation_client.get(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
    )
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_customer_app_content_and_wallet_contract(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
) -> None:
    user, cust_hdr = await customer(db_session)
    biz, _card = await business_with_card(db_session, user, name="Shop Tiers")
    admin = await make_admin(db_session, "superadmin", None, "cust-super")
    admin_hdr = await auth_headers(db_session, admin)
    await db_session.commit()

    # 1. Add store with coordinates
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=admin_hdr,
        json={
            "title_ru": "Филиал 1",
            "title_kk": "1-бөлімше",
            "address_ru": "Абая, 10",
            "address_kk": "Абай, 10",
            "latitude": 43.238949,
            "longitude": 76.889709,
        },
    )
    assert res.status_code == 201

    # 2. Add loyalty tiers with per-tier period
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=admin_hdr,
        json={
            "level": 1,
            "priority": 1,
            "name_ru": "Нет-нет заглядывает",
            "name_kk": "Нет-нет заглядывает",
            "turnover_period_months": 6,
            "min_turnover": 0.0,
            "max_turnover": 100000.0,
            "percent": 2.0,
        },
    )
    assert res.status_code == 201

    # 3. GET /me/app-content as customer
    res = await mutation_client.get(
        f"/me/app-content?business_id={biz.id}",
        headers=cust_hdr,
    )
    assert res.status_code == 200
    content = res.json()
    assert content["business_id"] == str(biz.id)
    assert len(content["stores"]) >= 1
    assert content["stores"][0]["latitude"] == pytest.approx(43.238949)
    assert content["stores"][0]["longitude"] == pytest.approx(76.889709)
    assert len(content["loyalty_tiers"]) == 1
    tier = content["loyalty_tiers"][0]
    assert tier["level"] == 1
    assert tier["turnover_period_months"] == 6
    assert tier["percent"] == "2.00"
    assert content["loyalty_tiers_version"] >= 2

    # 4. GET /me/cards as customer
    res = await mutation_client.get(
        "/me/cards",
        headers=cust_hdr,
    )
    assert res.status_code == 200
    cards = res.json()
    assert len(cards) >= 1
    c = cards[0]
    assert "loyalty_status" in c
    assert c["loyalty_status"]["known"] is False
    assert c["loyalty_status"]["reason"] == "unconfirmed"
    assert c["loyalty_status"]["program_version"] >= 1


@pytest.mark.asyncio
async def test_loyalty_tier_interval_overlap_and_image_scoping(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
) -> None:
    # Setup test businesses and managers
    biz1 = await make_business(db_session, "Biz Overlap 1")
    biz2 = await make_business(db_session, "Biz Overlap 2")
    mgr1 = await make_admin(db_session, "business_manager", biz1.id, "mgr-overlap-1")
    mgr2 = await make_admin(db_session, "business_manager", biz2.id, "mgr-overlap-2")
    superadmin = await make_admin(db_session, "superadmin", None, "super-overlap")
    h1 = await auth_headers(db_session, mgr1)
    h2 = await auth_headers(db_session, mgr2)
    await auth_headers(db_session, superadmin)
    await db_session.commit()

    # 1. Interval overlap in SAME period (period 6)
    # Tier A: [0, 100000)
    res_a = await mutation_client.post(
        f"/admin/businesses/{biz1.id}/loyalty-tiers",
        headers=h1,
        json={
            "level": 1,
            "priority": 10,
            "name_ru": "Старт",
            "name_kk": "Бастау",
            "turnover_period_months": 6,
            "min_turnover": 0.0,
            "max_turnover": 100000.0,
            "percent": 2.0,
        },
    )
    assert res_a.status_code == 201
    tier_a_id = res_a.json()["id"]

    # Tier B: [100000, 200000) - touching boundary at 100000 is ALLOWED (half-open)
    res_b = await mutation_client.post(
        f"/admin/businesses/{biz1.id}/loyalty-tiers",
        headers=h1,
        json={
            "level": 2,
            "priority": 20,
            "name_ru": "Бронза",
            "name_kk": "Қола",
            "turnover_period_months": 6,
            "min_turnover": 100000.0,
            "max_turnover": 200000.0,
            "percent": 3.0,
        },
    )
    assert res_b.status_code == 201

    # Overlapping Tier: [50000, 150000) -> 409 Conflict
    res_overlap = await mutation_client.post(
        f"/admin/businesses/{biz1.id}/loyalty-tiers",
        headers=h1,
        json={
            "level": 3,
            "priority": 30,
            "name_ru": "Конфликт",
            "name_kk": "Қақтығыс",
            "turnover_period_months": 6,
            "min_turnover": 50000.0,
            "max_turnover": 150000.0,
            "percent": 3.5,
        },
    )
    assert res_overlap.status_code == 409
    assert "overlaps" in res_overlap.json()["error"]["message"]

    # Overlapping with infinite upper bound: [150000, None) -> 409 Conflict with [100000, 200000)
    res_overlap_inf = await mutation_client.post(
        f"/admin/businesses/{biz1.id}/loyalty-tiers",
        headers=h1,
        json={
            "level": 4,
            "priority": 40,
            "name_ru": "Конфликт верх",
            "name_kk": "Қақтығыс жоғары",
            "turnover_period_months": 6,
            "min_turnover": 150000.0,
            "max_turnover": None,
            "percent": 4.0,
        },
    )
    assert res_overlap_inf.status_code == 409

    # 2. Overlap in DIFFERENT period (period 12) is ALLOWED (resolves by priority)
    res_diff_period = await mutation_client.post(
        f"/admin/businesses/{biz1.id}/loyalty-tiers",
        headers=h1,
        json={
            "level": 5,
            "priority": 50,
            "name_ru": "Годовой старт",
            "name_kk": "Жылдық бастау",
            "turnover_period_months": 12,
            "min_turnover": 0.0,
            "max_turnover": 100000.0,
            "percent": 2.5,
        },
    )
    assert res_diff_period.status_code == 201

    # 3. Same range in DIFFERENT business is ALLOWED
    res_diff_biz = await mutation_client.post(
        f"/admin/businesses/{biz2.id}/loyalty-tiers",
        headers=h2,
        json={
            "level": 1,
            "priority": 10,
            "name_ru": "Бизнес 2 Старт",
            "name_kk": "2-бизнес бастау",
            "turnover_period_months": 6,
            "min_turnover": 0.0,
            "max_turnover": 100000.0,
            "percent": 2.0,
        },
    )
    assert res_diff_biz.status_code == 201

    # 4. Inactive tier can overlap with active tier; activating it triggers 409 Conflict
    res_inactive = await mutation_client.post(
        f"/admin/businesses/{biz1.id}/loyalty-tiers",
        headers=h1,
        json={
            "level": 6,
            "priority": 60,
            "name_ru": "Черновик",
            "name_kk": "Нобай",
            "turnover_period_months": 6,
            "min_turnover": 50000.0,
            "max_turnover": 120000.0,
            "percent": 3.0,
            "is_active": False,
        },
    )
    assert res_inactive.status_code == 201
    inactive_id = res_inactive.json()["id"]

    # Try to activate inactive tier -> 409 Conflict
    res_activate = await mutation_client.patch(
        f"/admin/businesses/{biz1.id}/loyalty-tiers/{inactive_id}",
        headers=h1,
        json={"is_active": True},
    )
    assert res_activate.status_code == 409

    # 5. Scoped Image Validation
    storage = InMemoryMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage
    try:
        # Create a real PNG image in memory
        im = Image.new("RGBA", (100, 100), color=(200, 50, 100, 255))
        bio = io.BytesIO()
        im.save(bio, format="PNG")
        png_bytes = bio.getvalue()

        # Manager 1 uploads image for Biz 1
        res_up = await mutation_client.post(
            "/admin/media/images",
            headers=h1,
            data={"purpose": "promotion"},
            files={"file": ("tier_badge.png", png_bytes, "image/png")},
        )
        assert res_up.status_code == 200
        valid_img_url = res_up.json()["url"]

        # 5a. Assign own uploaded image to Biz 1 tier -> 200
        res_img_ok = await mutation_client.patch(
            f"/admin/businesses/{biz1.id}/loyalty-tiers/{tier_a_id}",
            headers=h1,
            json={"image_url": valid_img_url},
        )
        assert res_img_ok.status_code == 200
        assert res_img_ok.json()["image_url"] == valid_img_url

        # 5b. Manager 2 tries to use Biz 1's image in Biz 2 -> 403 Forbidden
        res_img_foreign = await mutation_client.post(
            f"/admin/businesses/{biz2.id}/loyalty-tiers",
            headers=h2,
            json={
                "level": 2,
                "priority": 20,
                "name_ru": "Чужая картинка",
                "name_kk": "Бөтен сурет",
                "turnover_period_months": 6,
                "min_turnover": 100000.0,
                "max_turnover": 200000.0,
                "percent": 3.0,
                "image_url": valid_img_url,
            },
        )
        assert res_img_foreign.status_code == 403

        # 5c. Non-existent image URL on poscenter CDN -> 404 Not Found
        hex32 = "a" * 32
        res_img_404 = await mutation_client.patch(
            f"/admin/businesses/{biz1.id}/loyalty-tiers/{tier_a_id}",
            headers=h1,
            json={"image_url": f"https://cashback-qr.poscenter.kz/media/promotions/{hex32}.webp"},
        )
        assert res_img_404.status_code == 404

        # 5d. Insecure/external protocol URL -> 422
        res_img_http = await mutation_client.patch(
            f"/admin/businesses/{biz1.id}/loyalty-tiers/{tier_a_id}",
            headers=h1,
            json={"image_url": "http://cashback-qr.poscenter.kz/media/promotions/test.webp"},
        )
        assert res_img_http.status_code == 422

        res_img_js = await mutation_client.patch(
            f"/admin/businesses/{biz1.id}/loyalty-tiers/{tier_a_id}",
            headers=h1,
            json={"image_url": "javascript:alert('xss')"},
        )
        assert res_img_js.status_code == 422

        # 5e. Verify old image was preserved after failed patches
        res_tier_check = await mutation_client.get(
            f"/admin/businesses/{biz1.id}/loyalty-tiers",
            headers=h1,
        )
        tier_a_fetched = next(t for t in res_tier_check.json() if t["id"] == tier_a_id)
        assert tier_a_fetched["image_url"] == valid_img_url

        # 5f. Clear image with None/null -> 200
        res_clear_img = await mutation_client.patch(
            f"/admin/businesses/{biz1.id}/loyalty-tiers/{tier_a_id}",
            headers=h1,
            json={"image_url": None},
        )
        assert res_clear_img.status_code == 200
        assert res_clear_img.json()["image_url"] is None
    finally:
        app.dependency_overrides.pop(get_media_storage, None)


@pytest.mark.asyncio
async def test_image_upload_commit_visible_in_new_db_session(db_engine) -> None:
    """Verify that POST /admin/media/images commits the asset,

    so that a subsequent request with a completely NEW DB session
    successfully finds and validates the image_url rather than 404.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # 1. Setup seed data in initial setup session
    async with session_factory() as s0:
        biz = await make_business(s0, "Biz Session Test")
        manager = await make_admin(s0, "business_manager", biz.id, "mgr-session-test")
        headers = await auth_headers(s0, manager)
        await s0.commit()
        biz_id = biz.id

    storage = InMemoryMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter
    _test_limiter.reset()

    # 2. Key test harness: dependency_override yields a FRESH session for each HTTP request
    async def fresh_session_dependency():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = fresh_session_dependency

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://admin.test"
        ) as client:
            im = Image.new("RGBA", (100, 100), color=(100, 200, 150, 255))
            bio = io.BytesIO()
            im.save(bio, format="PNG")
            png_bytes = bio.getvalue()

            # Request 1: POST /admin/media/images in Session 1
            # (Session 1 closes and terminates upon completion of this request)
            res_up = await client.post(
                "/admin/media/images",
                headers=headers,
                data={"purpose": "promotion"},
                files={"file": ("badge.png", png_bytes, "image/png")},
            )
            assert res_up.status_code == 200, res_up.text
            uploaded_url = res_up.json()["url"]

            # Request 2: POST /admin/businesses/{id}/loyalty-tiers in completely NEW Session 2
            # Verifies that BusinessSplashAsset committed in Session 1 is visible in Session 2
            res_tier = await client.post(
                f"/admin/businesses/{biz_id}/loyalty-tiers",
                headers=headers,
                json={
                    "level": 1,
                    "priority": 1,
                    "name_ru": "Тест новой сессии",
                    "name_kk": "Жаңа сессия тесті",
                    "turnover_period_months": 6,
                    "min_turnover": 0.0,
                    "max_turnover": 100000.0,
                    "percent": 2.5,
                    "image_url": uploaded_url,
                },
            )
            assert res_tier.status_code == 201, res_tier.text
            tier_data = res_tier.json()
            assert tier_data["image_url"] == uploaded_url

            # Request 3: Foreign business tries to use this uploaded image in NEW Session 3 -> 403
            async with session_factory() as s_foreign:
                other_biz = await make_business(s_foreign, "Other Biz For Scoping")
                other_mgr = await make_admin(
                    s_foreign, "business_manager", other_biz.id, "other-mgr-scoping"
                )
                other_headers = await auth_headers(s_foreign, other_mgr)
                await s_foreign.commit()
                other_biz_id = other_biz.id

            res_foreign = await client.post(
                f"/admin/businesses/{other_biz_id}/loyalty-tiers",
                headers=other_headers,
                json={
                    "level": 1,
                    "priority": 1,
                    "name_ru": "Чужая картинка",
                    "name_kk": "Бөтен сурет",
                    "turnover_period_months": 6,
                    "min_turnover": 0.0,
                    "max_turnover": 100000.0,
                    "percent": 2.5,
                    "image_url": uploaded_url,
                },
            )
            assert res_foreign.status_code == 403

            # Request 4: Non-existent image URL in NEW Session 4 -> 404
            hex32 = "b" * 32
            res_404 = await client.post(
                f"/admin/businesses/{biz_id}/loyalty-tiers",
                headers=headers,
                json={
                    "level": 2,
                    "priority": 2,
                    "name_ru": "Несуществующая картинка",
                    "name_kk": "Жоқ сурет",
                    "turnover_period_months": 6,
                    "min_turnover": 100000.0,
                    "max_turnover": 200000.0,
                    "percent": 3.0,
                    "image_url": f"https://cashback-qr.poscenter.kz/media/promotions/{hex32}.webp",
                },
            )
            assert res_404.status_code == 404
    finally:
        app.dependency_overrides.pop(get_media_storage, None)
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_rate_limiter, None)


@pytest.mark.asyncio
async def test_loyalty_tiers_auto_priority_and_level_ordering(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
) -> None:
    """Test auto-allocation of priority, conflict avoidance with non-matching priority, and level-based ordering."""
    biz = await make_business(db_session, "Auto Priority Biz")
    manager = await make_admin(db_session, "business_manager", biz.id, "auto-mgr")
    mgr_headers = await auth_headers(db_session, manager)
    await db_session.commit()

    # 1. Create tier with level=1 WITHOUT priority field
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 1,
            "name_ru": "Базовый",
            "name_kk": "Базалық",
            "turnover_period_months": 6,
            "min_turnover": 0.0,
            "max_turnover": 50000.0,
            "percent": 2.0,
        },
    )
    assert res.status_code == 201, res.text
    t1 = res.json()
    assert t1["level"] == 1
    assert t1["priority"] == 1
    t1_id = t1["id"]

    # 2. Create tier with explicit non-matching level=2, priority=5 (e.g. legacy client or custom priority)
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 2,
            "priority": 5,
            "name_ru": "Серебряный",
            "name_kk": "Күміс",
            "turnover_period_months": 6,
            "min_turnover": 50000.0,
            "max_turnover": 100000.0,
            "percent": 3.0,
        },
    )
    assert res.status_code == 201, res.text
    t2 = res.json()
    assert t2["level"] == 2
    assert t2["priority"] == 5

    # 3. Create tier with level=5 WITHOUT priority field.
    # Level 5 matches existing tier t2's priority (5).
    # Auto-allocation must NOT blindly set priority=5, which would cause 409 conflict!
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 5,
            "name_ru": "Платиновый",
            "name_kk": "Платиналық",
            "turnover_period_months": 6,
            "min_turnover": 200000.0,
            "max_turnover": None,
            "percent": 5.0,
        },
    )
    assert res.status_code == 201, res.text
    t5 = res.json()
    assert t5["level"] == 5
    # Priority should be chosen without collision (e.g. 6)
    assert t5["priority"] != 5
    assert t5["priority"] not in (1, 5)
    t5_id = t5["id"]

    # 4. Create tier with level=3, priority=2 (explicit non-matching priority smaller than t2's priority)
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
        json={
            "level": 3,
            "priority": 2,
            "name_ru": "Золотой",
            "name_kk": "Алтын",
            "turnover_period_months": 6,
            "min_turnover": 100000.0,
            "max_turnover": 200000.0,
            "percent": 4.0,
        },
    )
    assert res.status_code == 201, res.text
    t3 = res.json()
    assert t3["level"] == 3
    assert t3["priority"] == 2
    t3_id = t3["id"]

    # 5. List tiers: must be strictly ordered by level ASC: [1, 2, 3, 5],
    # even though priorities are [1, 5, 2, 6] (which would be [1, 2, 5, 6] if ordered by priority)
    res = await mutation_client.get(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 4
    levels = [item["level"] for item in items]
    assert levels == [1, 2, 3, 5], f"Expected levels [1, 2, 3, 5], got {levels}"
    priorities = [item["priority"] for item in items]
    assert priorities == [1, 5, 2, t5["priority"]]

    # 6. Edit existing tier t3 without priority field: existing priority must be preserved
    res = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/loyalty-tiers/{t3_id}",
        headers=mgr_headers,
        json={
            "name_ru": "Золотой VIP",
            "percent": 4.5,
        },
    )
    assert res.status_code == 200, res.text
    updated_t3 = res.json()
    assert updated_t3["name_ru"] == "Золотой VIP"
    assert float(updated_t3["percent"]) == 4.5
    assert updated_t3["priority"] == 2  # priority preserved!

    # 7. Change level of tier t5 from 5 to 4 without priority field
    res = await mutation_client.patch(
        f"/admin/businesses/{biz.id}/loyalty-tiers/{t5_id}",
        headers=mgr_headers,
        json={
            "level": 4,
        },
    )
    assert res.status_code == 200, res.text
    updated_t5 = res.json()
    assert updated_t5["level"] == 4

    # 8. Re-verify listing order after level change: now [1, 2, 3, 4]
    res = await mutation_client.get(
        f"/admin/businesses/{biz.id}/loyalty-tiers",
        headers=mgr_headers,
    )
    assert res.status_code == 200
    levels = [item["level"] for item in res.json()]
    assert levels == [1, 2, 3, 4]

    # 9. Customer app endpoint also returns tiers ordered by level ASC
    _user, cust_hdr = await customer(db_session)
    res_app = await mutation_client.get(
        f"/me/app-content?business_id={biz.id}",
        headers=cust_hdr,
    )
    assert res_app.status_code == 200
    app_tiers = res_app.json()["loyalty_tiers"]
    assert [t["level"] for t in app_tiers] == [1, 2, 3, 4]
