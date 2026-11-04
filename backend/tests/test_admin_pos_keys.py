"""Tests for Admin POS key management (Task B, 2026-11-04).

Covers:
1. Superadmin POS key creation (one-time raw key disclosure, format pos_...).
2. POS keys listing (omits raw key and hash).
3. POS key revocation.
4. Role permissions (only superadmin, manager gets 403).
5. Audit trail hygiene (actions pos_key_created, pos_key_revoked without secrets/hashes).
"""
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser
from app.models.entities import AuditLog, Business, PosKey
from app.services.admin_security import (
    admin_refresh_token_hash,
    create_admin_access_token,
    generate_admin_refresh_token,
    hash_admin_password,
)
from app.services.pos_auth import hash_pos_key
from app.services.rate_limiter import _test_limiter, get_rate_limiter

ORIGIN_HEADERS = {"Origin": "https://admin.test", "X-Admin-Request": "1"}
TEST_PASSWORD = "fixture-admin-pos-password"


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
async def test_pos_key_issuance_and_disclosure(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.poskeys")
    headers = await auth_headers(db_session, root)

    business = Business(name="КассаТест")
    db_session.add(business)
    await db_session.commit()

    # Create POS key
    resp = await admin_client.post(
        f"/admin/businesses/{business.id}/pos-keys",
        headers=headers,
        json={"name": "Касса 1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "api_key" in data
    raw_key = data["api_key"]
    assert raw_key.startswith("pos_")
    assert len(raw_key) >= 36  # prefix + >= 32 chars random

    pos_key_data = data["pos_key"]
    assert pos_key_data["name"] == "Касса 1"
    assert pos_key_data["status"] == "active"
    assert pos_key_data["business_id"] == str(business.id)
    assert pos_key_data["last_used_at"] is None
    assert pos_key_data["revoked_at"] is None

    # Verify DB stores only hash
    pos_key_id = uuid.UUID(pos_key_data["id"])
    db_key = await db_session.get_one(PosKey, pos_key_id)
    assert db_key.key_hash == hash_pos_key(raw_key)
    assert raw_key not in db_key.key_hash


@pytest.mark.asyncio
async def test_list_pos_keys(db_session: AsyncSession, admin_client: AsyncClient) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.poslist")
    headers = await auth_headers(db_session, root)

    biz1 = Business(name="Бизнес 1")
    biz2 = Business(name="Бизнес 2")
    db_session.add_all([biz1, biz2])
    await db_session.commit()

    # Create 2 keys for biz1 and 1 for biz2
    r1 = await admin_client.post(
        f"/admin/businesses/{biz1.id}/pos-keys",
        headers=headers,
        json={"name": "Касса 1.1"},
    )
    assert r1.status_code == 201
    r2 = await admin_client.post(
        f"/admin/businesses/{biz1.id}/pos-keys",
        headers=headers,
        json={"name": "Касса 1.2"},
    )
    assert r2.status_code == 201
    r3 = await admin_client.post(
        f"/admin/businesses/{biz2.id}/pos-keys",
        headers=headers,
        json={"name": "Касса 2.1"},
    )
    assert r3.status_code == 201

    # List keys for biz1
    list_resp = await admin_client.get(
        f"/admin/businesses/{biz1.id}/pos-keys",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 2
    names = [it["name"] for it in items]
    assert "Касса 1.1" in names
    assert "Касса 1.2" in names
    for it in items:
        assert "api_key" not in it
        assert "key_hash" not in it
        assert it["business_id"] == str(biz1.id)


@pytest.mark.asyncio
async def test_revoke_pos_key(db_session: AsyncSession, admin_client: AsyncClient) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.posrevoke")
    headers = await auth_headers(db_session, root)

    biz = Business(name="Бизнес Отзыв")
    db_session.add(biz)
    await db_session.commit()

    create_resp = await admin_client.post(
        f"/admin/businesses/{biz.id}/pos-keys",
        headers=headers,
        json={"name": "Касса для отзыва"},
    )
    assert create_resp.status_code == 201
    key_id = create_resp.json()["pos_key"]["id"]

    # Revoke key
    revoke_resp = await admin_client.post(
        f"/admin/pos-keys/{key_id}/revoke",
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    revoked_data = revoke_resp.json()
    assert revoked_data["status"] == "revoked"
    assert revoked_data["revoked_at"] is not None

    # Idempotent re-revoke
    revoke_again = await admin_client.post(
        f"/admin/pos-keys/{key_id}/revoke",
        headers=headers,
    )
    assert revoke_again.status_code == 200
    assert revoke_again.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_manager_cannot_manage_pos_keys(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    biz = Business(name="Бизнес Менеджера")
    db_session.add(biz)
    await db_session.commit()

    manager = await make_admin(db_session, "business_manager", biz.id, "mgr.poskeys")
    headers = await auth_headers(db_session, manager)

    # List -> 403
    r1 = await admin_client.get(
        f"/admin/businesses/{biz.id}/pos-keys",
        headers=headers,
    )
    assert r1.status_code == 403

    # Create -> 403
    r2 = await admin_client.post(
        f"/admin/businesses/{biz.id}/pos-keys",
        headers=headers,
        json={"name": "Касса Менеджера"},
    )
    assert r2.status_code == 403

    # Revoke -> 403
    fake_key_id = uuid.uuid4()
    r3 = await admin_client.post(
        f"/admin/pos-keys/{fake_key_id}/revoke",
        headers=headers,
    )
    assert r3.status_code == 403


@pytest.mark.asyncio
async def test_audit_trail_for_pos_keys(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.posaudit")
    headers = await auth_headers(db_session, root)

    biz = Business(name="Бизнес Аудит")
    db_session.add(biz)
    await db_session.commit()

    # Create
    create_resp = await admin_client.post(
        f"/admin/businesses/{biz.id}/pos-keys",
        headers=headers,
        json={"name": "Аудит Касса"},
    )
    assert create_resp.status_code == 201
    key_id = create_resp.json()["pos_key"]["id"]
    raw_key = create_resp.json()["api_key"]

    # Revoke
    revoke_resp = await admin_client.post(
        f"/admin/pos-keys/{key_id}/revoke",
        headers=headers,
    )
    assert revoke_resp.status_code == 200

    # Query audit logs
    audit_rows = (
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.business_id == biz.id)
            .order_by(AuditLog.created_at.asc())
        )
    ).all()
    actions = [row.action for row in audit_rows]
    assert "pos_key_created" in actions
    assert "pos_key_revoked" in actions

    for row in audit_rows:
        if row.action in ("pos_key_created", "pos_key_revoked"):
            # Ensure no secret key or key_hash leaked into audit log
            row_str = str(row.before_state) + str(row.after_state)
            assert raw_key not in row_str
            assert "key_hash" not in row_str
            state = row.after_state or {}
            for v in state.values():
                assert not str(v).startswith("pos_")
