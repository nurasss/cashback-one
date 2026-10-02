import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser, AgentCommand
from app.models.entities import Agent, AuditLog, Business, Card, User, UserCard
from app.services.admin_mutations import sanitize_admin_audit_state
from app.services.admin_security import (
    admin_refresh_token_hash,
    create_admin_access_token,
    generate_admin_refresh_token,
    hash_admin_password,
)
from app.services.agent_auth import hash_agent_key

ORIGIN_HEADERS = {"Origin": "https://admin.test", "X-Admin-Request": "1"}
TEST_PASSWORD = "fixture-admin-mutations-password"


def test_audit_snapshot_removes_secret_fields_and_redacts_secret_values() -> None:
    snapshot = sanitize_admin_audit_state({
        "agent_id": uuid.uuid4(),
        "key_hash": "sha256-fixture-hash",
        "password_hash": "argon-fixture-hash",
        "refresh_token": "adm_rfr_fixture-refresh-secret",
        "wappi_secret": "fixture-wappi-secret",
        "phone": "+77001112233",
        "barcode": "0000000000123",
        "colors": {"primary": "#155d4a", "access_token": "fixture-jwt"},
        "barcode_prefixes": ["012"],
    })
    assert snapshot is not None
    serialized = str(snapshot)
    for secret in (
        "sha256-fixture-hash",
        "argon-fixture-hash",
        "adm_rfr_fixture-refresh-secret",
        "fixture-wappi-secret",
        "+77001112233",
        "0000000000123",
        "fixture-jwt",
    ):
        assert secret not in serialized
    assert snapshot["barcode_prefixes"] == ["012"]


@pytest.fixture
async def mutation_client(db_session: AsyncSession):
    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://admin.test") as client:
        yield client
    app.dependency_overrides.clear()


async def make_business(db: AsyncSession, name: str) -> Business:
    business = Business(name=name, status="active")
    db.add(business)
    await db.flush()
    return business


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
async def test_business_create_update_validation_and_audit_are_atomic(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.businessmut")
    headers = await auth_headers(db_session, root)

    created = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "  Pilot Market  ",
            "logo_url": "https://cdn.example.test/brand.svg?access_token=fixture-secret",
            "colors": {"primary": "#155d4a", "debug_token": "fixture-secret"},
            "barcode_prefixes": [],
            "status": "active",
        },
    )
    assert created.status_code == 201
    business = created.json()
    business_id = uuid.UUID(business["id"])
    assert business["name"] == "Pilot Market"
    assert business["barcode_prefixes"] == []

    updated = await mutation_client.patch(
        f"/admin/businesses/{business_id}",
        headers=headers,
        json={"name": "Pilot Updated", "status": "inactive", "barcode_prefixes": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Pilot Updated"
    assert updated.json()["status"] == "inactive"
    assert updated.json()["barcode_prefixes"] is None

    invalid = [
        {"name": "   "},
        {"name": "x", "status": "pending"},
        {"name": "x", "logo_url": "javascript:alert(1)"},
        {"name": "x", "logo_url": "https://user:pass@example.test/logo.svg"},
        {"name": "x", "colors": {"nested": [[[[[[{"too_deep": 1}]]]]]]}},
    ]
    for payload in invalid:
        response = await mutation_client.post("/admin/businesses", headers=headers, json=payload)
        assert response.status_code == 422

    too_large = await mutation_client.post(
        "/admin/businesses",
        headers={**headers, "Content-Type": "application/json"},
        content=(('{"name":"oversize","colors":{"label":"' + ("x" * 17_000) + '"}}').encode()),
    )
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "ADMIN_REQUEST_TOO_LARGE"

    events = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.business_id == business_id).order_by(AuditLog.created_at, AuditLog.id)
        )
    ).all()
    assert [event.action for event in events] == ["business_created", "business_updated"]
    assert all(event.admin_user_id == root.id and event.actor == root.login for event in events)
    assert events[0].before_state is None
    assert events[0].after_state is not None
    assert events[0].after_state["name"] == "Pilot Market"
    assert events[0].after_state["logo_url"] == "https://cdn.example.test/brand.svg?[REDACTED]"
    assert events[0].after_state["colors"] == {"configured": True, "keys": ["primary"]}
    assert "#155d4a" not in str(events[0].after_state)
    assert "debug_token" not in str(events[0].after_state)
    assert "fixture-secret" not in str(events)


@pytest.mark.asyncio
async def test_manager_cannot_run_any_superadmin_mutation(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    business = await make_business(db_session, "Manager scope")
    manager = await make_admin(db_session, "business_manager", business.id, "manager.mutations")
    agent_key_hash = hash_agent_key("fixture-agent-key")
    agent = Agent(business_id=business.id, key_hash=agent_key_hash, status="active")
    db_session.add(agent)
    await db_session.flush()
    headers = await auth_headers(db_session, manager)
    before = await db_session.scalar(select(func.count(AuditLog.id)))

    responses = [
        await mutation_client.post("/admin/businesses", headers=headers, json={"name": "Denied"}),
        await mutation_client.patch(
            f"/admin/businesses/{business.id}", headers=headers, json={"name": "Denied"}
        ),
        await mutation_client.post(
            "/admin/agents", headers=headers, json={"business_id": str(business.id)}
        ),
        await mutation_client.post(f"/admin/agents/{agent.id}/rotate-key", headers=headers),
        await mutation_client.post(f"/admin/agents/{agent.id}/revoke", headers=headers),
        await mutation_client.post(f"/admin/agents/{agent.id}/full-resync", headers=headers),
    ]
    assert [response.status_code for response in responses] == [403] * 6
    after = await db_session.scalar(select(func.count(AuditLog.id)))
    assert after == before


@pytest.mark.asyncio
async def test_agent_key_one_time_rotation_revocation_and_audit(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    business = await make_business(db_session, "Agent lifecycle")
    root = await make_admin(db_session, "superadmin", None, "root.agentmut")
    headers = await auth_headers(db_session, root)

    created = await mutation_client.post(
        "/admin/agents", headers=headers, json={"business_id": str(business.id)}
    )
    assert created.status_code == 201
    body = created.json()
    agent_id = uuid.UUID(body["agent"]["id"])
    initial_key = body["api_key"]
    assert initial_key.startswith("agk_")
    assert "key_hash" not in created.text
    assert await db_session.scalar(
        select(Agent.key_hash).where(Agent.id == agent_id)
    ) == hash_agent_key(initial_key)

    first_heartbeat = await mutation_client.post(
        "/agent/heartbeat", headers={"X-Agent-Key": initial_key}, json={"version": "1.0.0"}
    )
    assert first_heartbeat.status_code == 200
    key_view = await mutation_client.get(f"/admin/agents/{agent_id}/key", headers=headers)
    assert key_view.status_code == 404

    rotated = await mutation_client.post(f"/admin/agents/{agent_id}/rotate-key", headers=headers)
    assert rotated.status_code == 200
    next_key = rotated.json()["api_key"]
    assert next_key != initial_key
    assert "key_hash" not in rotated.text
    old_key_result = await mutation_client.post(
        "/agent/heartbeat", headers={"X-Agent-Key": initial_key}, json={}
    )
    new_key_result = await mutation_client.post(
        "/agent/heartbeat", headers={"X-Agent-Key": next_key}, json={}
    )
    assert old_key_result.status_code == 401
    assert old_key_result.json()["error"]["code"] == "AGENT_KEY_INVALID"
    assert new_key_result.status_code == 200

    listing = await mutation_client.get("/admin/agents", headers=headers)
    assert initial_key not in listing.text and next_key not in listing.text
    assert "key_hash" not in listing.text

    revoked = await mutation_client.post(f"/admin/agents/{agent_id}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["agent"]["status"] == "revoked"
    rejected_key = await mutation_client.post(
        "/agent/heartbeat", headers={"X-Agent-Key": next_key}, json={}
    )
    assert rejected_key.status_code == 403
    assert rejected_key.json()["error"]["code"] == "AGENT_REVOKED"
    assert "key_hash" not in revoked.text

    audits = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.business_id == business.id).order_by(AuditLog.created_at, AuditLog.id)
        )
    ).all()
    assert [event.action for event in audits] == ["agent_created", "agent_key_rotated", "agent_revoked"]
    assert all(event.admin_user_id == root.id for event in audits)
    assert initial_key not in str(audits) and next_key not in str(audits)
    assert "key_hash" not in str(audits)
    assert audits[1].after_state == {
        "agent_id": str(agent_id),
        "business_id": str(business.id),
        "key_rotated": True,
        "rotated_at": audits[1].after_state["rotated_at"],
    }


@pytest.mark.asyncio
async def test_full_resync_is_durable_idempotent_and_stays_pending(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    business = await make_business(db_session, "Resync business")
    root = await make_admin(db_session, "superadmin", None, "root.resync")
    agent = Agent(business_id=business.id, key_hash=hash_agent_key("fixture-resync-key"), status="active")
    db_session.add(agent)
    await db_session.flush()
    headers = await auth_headers(db_session, root)

    first = await mutation_client.post(f"/admin/agents/{agent.id}/full-resync", headers=headers)
    second = await mutation_client.post(f"/admin/agents/{agent.id}/full-resync", headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["command_id"] == second.json()["command_id"]
    assert first.json()["status"] == "pending"
    assert first.json()["execution"] == "deferred"
    assert "completed" not in first.text.lower()

    commands = (
        await db_session.scalars(
            select(AgentCommand).where(AgentCommand.agent_id == agent.id)
        )
    ).all()
    assert len(commands) == 1
    assert commands[0].status == "pending"
    assert commands[0].created_by_admin_id == root.id
    audits = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.business_id == business.id)
        )
    ).all()
    assert [event.action for event in audits] == ["agent_full_resync_requested"]
    assert audits[0].after_state == {
        "command_id": str(commands[0].id),
        "agent_id": str(agent.id),
        "business_id": str(business.id),
    }


@pytest.mark.asyncio
async def test_manager_unbind_is_scoped_idempotent_and_does_not_delete_business_data(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    tenant_a = await make_business(db_session, "Unbind A")
    tenant_b = await make_business(db_session, "Unbind B")
    manager = await make_admin(db_session, "business_manager", tenant_a.id, "manager.unbind")
    root = await make_admin(db_session, "superadmin", None, "root.unbind")
    user = User(phone="+77009991122", language="ru")
    db_session.add(user)
    await db_session.flush()
    card_a = Card(
        business_id=tenant_a.id,
        barcode="0000000000011",
        phone=user.phone,
        full_name="Fixture Owner",
        balance=Decimal("123.4500"),
    )
    card_b = Card(
        business_id=tenant_b.id,
        barcode="0000000000022",
        phone=user.phone,
        full_name="Fixture Owner",
        balance=Decimal("234.5600"),
    )
    db_session.add_all([card_a, card_b])
    await db_session.flush()
    binding_a = UserCard(user_id=user.id, card_id=card_a.id, bound_at=datetime.now(UTC), bind_method="manual_barcode")
    binding_b = UserCard(user_id=user.id, card_id=card_b.id, bound_at=datetime.now(UTC), bind_method="manual_barcode")
    db_session.add_all([binding_a, binding_b])
    await db_session.flush()
    manager_headers = await auth_headers(db_session, manager)
    root_headers = await auth_headers(db_session, root)

    foreign = await mutation_client.post(
        f"/admin/cards/{card_b.id}/unbind", headers=manager_headers
    )
    assert foreign.status_code == 404
    result = await mutation_client.post(
        f"/admin/cards/{card_a.id}/unbind", headers=manager_headers
    )
    assert result.status_code == 200
    assert result.json() == {"status": "unbound"}
    repeated = await mutation_client.post(
        f"/admin/cards/{card_a.id}/unbind", headers=manager_headers
    )
    assert repeated.status_code == 200
    assert repeated.json() == {"status": "already_unbound"}
    superadmin_unbind = await mutation_client.post(
        f"/admin/cards/{card_b.id}/unbind", headers=root_headers
    )
    assert superadmin_unbind.status_code == 200
    assert superadmin_unbind.json() == {"status": "unbound"}

    assert await db_session.get(Card, card_a.id) is not None
    assert await db_session.get(Card, card_b.id) is not None
    assert (await db_session.get(Card, card_a.id)).balance == Decimal("123.4500")
    assert await db_session.get(User, user.id) is not None
    assert await db_session.scalar(select(UserCard.id).where(UserCard.card_id == card_a.id)) is None
    assert await db_session.scalar(select(UserCard.id).where(UserCard.card_id == card_b.id)) is None

    manager_audit = await mutation_client.get("/admin/audit", headers=manager_headers)
    assert manager_audit.status_code == 200
    assert len(manager_audit.json()["items"]) == 1
    row = manager_audit.json()["items"][0]
    assert row["action"] == "card_unbound"
    assert row["business_id"] == str(tenant_a.id)
    assert row["before_state"]["user_id"] == str(user.id)
    assert user.phone not in str(row)
    assert card_a.barcode not in str(row)

    global_audit = await mutation_client.get("/admin/audit", headers=root_headers)
    assert global_audit.status_code == 200
    assert len(global_audit.json()["items"]) == 2
