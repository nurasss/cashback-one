"""Tests for business stores, app texts, and customer /me/app-content."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditLog, BusinessStore, UserCard
from tests.test_admin_mutations import (
    auth_headers,
    make_admin,
    make_business,
    mutation_client,  # noqa: F401
)
from tests.test_customer_app import business_with_card, customer


@pytest.mark.asyncio
async def test_superadmin_and_manager_store_lifecycle(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    superadmin = await make_admin(db_session, "superadmin", None, "store-super")
    biz_own = await make_business(db_session, "Biz Own")
    biz_other = await make_business(db_session, "Biz Other")
    manager = await make_admin(
        db_session, "business_manager", biz_own.id, "store-manager"
    )

    super_headers = await auth_headers(db_session, superadmin)
    mgr_headers = await auth_headers(db_session, manager)
    await db_session.commit()

    # 1. Superadmin creates store in biz_own
    res = await mutation_client.post(
        f"/admin/businesses/{biz_own.id}/stores",
        headers=super_headers,
        json={
            "title_ru": "  Супермаркет Керемет  ",
            "title_kk": "Керемет супермаркеті",
            "address_ru": "  проспект Тауелсиздик, 4  ",
            "address_kk": "Тәуелсіздік даңғылы, 4",
            "map_url": "https://2gis.kz/astana/firm/70000001103172202",
            "sort_order": 1,
            "is_active": True,
        },
    )
    assert res.status_code == 201, res.text
    store1 = res.json()
    assert store1["title_ru"] == "Супермаркет Керемет"
    assert store1["address_ru"] == "проспект Тауелсиздик, 4"
    assert store1["sort_order"] == 1
    assert store1["is_active"] is True
    store1_id = store1["id"]

    # 2. Manager creates store in biz_own
    res = await mutation_client.post(
        f"/admin/businesses/{biz_own.id}/stores",
        headers=mgr_headers,
        json={
            "title_ru": "Филиал 2",
            "title_kk": "Филиал 2 kk",
            "address_ru": "ул. Достык, 10",
            "address_kk": "Достық к-сі, 10",
            "sort_order": 2,
        },
    )
    assert res.status_code == 201
    store2 = res.json()
    store2_id = store2["id"]
    assert store2["sort_order"] == 2
    assert store2["is_active"] is True
    assert store2["map_url"] is None

    # 3. Manager lists stores of biz_own
    res = await mutation_client.get(
        f"/admin/businesses/{biz_own.id}/stores",
        headers=mgr_headers,
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert items[0]["id"] == store1_id
    assert items[1]["id"] == store2_id

    # 4. Manager patches store in biz_own
    res = await mutation_client.patch(
        f"/admin/businesses/{biz_own.id}/stores/{store1_id}",
        headers=mgr_headers,
        json={"title_ru": "Обновленный Керемет", "is_active": False},
    )
    assert res.status_code == 200
    assert res.json()["title_ru"] == "Обновленный Керемет"
    assert res.json()["is_active"] is False

    # 5. Manager deletes store2 in biz_own
    res = await mutation_client.delete(
        f"/admin/businesses/{biz_own.id}/stores/{store2_id}",
        headers=mgr_headers,
    )
    assert res.status_code == 204
    assert (
        await db_session.scalar(
            select(BusinessStore).where(
                BusinessStore.id == uuid.UUID(store2_id)
            )
        )
        is None
    )

    # 6. Manager gets 404 for another business
    assert (
        await mutation_client.get(
            f"/admin/businesses/{biz_other.id}/stores", headers=mgr_headers
        )
    ).status_code == 404
    assert (
        await mutation_client.post(
            f"/admin/businesses/{biz_other.id}/stores",
            headers=mgr_headers,
            json={
                "title_ru": "x",
                "title_kk": "x",
                "address_ru": "y",
                "address_kk": "y",
            },
        )
    ).status_code == 404
    assert (
        await mutation_client.patch(
            f"/admin/businesses/{biz_other.id}/stores/{store1_id}",
            headers=mgr_headers,
            json={"title_ru": "hacked"},
        )
    ).status_code == 404
    assert (
        await mutation_client.delete(
            f"/admin/businesses/{biz_other.id}/stores/{store1_id}",
            headers=mgr_headers,
        )
    ).status_code == 404

    # 7. Non-existent business yields 404
    random_biz = uuid.uuid4()
    assert (
        await mutation_client.get(
            f"/admin/businesses/{random_biz}/stores", headers=super_headers
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_store_validation_and_url_security(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    superadmin = await make_admin(db_session, "superadmin", None, "store-val")
    biz = await make_business(db_session, "Val Shop")
    headers = await auth_headers(db_session, superadmin)
    await db_session.commit()

    base_payload = {
        "title_ru": "Магазин",
        "title_kk": "Дүкен",
        "address_ru": "Адрес",
        "address_kk": "Мекенжай",
    }

    # Insecure / invalid map_url schemes
    for bad_url in [
        "http://insecure.example.com",
        "javascript:alert(1)",
        "data:text/html,test",
        "https://",
        "https://   ",
        "ftp://files.example.com",
        "https://" + "a" * 1025,
    ]:
        res = await mutation_client.post(
            f"/admin/businesses/{biz.id}/stores",
            headers=headers,
            json={**base_payload, "map_url": bad_url},
        )
        assert res.status_code == 422, f"Expected 422 for url: {bad_url}"

    # Empty string or whitespace map_url is treated as None
    for empty_url in ["", "   "]:
        res = await mutation_client.post(
            f"/admin/businesses/{biz.id}/stores",
            headers=headers,
            json={**base_payload, "map_url": empty_url},
        )
        assert res.status_code == 201
        assert res.json()["map_url"] is None

    # Empty required string fields
    for field in ["title_ru", "title_kk", "address_ru", "address_kk"]:
        res = await mutation_client.post(
            f"/admin/businesses/{biz.id}/stores",
            headers=headers,
            json={**base_payload, field: "   "},
        )
        assert res.status_code == 422, f"Expected 422 for empty field: {field}"

    # Overly long fields
    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=headers,
        json={**base_payload, "title_ru": "x" * 161},
    )
    assert res.status_code == 422

    res = await mutation_client.post(
        f"/admin/businesses/{biz.id}/stores",
        headers=headers,
        json={**base_payload, "address_ru": "x" * 256},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_app_texts_lifecycle_and_validation(
    db_session: AsyncSession, mutation_client: AsyncClient  # noqa: F811
) -> None:
    superadmin = await make_admin(db_session, "superadmin", None, "texts-super")
    biz_own = await make_business(db_session, "Texts Own")
    biz_other = await make_business(db_session, "Texts Other")
    manager = await make_admin(
        db_session, "business_manager", biz_own.id, "texts-mgr"
    )

    super_headers = await auth_headers(db_session, superadmin)
    mgr_headers = await auth_headers(db_session, manager)
    await db_session.commit()

    # Initial GET returns closed keys with nulls
    res = await mutation_client.get(
        f"/admin/businesses/{biz_own.id}/app-texts",
        headers=super_headers,
    )
    assert res.status_code == 200
    assert res.json() == {
        "home_store_note_lead": {"ru": None, "kk": None},
        "balance_delay_note": {"ru": None, "kk": None},
    }

    # PUT valid texts by manager
    res = await mutation_client.put(
        f"/admin/businesses/{biz_own.id}/app-texts",
        headers=mgr_headers,
        json={
            "home_store_note_lead": {
                "ru": "  Вы можете потратить эти баллы в супермаркете «КеремЕт»  ",
                "kk": "Сіз бұл ұпайларды «КеремЕт» супермаркетінде жұмсай аласыз",
            },
            "balance_delay_note": {
                "ru": "Баллы начисляются после закрытия смены",
                "kk": "Ұпайлар ауысым жабылғаннан кейін есептеледі",
            },
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert (
        body["home_store_note_lead"]["ru"]
        == "Вы можете потратить эти баллы в супермаркете «КеремЕт»"
    )

    # Unknown key is rejected with 422 (closed key set)
    res = await mutation_client.put(
        f"/admin/businesses/{biz_own.id}/app-texts",
        headers=mgr_headers,
        json={
            "unknown_feature_text": {"ru": "error"},
        },
    )
    assert res.status_code == 422

    # Text exceeding 500 characters is rejected with 422
    res = await mutation_client.put(
        f"/admin/businesses/{biz_own.id}/app-texts",
        headers=mgr_headers,
        json={
            "home_store_note_lead": {"ru": "a" * 501, "kk": None},
        },
    )
    assert res.status_code == 422

    # Manager cannot access other business texts
    assert (
        await mutation_client.get(
            f"/admin/businesses/{biz_other.id}/app-texts", headers=mgr_headers
        )
    ).status_code == 404
    assert (
        await mutation_client.put(
            f"/admin/businesses/{biz_other.id}/app-texts",
            headers=mgr_headers,
            json={"home_store_note_lead": {"ru": "x", "kk": "x"}},
        )
    ).status_code == 404

    # Audit log check
    actions = set(
        (
            await db_session.scalars(
                select(AuditLog.action).where(
                    AuditLog.business_id == biz_own.id
                )
            )
        ).all()
    )
    assert "app_texts_updated" in actions


@pytest.mark.asyncio
async def test_customer_app_content_endpoint(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    user, auth = await customer(db_session, "+77019998877")
    biz, _card = await business_with_card(
        db_session, user, name="Keremet Store", barcode="1234567890123"
    )
    other_biz = await make_business(db_session, "Unrelated Biz")

    # Add active and inactive stores
    s1 = BusinessStore(
        business_id=biz.id,
        title_ru="Керемет ТЦ In Plaza",
        title_kk="Керемет In Plaza СОО",
        address_ru="Тауелсиздик, 4",
        address_kk="Тәуелсіздік, 4",
        map_url="https://2gis.kz/astana/firm/70000001103172202",
        sort_order=2,
        is_active=True,
    )
    s2 = BusinessStore(
        business_id=biz.id,
        title_ru="Керемет Экспресс",
        title_kk="Керемет Экспресс kk",
        address_ru="Сыганак, 1",
        address_kk="Сығанақ, 1",
        map_url=None,
        sort_order=1,
        is_active=True,
    )
    s3_inactive = BusinessStore(
        business_id=biz.id,
        title_ru="Закрытая точка",
        title_kk="Жабық нүкте",
        address_ru="Кунаева, 5",
        address_kk="Қонаев, 5",
        sort_order=0,
        is_active=False,
    )
    biz.app_texts = {
        "home_store_note_lead": {
            "ru": "Потратьте баллы в супермаркете «КеремЕт»:",
            "kk": "«КеремЕт» супермаркетінде ұпайларды жұмсаңыз:",
        },
        "balance_delay_note": {
            "ru": "Баллы начисляются после закрытия смены",
            "kk": "Ұпайлар ауысым жабылғаннан кейін түседі",
        },
    }
    db_session.add_all([s1, s2, s3_inactive])
    await db_session.commit()

    # 1. Customer with active card requests app-content
    res = await client.get(
        f"/me/app-content?business_id={biz.id}", headers=auth
    )
    assert res.status_code == 200
    data = res.json()
    assert data["business_id"] == str(biz.id)
    assert len(data["stores"]) == 2
    # Ordered by sort_order ASC: s2 (sort_order 1) comes before s1 (sort_order 2)
    assert data["stores"][0]["title_ru"] == "Керемет Экспресс"
    assert data["stores"][1]["title_ru"] == "Керемет ТЦ In Plaza"
    assert (
        data["app_texts"]["home_store_note_lead"]["ru"]
        == "Потратьте баллы в супермаркете «КеремЕт»:"
    )
    assert "updated_at" in data

    # Headers check
    etag = res.headers.get("ETag")
    assert etag is not None
    assert res.headers.get("Cache-Control") == "private, max-age=300"

    # 2. Re-request with If-None-Match yields 304 Not Modified
    res304 = await client.get(
        f"/me/app-content?business_id={biz.id}",
        headers={**auth, "If-None-Match": etag},
    )
    assert res304.status_code == 304
    assert res304.headers.get("ETag") == etag
    assert res304.headers.get("Cache-Control") == "private, max-age=300"
    assert not res304.content  # empty body on 304

    # 3. Customer without a card of another active business gets 200 (no card required)
    res_no_card = await client.get(
        f"/me/app-content?business_id={other_biz.id}", headers=auth
    )
    assert res_no_card.status_code == 200
    assert res_no_card.json()["business_id"] == str(other_biz.id)
    assert res_no_card.json()["stores"] == []

    # 4. Inactive or non-existent business gets 404
    fake_id = uuid.uuid4()
    assert (
        await client.get(f"/me/app-content?business_id={fake_id}", headers=auth)
    ).status_code == 404

    other_biz.status = "suspended"
    await db_session.commit()
    assert (
        await client.get(f"/me/app-content?business_id={other_biz.id}", headers=auth)
    ).status_code == 404
