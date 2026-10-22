import logging
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser
from app.models.entities import AuditLog, Business
from app.services.admin_security import (
    admin_refresh_token_hash,
    create_admin_access_token,
    generate_admin_refresh_token,
    hash_admin_password,
    normalize_admin_login,
    validate_admin_password,
    verify_admin_password,
)
from app.services.rate_limiter import _test_limiter, get_rate_limiter

ORIGIN_HEADERS = {"Origin": "https://admin.test", "X-Admin-Request": "1"}
TEST_PASSWORD = "fixture-admin-mutations-password"


@pytest.fixture
async def mutation_client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_rate_limiter] = lambda: _test_limiter  # type: ignore[return-value]
    _test_limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
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
async def test_create_business_provisions_manager_account(
    db_session: AsyncSession, mutation_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    root = await make_admin(db_session, "superadmin", None, "root.managerprov")
    headers = await auth_headers(db_session, root)

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Магазин «Ромашка»",
            "status": "active",
        },
    )
    assert resp.status_code == 201
    assert resp.headers.get("Cache-Control") == "no-store"

    data = resp.json()
    business_id = uuid.UUID(data["id"])
    assert "manager_access" in data
    manager_access = data["manager_access"]
    assert manager_access is not None
    raw_password = manager_access["password"]
    login = manager_access["login"]

    assert len(raw_password) >= 16
    validate_admin_password(raw_password)
    # Exclude ambiguous characters 0, O, 1, l, I
    for forbidden in ("0", "O", "1", "l", "I"):
        assert forbidden not in raw_password

    assert login == "magazin-romashka"
    assert normalize_admin_login(login) == login
    assert manager_access["login_url"] == settings.admin_public_url
    assert manager_access["one_time"] is True

    # DB verification: AdminUser exists with correct role, business_id, and hashed password
    manager = await db_session.scalar(
        select(AdminUser).where(AdminUser.login == login)
    )
    assert manager is not None
    assert manager.role == "business_manager"
    assert manager.business_id == business_id
    assert manager.is_active is True
    assert manager.password_hash.startswith("$argon2id$")
    assert raw_password not in manager.password_hash
    assert verify_admin_password(manager.password_hash, raw_password) is True

    # Audit verification
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.business_id == business_id,
            AuditLog.action == "business_manager_created",
        )
    )
    assert audit is not None
    assert audit.actor == root.login
    assert audit.admin_user_id == root.id
    assert audit.after_state == {"id": str(manager.id), "login": login}
    assert raw_password not in str(audit.after_state)
    assert manager.password_hash not in str(audit.after_state)

    # Password does not leak into logs
    assert raw_password not in caplog.text

    # Login works with provisioned credentials
    login_resp = await mutation_client.post(
        "/admin/auth/login",
        headers=ORIGIN_HEADERS,
        json={"login": login, "password": raw_password},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    manager_token = token_data["access_token"]

    manager_headers = {
        **ORIGIN_HEADERS,
        "Authorization": f"Bearer {manager_token}",
    }

    # Manager /admin/me shows role and business
    me_resp = await mutation_client.get("/admin/me", headers=manager_headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()["admin"]
    assert me_data["role"] == "business_manager"
    assert me_data["business"]["id"] == str(business_id)

    # Manager cannot access other business
    other_bid = uuid.uuid4()
    other_resp = await mutation_client.get(
        f"/admin/businesses/{other_bid}", headers=manager_headers
    )
    assert other_resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_create_business_with_create_manager_false(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.nomanager")
    headers = await auth_headers(db_session, root)

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "No Manager Business",
            "create_manager": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    business_id = uuid.UUID(data["id"])
    assert data["manager_access"] is None

    # No manager was provisioned
    mgr_count = await db_session.scalar(
        select(func.count(AdminUser.id)).where(AdminUser.business_id == business_id)
    )
    assert mgr_count == 0


@pytest.mark.asyncio
async def test_login_collision_generates_unique_suffix(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.collision")
    headers = await auth_headers(db_session, root)

    # Pre-create a business manager with login "samara-market"
    b_pre = Business(name="Existing", status="active")
    db_session.add(b_pre)
    await db_session.flush()
    existing_mgr = AdminUser(
        login="samara-market",
        password_hash=hash_admin_password(TEST_PASSWORD),
        role="business_manager",
        business_id=b_pre.id,
        is_active=True,
    )
    db_session.add(existing_mgr)
    await db_session.commit()

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Samara Market"},
    )
    assert resp.status_code == 201
    manager_access = resp.json()["manager_access"]
    new_login = manager_access["login"]

    assert new_login != "samara-market"
    assert new_login.startswith("samara-market-")
    assert normalize_admin_login(new_login) == new_login


@pytest.mark.asyncio
async def test_empty_or_symbolic_business_name_generates_valid_login(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.symbolic")
    headers = await auth_headers(db_session, root)

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "---###---"},
    )
    assert resp.status_code == 201
    manager_access = resp.json()["manager_access"]
    new_login = manager_access["login"]

    assert new_login.startswith("biz-")
    assert normalize_admin_login(new_login) == new_login


@pytest.mark.asyncio
async def test_manager_access_reset_revokes_sessions_and_updates_password(
    db_session: AsyncSession, mutation_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    root = await make_admin(db_session, "superadmin", None, "root.resetmanager")
    headers = await auth_headers(db_session, root)

    # 1. Create business with initial manager
    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Кафе Звезда"},
    )
    assert resp.status_code == 201
    b_id = resp.json()["id"]
    initial_access = resp.json()["manager_access"]
    login = initial_access["login"]
    old_password = initial_access["password"]

    # 2. Manager logs in and gets an active session
    login_resp1 = await mutation_client.post(
        "/admin/auth/login",
        headers=ORIGIN_HEADERS,
        json={"login": login, "password": old_password},
    )
    assert login_resp1.status_code == 200

    manager = await db_session.scalar(select(AdminUser).where(AdminUser.login == login))
    active_sessions = (
        await db_session.scalars(
            select(AdminSession).where(
                AdminSession.admin_user_id == manager.id,
                AdminSession.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(active_sessions) >= 1

    # 3. Superadmin calls POST /admin/businesses/{business_id}/manager-access
    reset_resp = await mutation_client.post(
        f"/admin/businesses/{b_id}/manager-access",
        headers=headers,
    )
    assert reset_resp.status_code == 200
    assert reset_resp.headers.get("Cache-Control") == "no-store"
    new_access = reset_resp.json()
    new_password = new_access["password"]
    assert new_access["login"] == login
    assert new_password != old_password
    assert len(new_password) >= 16
    validate_admin_password(new_password)

    # 4. Active sessions for this manager must now be revoked
    await db_session.refresh(manager)
    unrevoked = (
        await db_session.scalars(
            select(AdminSession).where(
                AdminSession.admin_user_id == manager.id,
                AdminSession.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(unrevoked) == 0

    # 5. Old password fails
    fail_resp = await mutation_client.post(
        "/admin/auth/login",
        headers=ORIGIN_HEADERS,
        json={"login": login, "password": old_password},
    )
    assert fail_resp.status_code == 401

    # 6. New password succeeds
    ok_resp = await mutation_client.post(
        "/admin/auth/login",
        headers=ORIGIN_HEADERS,
        json={"login": login, "password": new_password},
    )
    assert ok_resp.status_code == 200

    # 7. Audit log check
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.business_id == uuid.UUID(b_id),
            AuditLog.action == "business_manager_password_reset",
        )
    )
    assert audit is not None
    assert audit.after_state == {"id": str(manager.id), "login": login}
    assert new_password not in str(audit.after_state)
    assert new_password not in caplog.text


@pytest.mark.asyncio
async def test_manager_access_provisions_manager_if_none_existed(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.lateprov")
    headers = await auth_headers(db_session, root)

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Late Manager Business", "create_manager": False},
    )
    b_id = resp.json()["id"]

    prov_resp = await mutation_client.post(
        f"/admin/businesses/{b_id}/manager-access",
        headers=headers,
    )
    assert prov_resp.status_code == 200
    access = prov_resp.json()
    assert access["login"] == "late-manager-business"
    assert len(access["password"]) >= 16

    login_resp = await mutation_client.post(
        "/admin/auth/login",
        headers=ORIGIN_HEADERS,
        json={"login": access["login"], "password": access["password"]},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_multiple_managers_targets_earliest_created(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.multimanagers")
    headers = await auth_headers(db_session, root)

    business = Business(name="Multi Managers Biz", status="active")
    db_session.add(business)
    await db_session.flush()

    # Create manager 1 (earliest)
    now = utcnow()
    mgr1 = AdminUser(
        login="mgr.first",
        password_hash=hash_admin_password(TEST_PASSWORD),
        role="business_manager",
        business_id=business.id,
        is_active=True,
        created_at=now - timedelta(days=2),
    )
    # Create manager 2 (later)
    mgr2 = AdminUser(
        login="mgr.second",
        password_hash=hash_admin_password(TEST_PASSWORD),
        role="business_manager",
        business_id=business.id,
        is_active=True,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([mgr1, mgr2])
    await db_session.commit()

    resp = await mutation_client.post(
        f"/admin/businesses/{business.id}/manager-access",
        headers=headers,
    )
    assert resp.status_code == 200
    access = resp.json()
    assert access["login"] == "mgr.first"

    await db_session.refresh(mgr1)
    await db_session.refresh(mgr2)

    # mgr1 password hash changed; mgr2 password hash did not change
    assert mgr1.password_hash != hash_admin_password(TEST_PASSWORD)
    assert verify_admin_password(mgr2.password_hash, TEST_PASSWORD) is True


@pytest.mark.asyncio
async def test_business_manager_forbidden_on_manager_access_endpoints(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    business = Business(name="Scoped Biz", status="active")
    db_session.add(business)
    await db_session.flush()

    manager = await make_admin(db_session, "business_manager", business.id, "mgr.scoped")
    m_headers = await auth_headers(db_session, manager)

    # Manager cannot create a business
    create_resp = await mutation_client.post(
        "/admin/businesses",
        headers=m_headers,
        json={"name": "Forbidden Biz"},
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["error"]["code"] == "ADMIN_FORBIDDEN"

    # Manager cannot call /manager-access
    access_resp = await mutation_client.post(
        f"/admin/businesses/{business.id}/manager-access",
        headers=m_headers,
    )
    assert access_resp.status_code == 403
    assert access_resp.json()["error"]["code"] == "ADMIN_FORBIDDEN"
