"""Admin management of promotions, notifications and loyalty levels."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditLog, Notification, Promotion
from tests.test_admin_mutations import (  # noqa: F401
    auth_headers,
    make_admin,
    make_business,
    mutation_client,
)


@pytest.mark.asyncio
async def test_superadmin_manages_global_and_business_promotions(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "content-super")
    biz = await make_business(db_session, "Shop")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    res = await mutation_client.post("/admin/promotions", headers=headers, json={
        "kind": "banner", "title": "  Выиграй авто  ", "image_url": "https://cdn.example.kz/car.png",
    })
    assert res.status_code == 201, res.text
    banner = res.json()
    assert banner["title"] == "Выиграй авто" and banner["business_id"] is None

    res = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id), "title": "Скидка на хиты", "badge": "Скидка", "sort_order": 1,
    })
    assert res.status_code == 201
    offer_id = res.json()["id"]

    for bad in ({"title": ""}, {"title": "x", "image_url": "http://insecure.kz/a.png"},
                {"title": "x", "starts_at": "2026-10-10T00:00:00Z", "ends_at": "2026-10-01T00:00:00Z"},
                {"title": "x", "kind": "popup"}):
        assert (await mutation_client.post("/admin/promotions", headers=headers, json=bad)).status_code == 422

    res = await mutation_client.patch(f"/admin/promotions/{offer_id}", headers=headers, json={"is_active": False})
    assert res.status_code == 200 and res.json()["is_active"] is False
    assert (await mutation_client.patch(f"/admin/promotions/{offer_id}", headers=headers, json={"title": None})).status_code == 422

    listed = await mutation_client.get("/admin/promotions", headers=headers)
    assert {p["title"] for p in listed.json()["items"]} == {"Выиграй авто", "Скидка на хиты"}
    only_biz = await mutation_client.get(f"/admin/promotions?business_id={biz.id}", headers=headers)
    assert [p["title"] for p in only_biz.json()["items"]] == ["Скидка на хиты"]

    assert (await mutation_client.delete(f"/admin/promotions/{offer_id}", headers=headers)).status_code == 204
    assert await db_session.scalar(select(Promotion).where(Promotion.id == uuid.UUID(offer_id))) is None

    actions = set((await db_session.scalars(select(AuditLog.action))).all())
    assert {"promotion_created", "promotion_updated", "promotion_deleted"} <= actions


@pytest.mark.asyncio
async def test_manager_content_is_scoped_to_own_business(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    own = await make_business(db_session, "Own")
    other = await make_business(db_session, "Other")
    manager = await make_admin(db_session, "business_manager", own.id, "content-manager")
    headers = await auth_headers(db_session, manager)
    foreign = Promotion(title="Foreign", business_id=other.id)
    global_promo = Promotion(title="Global")
    foreign_note = Notification(title="Foreign", body="x", business_id=other.id)
    db_session.add_all([foreign, global_promo, foreign_note])
    await db_session.commit()

    res = await mutation_client.post("/admin/promotions", headers=headers, json={"title": "Mine"})
    assert res.status_code == 201 and res.json()["business_id"] == str(own.id)
    res = await mutation_client.post("/admin/promotions", headers=headers,
                                     json={"title": "Steal", "business_id": str(other.id)})
    assert res.status_code == 404

    titles = {p["title"] for p in (await mutation_client.get("/admin/promotions", headers=headers)).json()["items"]}
    assert titles == {"Mine"}
    for promo in (foreign, global_promo):
        assert (await mutation_client.patch(f"/admin/promotions/{promo.id}", headers=headers,
                                            json={"title": "hacked"})).status_code == 404
        assert (await mutation_client.delete(f"/admin/promotions/{promo.id}", headers=headers)).status_code == 404

    res = await mutation_client.post("/admin/notifications", headers=headers, json={"title": "Новая акция", "body": "Скидки"})
    assert res.status_code == 201 and res.json()["business_id"] == str(own.id)
    notes = (await mutation_client.get("/admin/notifications", headers=headers)).json()["items"]
    assert [n["title"] for n in notes] == ["Новая акция"]
    assert (await mutation_client.delete(f"/admin/notifications/{foreign_note.id}", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_business_loyalty_tiers_update_and_validation(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "tiers-super")
    biz = await make_business(db_session, "Tiers")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    tiers = [
        {"level": 2, "name": "Silver", "threshold": "350000", "percent": "7"},
        {"level": 1, "name": "Base", "threshold": "0", "percent": "3"},
    ]
    res = await mutation_client.patch(f"/admin/businesses/{biz.id}", headers=headers, json={"loyalty_tiers": tiers})
    assert res.status_code == 200, res.text
    assert res.json()["loyalty_tiers"] == [
        {"level": 1, "name": "Base", "threshold": "0", "percent": "3"},
        {"level": 2, "name": "Silver", "threshold": "350000", "percent": "7"},
    ]

    for bad in (
        [],
        [{"level": 1, "threshold": "100", "percent": "3"}],
        [{"level": 1, "threshold": "0", "percent": "3"}, {"level": 2, "threshold": "0", "percent": "5"}],
        [{"level": 2, "threshold": "0", "percent": "3"}, {"level": 1, "threshold": "10", "percent": "5"}],
        [{"level": 1, "threshold": "0", "percent": "300"}],
    ):
        res = await mutation_client.patch(f"/admin/businesses/{biz.id}", headers=headers, json={"loyalty_tiers": bad})
        assert res.status_code == 422, bad


@pytest.mark.asyncio
async def test_promotions_kind_filter_and_window_validation(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    from datetime import timedelta

    from app.core.time import utcnow

    admin = await make_admin(db_session, "superadmin", None, "promo-filter-super")
    biz = await make_business(db_session, "PromoFilterBiz")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    # 1. Create banner and offer
    res_b = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "banner",
        "title": "Main Banner",
    })
    assert res_b.status_code == 201
    banner_id = res_b.json()["id"]

    res_o = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "offer",
        "title": "Special Offer",
    })
    assert res_o.status_code == 201
    offer_id = res_o.json()["id"]

    # 2. Filter by kind
    banners_res = await mutation_client.get(f"/admin/promotions?business_id={biz.id}&kind=banner", headers=headers)
    assert banners_res.status_code == 200
    banner_items = banners_res.json()["items"]
    assert len(banner_items) == 1
    assert banner_items[0]["id"] == banner_id

    offers_res = await mutation_client.get(f"/admin/promotions?business_id={biz.id}&kind=offer", headers=headers)
    assert offers_res.status_code == 200
    offer_items = offers_res.json()["items"]
    assert len(offer_items) == 1
    assert offer_items[0]["id"] == offer_id

    # 3. Create with starts_at in the past is rejected
    past_time = (utcnow() - timedelta(hours=2)).isoformat()
    future_time = (utcnow() + timedelta(days=5)).isoformat()
    bad_past_res = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "offer",
        "title": "Past Offer",
        "starts_at": past_time,
        "ends_at": future_time,
    })
    assert bad_past_res.status_code == 422

    # 4. Valid future window
    start_future = (utcnow() + timedelta(hours=1)).isoformat()
    end_future = (utcnow() + timedelta(days=2)).isoformat()
    good_res = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "offer",
        "title": "Future Offer",
        "starts_at": start_future,
        "ends_at": end_future,
    })
    assert good_res.status_code == 201
    future_id = good_res.json()["id"]

    # 5. Update with ends_at <= starts_at is rejected
    invalid_window = await mutation_client.patch(f"/admin/promotions/{future_id}", headers=headers, json={
        "ends_at": (utcnow() + timedelta(minutes=30)).isoformat(),
    })
    assert invalid_window.status_code == 422

    # 6. Promotion already started in past: editing title does NOT require changing starts_at
    past_promo = Promotion(
        business_id=biz.id,
        kind="offer",
        title="Active Past Promo",
        starts_at=utcnow() - timedelta(days=2),
        ends_at=utcnow() + timedelta(days=2),
    )
    db_session.add(past_promo)
    await db_session.commit()
    await db_session.refresh(past_promo)

    edit_active_res = await mutation_client.patch(f"/admin/promotions/{past_promo.id}", headers=headers, json={
        "title": "Active Past Promo Updated",
    })
    assert edit_active_res.status_code == 200
    assert edit_active_res.json()["title"] == "Active Past Promo Updated"

    # 7. Changing starts_at to a new past time is rejected
    change_to_past_res = await mutation_client.patch(f"/admin/promotions/{past_promo.id}", headers=headers, json={
        "starts_at": (utcnow() - timedelta(days=5)).isoformat(),
    })
    assert change_to_past_res.status_code == 422

    # 8. starts_at=None + ends_at in the past on create -> 422
    res_past_end = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "offer",
        "title": "Expired on create",
        "starts_at": None,
        "ends_at": (utcnow() - timedelta(days=1)).isoformat(),
    })
    assert res_past_end.status_code == 422

    # 9. starts_at=None + ends_at in future on create -> 201
    res_immediate = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "offer",
        "title": "Starts immediately",
        "starts_at": None,
        "ends_at": (utcnow() + timedelta(days=3)).isoformat(),
    })
    assert res_immediate.status_code == 201
    immediate_id = res_immediate.json()["id"]

    # 10. starts_at 30 seconds in the past is rejected (beyond 15s network latency allowance)
    res_slight_past = await mutation_client.post("/admin/promotions", headers=headers, json={
        "business_id": str(biz.id),
        "kind": "offer",
        "title": "30s in the past",
        "starts_at": (utcnow() - timedelta(seconds=30)).isoformat(),
        "ends_at": (utcnow() + timedelta(days=1)).isoformat(),
    })
    assert res_slight_past.status_code == 422

    # 11. Expired promotion (both starts_at and ends_at in past): editing title does NOT require changing dates
    expired_promo = Promotion(
        business_id=biz.id,
        kind="banner",
        title="Expired Banner",
        starts_at=utcnow() - timedelta(days=10),
        ends_at=utcnow() - timedelta(days=1),
    )
    db_session.add(expired_promo)
    await db_session.commit()
    await db_session.refresh(expired_promo)

    edit_expired_res = await mutation_client.patch(f"/admin/promotions/{expired_promo.id}", headers=headers, json={
        "title": "Archived Banner Title",
    })
    assert edit_expired_res.status_code == 200
    assert edit_expired_res.json()["title"] == "Archived Banner Title"

    # 12. Patch setting ends_at in the past for promotion where starts_at is null -> 422
    patch_past_end = await mutation_client.patch(f"/admin/promotions/{immediate_id}", headers=headers, json={
        "ends_at": (utcnow() - timedelta(hours=1)).isoformat(),
    })
    assert patch_past_end.status_code == 422

    # 13. existing ends_at set -> PATCH ends_at: null successfully clears ends_at (perpetual)
    promo_with_end = Promotion(
        business_id=biz.id,
        kind="offer",
        title="Promo with end",
        starts_at=utcnow() + timedelta(hours=1),
        ends_at=utcnow() + timedelta(days=5),
    )
    db_session.add(promo_with_end)
    await db_session.commit()
    await db_session.refresh(promo_with_end)

    patch_clear_end = await mutation_client.patch(f"/admin/promotions/{promo_with_end.id}", headers=headers, json={
        "ends_at": None,
    })
    assert patch_clear_end.status_code == 200
    assert patch_clear_end.json()["ends_at"] is None

    # 14. starts_at set -> PATCH starts_at: null with future ends_at successfully switches to start now
    patch_clear_start = await mutation_client.patch(f"/admin/promotions/{future_id}", headers=headers, json={
        "starts_at": None,
    })
    assert patch_clear_start.status_code == 200
    assert patch_clear_start.json()["starts_at"] is None

    # 15. PATCH starts_at: null on promotion with old ends_at in past -> 422, not 500
    patch_null_start_past_end = await mutation_client.patch(f"/admin/promotions/{expired_promo.id}", headers=headers, json={
        "starts_at": None,
    })
    assert patch_null_start_past_end.status_code == 422
    assert "ends_at must be after starts_at" in patch_null_start_past_end.json()["error"]["message"]

    # 16. dates omitted in PATCH -> existing dates remain untouched, title update on expired record succeeds
    patch_no_dates = await mutation_client.patch(f"/admin/promotions/{expired_promo.id}", headers=headers, json={
        "title": "Still Archived Title",
    })
    assert patch_no_dates.status_code == 200
    assert patch_no_dates.json()["title"] == "Still Archived Title"
    assert patch_no_dates.json()["starts_at"] is not None
    assert patch_no_dates.json()["ends_at"] is not None
