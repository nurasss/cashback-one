"""Tests for business android_app_id configuration and manager access."""
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser
from app.models.entities import Business
from app.services.admin_security import (
    admin_refresh_token_hash,
    create_admin_access_token,
    generate_admin_refresh_token,
    hash_admin_password,
)
from app.services.rate_limiter import _test_limiter, get_rate_limiter

ORIGIN_HEADERS = {"Origin": "https://admin.test", "X-Admin-Request": "1"}
TEST_PASSWORD = "fixture-admin-mutations-password"


@pytest.fixture
async def admin_client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://admin.test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def make_admin(
    db: AsyncSession, role: str, business_id: uuid.UUID | None, login: str
) -> AdminUser:
    admin = AdminUser(
        login=login,
        password_hash=hash_admin_password(TEST_PASSWORD),
        role=role,
        business_id=business_id,
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    return admin


async def auth_headers(db: AsyncSession, admin: AdminUser) -> dict[str, str]:
    raw = generate_admin_refresh_token()
    session = AdminSession(
        admin_user_id=admin.id,
        refresh_token_hash=admin_refresh_token_hash(raw),
        expires_at=utcnow() + timedelta(hours=8),
    )
    db.add(session)
    await db.flush()
    return {
        **ORIGIN_HEADERS,
        "Authorization": f"Bearer {create_admin_access_token(admin.id, session.id)}",
    }


@pytest.mark.asyncio
async def test_superadmin_can_create_business_with_android_app_id(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.app_id_create")
    headers = await auth_headers(db_session, root)

    resp = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Супермаркет Керемет",
            "android_app_id": "kz.cashbackone.keremet",
            "status": "active",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["android_app_id"] == "kz.cashbackone.keremet"

    b_id = uuid.UUID(data["id"])
    biz_in_db = await db_session.get(Business, b_id)
    assert biz_in_db is not None
    assert biz_in_db.android_app_id == "kz.cashbackone.keremet"


@pytest.mark.asyncio
async def test_business_android_app_id_invalid_format_returns_422(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.app_id_invalid")
    headers = await auth_headers(db_session, root)

    # Missing segment (no dot)
    resp = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Bad App 1", "android_app_id": "nodotpackage"},
    )
    assert resp.status_code == 422

    # Starting with a digit
    resp2 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Bad App 2", "android_app_id": "123.bad.pkg"},
    )
    assert resp2.status_code == 422

    # Double dots
    resp3 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Bad App 3", "android_app_id": "kz..keremet"},
    )
    assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_business_android_app_id_uniqueness(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.app_id_unique")
    headers = await auth_headers(db_session, root)

    # 1. Create first business
    resp1 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Керемет 1",
            "android_app_id": "kz.cashbackone.keremet",
            "create_manager": False,
        },
    )
    assert resp1.status_code == 201

    # 2. Duplicate create fails with 422
    resp2 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Керемет 2",
            "android_app_id": "kz.cashbackone.keremet",
            "create_manager": False,
        },
    )
    assert resp2.status_code == 422
    err_body = resp2.json()
    assert "DUPLICATE_ANDROID_APP_ID" in str(err_body) or "already exists" in str(err_body)

    # 3. Create second business with different app_id
    resp3 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Магазин 2",
            "android_app_id": "kz.cashbackone.magazin2",
            "create_manager": False,
        },
    )
    assert resp3.status_code == 201
    b2_id = resp3.json()["id"]

    # 4. Updating business 2 to use business 1's app_id fails with 422
    resp_update = await admin_client.patch(
        f"/admin/businesses/{b2_id}",
        headers=headers,
        json={"android_app_id": "kz.cashbackone.keremet"},
    )
    assert resp_update.status_code == 422

    # 5. Multiple businesses with NULL/empty android_app_id are allowed
    resp_null1 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Shared Biz 1", "create_manager": False},
    )
    assert resp_null1.status_code == 201

    resp_null2 = await admin_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Shared Biz 2", "create_manager": False},
    )
    assert resp_null2.status_code == 201


@pytest.mark.asyncio
async def test_manager_access_to_android_app_id(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    """Manager can view android_app_id on their business, but cannot update it."""
    root = await make_admin(db_session, "superadmin", None, "root.mgr_test")
    root_headers = await auth_headers(db_session, root)

    resp = await admin_client.post(
        "/admin/businesses",
        headers=root_headers,
        json={
            "name": "Керемет Менеджер Тест",
            "android_app_id": "kz.cashbackone.keremet",
            "create_manager": False,
        },
    )
    assert resp.status_code == 201
    b_id = uuid.UUID(resp.json()["id"])

    manager = await make_admin(
        db_session, "business_manager", b_id, "mgr.keremet"
    )
    mgr_headers = await auth_headers(db_session, manager)

    # 1. Manager CAN view their own business and see android_app_id
    detail_resp = await admin_client.get(
        f"/admin/businesses/{b_id}", headers=mgr_headers
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["android_app_id"] == "kz.cashbackone.keremet"

    # 2. Manager CANNOT view another business
    other_biz = Business(name="Other Biz", status="active")
    db_session.add(other_biz)
    await db_session.commit()

    other_resp = await admin_client.get(
        f"/admin/businesses/{other_biz.id}", headers=mgr_headers
    )
    assert other_resp.status_code == 404

    # 3. Manager CANNOT update their business (PATCH forbidden for business_manager)
    patch_resp = await admin_client.patch(
        f"/admin/businesses/{b_id}",
        headers=mgr_headers,
        json={"android_app_id": "kz.cashbackone.hacked"},
    )
    assert patch_resp.status_code == 403
    assert patch_resp.json()["error"]["code"] == "ADMIN_FORBIDDEN"
