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
