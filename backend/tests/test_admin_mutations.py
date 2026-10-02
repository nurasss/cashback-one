import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token as create_customer_access_token
from app.core.security import hash_refresh_token
from app.core.time import utcnow
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser, AgentCommand
from app.models.entities import Agent, AuditLog, AuthSession, Business, Card, User, UserCard
from app.services.admin_mutations import safe_audit_snapshot, sanitize_admin_audit_state
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

    # Unknown or legacy action -> fails closed to None
    assert (
        safe_audit_snapshot(
            "unknown_legacy_action",
            {
                "DATABASE_URL": "postgresql://fixture:fixture-password@localhost/db",
                "ONE_CONNECTION_STRING": "Provider=fixture;Password=secret",
            },
            admin_user_id=uuid.uuid4(),
            business_id=uuid.uuid4(),
        )
        is None
    )
    assert safe_audit_snapshot(None, {"name": "test"}) is None

    # Missing structural provenance (admin_user_id or business_id is None) fails closed to None
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    assert (
        safe_audit_snapshot(
            "agent_created",
            {"agent_id": aid, "business_id": bid, "status": "active"},
            admin_user_id=None,
            business_id=bid,
        )
        is None
    )
    assert (
        safe_audit_snapshot(
            "agent_created",
            {"agent_id": aid, "business_id": bid, "status": "active"},
            admin_user_id=aid,
            business_id=None,
        )
        is None
    )

    # Known action with verified provenance projects only allowlisted safe keys and redacts secrets
    projected_agent = safe_audit_snapshot(
        "agent_created",
        {
            "agent_id": aid,
            "business_id": bid,
            "status": "active",
            "key_hash": "secret-hash",
            "api_key": "agk_secret-key",
            "ONE_CONNECTION_STRING": "Provider=fixture;Password=secret",
        },
        admin_user_id=uuid.uuid4(),
        business_id=bid,
    )
    assert projected_agent == {
        "agent_id": str(aid),
        "business_id": str(bid),
        "status": "active",
    }
    assert "key_hash" not in str(projected_agent)
    assert "secret" not in str(projected_agent)


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
    assert events[0].after_state["business_id"] == str(business_id)
    assert events[0].after_state["status"] == "active"
    assert events[0].after_state["configured_fields"] == [
        "barcode_prefixes",
        "colors",
        "logo_url",
        "name",
        "status",
    ]
    assert events[0].after_state["colors"] == {"configured": True}
    assert "name" not in events[0].after_state
    assert "logo_url" not in events[0].after_state
    assert "barcode_prefixes" not in events[0].after_state
    assert "Pilot Market" not in str(events[0].after_state)
    assert "#155d4a" not in str(events[0].after_state)
    assert "debug_token" not in str(events[0].after_state)
    assert "fixture-secret" not in str(events)

    assert events[1].before_state is not None
    assert events[1].before_state["status"] == "active"
    assert events[1].after_state is not None
    assert events[1].after_state["business_id"] == str(business_id)
    assert events[1].after_state["status"] == "inactive"
    assert events[1].after_state["changed_fields"] == ["barcode_prefixes", "name", "status"]
    assert "name" not in events[1].after_state
    assert "Pilot Updated" not in str(events[1].after_state)


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


@pytest.mark.asyncio
async def test_legacy_audit_snapshot_secrets_are_never_disclosed_at_read_time(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.legacyaudit")
    root_headers = await auth_headers(db_session, root)

    tenant = await make_business(db_session, "Tenant Audit Scope")
    manager = await make_admin(db_session, "business_manager", tenant.id, "manager.legacyaudit")
    manager_headers = await auth_headers(db_session, manager)

    # Insert legacy AuditLog row containing raw secrets, credentials, and connection strings
    legacy_log = AuditLog(
        actor="legacy_system_migrator",
        admin_user_id=None,
        business_id=None,
        action="legacy_system_sync",
        entity="system",
        before_state={
            "ONE_CONNECTION_STRING": "Provider=fixture;Password=fixture-one-db-secret",
            "DATABASE_URL": "postgresql://fixture:fixture-db-password@localhost/db",
        },
        after_state={
            "nested": {
                "password": "fixture-nested-secret",
                "token": "fixture-token-secret",
            }
        },
    )
    db_session.add(legacy_log)
    await db_session.commit()

    # Authenticated superadmin GET /admin/audit
    response = await mutation_client.get("/admin/audit", headers=root_headers)
    assert response.status_code == 200
    res_text = response.text

    # Assert response JSON does NOT contain any fixture secret string or raw connection string
    for secret in (
        "fixture-one-db-secret",
        "fixture-db-password",
        "fixture-nested-secret",
        "fixture-token-secret",
        "Provider=fixture",
        "postgresql://",
    ):
        assert secret not in res_text, f"Secret string '{secret}' found in /admin/audit response!"

    items = response.json()["items"]
    legacy_item = next((item for item in items if item["id"] == str(legacy_log.id)), None)
    assert legacy_item is not None
    assert legacy_item["before_state"] is None
    assert legacy_item["after_state"] is None

    # Manager isolation check: legacy row has no business_id and must be invisible to manager
    manager_res = await mutation_client.get("/admin/audit", headers=manager_headers)
    assert manager_res.status_code == 200
    assert not any(item["id"] == str(legacy_log.id) for item in manager_res.json()["items"])


@pytest.mark.asyncio
async def test_mutation_audit_events_never_record_raw_keys_hashes_or_passwords(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.auditwritetest")
    headers = await auth_headers(db_session, root)

    # 1. Create Business
    b_resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Audit Security Business", "status": "active"},
    )
    assert b_resp.status_code == 201
    business_id = b_resp.json()["id"]

    # 2. Create Agent
    a_resp = await mutation_client.post(
        "/admin/agents",
        headers=headers,
        json={"business_id": business_id},
    )
    assert a_resp.status_code == 201
    agent_id = a_resp.json()["agent"]["id"]
    raw_key = a_resp.json()["api_key"]
    assert raw_key.startswith("agk_")

    # 3. Rotate Agent Key
    rot_resp = await mutation_client.post(
        f"/admin/agents/{agent_id}/rotate-key",
        headers=headers,
    )
    assert rot_resp.status_code == 200
    rotated_key = rot_resp.json()["api_key"]
    assert rotated_key.startswith("agk_")
    assert rotated_key != raw_key

    # Query all audit logs for this business
    events = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.business_id == uuid.UUID(business_id))
        )
    ).all()
    assert len(events) >= 3

    for ev in events:
        ev_str = f"{ev.before_state} {ev.after_state}"
        assert raw_key not in ev_str, f"Raw key leaked in audit event {ev.action}"
        assert rotated_key not in ev_str, f"Rotated key leaked in audit event {ev.action}"
        assert "key_hash" not in ev_str, f"Key hash leaked in audit event {ev.action}"
        assert "password" not in ev_str
        assert "token" not in ev_str
        assert "secret" not in ev_str


@pytest.mark.asyncio
async def test_business_colors_validation_rejects_non_string_types(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.colorval")
    headers = await auth_headers(db_session, root)

    business = await make_business(db_session, "Color Test Business")

    invalid_color_payloads = [
        {"primary": 123},
        {"accent": {"bad": "type"}},
        {"primary_color": []},
        {"accent_color": False},
        {"primary": "valid", "accent": 456},
        {"primary": ["#fff"]},
    ]

    # Verify POST /admin/businesses returns 422 for each
    for colors in invalid_color_payloads:
        resp = await mutation_client.post(
            "/admin/businesses",
            headers=headers,
            json={"name": "Bad Colors", "colors": colors},
        )
        assert resp.status_code == 422, f"Expected 422 for colors {colors}, got {resp.status_code}"

    # Verify PATCH /admin/businesses/{id} returns 422 for each
    for colors in invalid_color_payloads:
        resp = await mutation_client.patch(
            f"/admin/businesses/{business.id}",
            headers=headers,
            json={"colors": colors},
        )
        assert resp.status_code == 422, f"Expected 422 for colors {colors}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_business_colors_contract_with_customer_wallet_end_to_end(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.brandinge2e")
    headers = await auth_headers(db_session, root)

    # 1. Superadmin creates Business with valid colors and logo
    valid_colors = {
        "primary": "#155d4a",
        "accent": "#f59e0b",
    }
    create_resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Branding Safe Market",
            "logo_url": "https://cdn.example.test/branding_logo.svg",
            "colors": valid_colors,
        },
    )
    assert create_resp.status_code == 201
    business_data = create_resp.json()
    b_id = uuid.UUID(business_data["id"])

    # 2. Create card of this business
    card = Card(
        business_id=b_id,
        barcode="9988776655443",
        phone="+77028889900",
        balance=Decimal("250.0000"),
        is_blocked=False,
    )
    db_session.add(card)

    # 3. Create user and bind card
    user = User(phone="+77028889900", language="ru")
    db_session.add(user)
    await db_session.flush()

    user_card = UserCard(
        user_id=user.id,
        card_id=card.id,
        bind_method="manual",
    )
    db_session.add(user_card)

    auth_session = AuthSession(
        user_id=user.id,
        device_id="branding-device-uuid",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    await db_session.commit()

    # 4. Customer requests GET /me/cards
    customer_token = create_customer_access_token(user_id=user.id, session_id=auth_session.id)
    customer_resp = await mutation_client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    # 5. Must return 200 (not 500)
    assert customer_resp.status_code == 200
    cards_data = customer_resp.json()
    assert len(cards_data) == 1
    card_view = cards_data[0]
    assert card_view["id"] == str(card.id)

    # 6. Branding successfully serialized
    branding = card_view["business"]["branding"]
    assert branding is not None
    assert branding["primary_color"] == "#155d4a"
    assert branding["accent_color"] == "#f59e0b"
    assert branding["logo_url"] == "https://cdn.example.test/branding_logo.svg"


@pytest.mark.asyncio
async def test_legacy_audit_snapshot_with_known_action_fails_closed_and_never_discloses_secrets(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.legacyknownaction")
    root_headers = await auth_headers(db_session, root)

    # Legacy row with known action "business_created" but NULL admin_user_id and NULL business_id
    legacy_known_action_log = AuditLog(
        actor="legacy_system",
        admin_user_id=None,
        business_id=None,
        action="business_created",
        entity="business",
        before_state={
            "colors": {
                "nested": {
                    "opaque": "fixture-nested-secret",
                }
            },
            "name": {
                "label": "fixture-token-secret",
            },
        },
        after_state={
            "colors": {
                "nested": {
                    "opaque": "fixture-nested-secret",
                }
            },
            "name": {
                "label": "fixture-token-secret",
            },
        },
    )
    db_session.add(legacy_known_action_log)
    await db_session.commit()

    # Authenticated superadmin GET /admin/audit
    response = await mutation_client.get("/admin/audit", headers=root_headers)
    assert response.status_code == 200
    res_text = response.text

    # Assert response body does NOT contain fixture-nested-secret or fixture-token-secret
    assert "fixture-nested-secret" not in res_text
    assert "fixture-token-secret" not in res_text

    items = response.json()["items"]
    legacy_item = next(
        (item for item in items if item["id"] == str(legacy_known_action_log.id)), None
    )
    assert legacy_item is not None
    assert legacy_item["before_state"] is None
    assert legacy_item["after_state"] is None


def test_known_action_alone_without_admin_provenance_fails_closed() -> None:
    # Known action + missing Admin provenance = NO snapshot disclosure
    valid_payload = {
        "id": str(uuid.uuid4()),
        "name": "Trusted Name",
        "status": "active",
        "logo_url": "https://cdn.example.test/logo.svg",
    }
    # missing admin_user_id
    assert (
        safe_audit_snapshot(
            "business_created",
            valid_payload,
            admin_user_id=None,
            business_id=uuid.uuid4(),
        )
        is None
    )
    # missing business_id
    assert (
        safe_audit_snapshot(
            "business_created",
            valid_payload,
            admin_user_id=uuid.uuid4(),
            business_id=None,
        )
        is None
    )
    # both missing
    assert (
        safe_audit_snapshot(
            "business_created",
            valid_payload,
            admin_user_id=None,
            business_id=None,
        )
        is None
    )

    # same for other actions
    assert (
        safe_audit_snapshot(
            "agent_created",
            {"agent_id": str(uuid.uuid4()), "business_id": str(uuid.uuid4()), "status": "active"},
            admin_user_id=None,
            business_id=uuid.uuid4(),
        )
        is None
    )
    assert (
        safe_audit_snapshot(
            "card_unbound",
            {"card_id": str(uuid.uuid4()), "business_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4())},
            admin_user_id=None,
            business_id=uuid.uuid4(),
        )
        is None
    )


def test_trusted_admin_event_strict_shape_drops_malformed_and_opaque_structures() -> None:
    admin_id = uuid.uuid4()
    b_id = uuid.uuid4()

    malformed_payload = {
        "name": {"label": "fixture-secret"},  # non-string name
        "colors": {
            "primary": "#123456",
            "nested": {
                "secret": "fixture-secret",
            },
            "opaque": "real-secret-value",
        },
        "barcode_prefixes": [
            "123",
            {"secret": "fixture-secret"},  # non-string element in list
        ],
        "status": {
            "secret": "fixture-secret",  # non-string status
        },
    }

    projected = safe_audit_snapshot(
        "business_created",
        malformed_payload,
        admin_user_id=admin_id,
        business_id=b_id,
    )

    assert projected is not None
    # name dropped because it was a dict
    assert "name" not in projected
    # status dropped because it was a dict
    assert "status" not in projected
    # barcode_prefixes dropped because it contained a non-string item
    assert "barcode_prefixes" not in projected
    # colors kept safe boolean metadata, dropped raw values, nested, and opaque
    assert projected["colors"] == {"configured": True}
    assert "#123456" not in str(projected)
    assert "nested" not in str(projected)
    assert "opaque" not in str(projected)
    assert "fixture-secret" not in str(projected)
    assert "real-secret-value" not in str(projected)


@pytest.mark.asyncio
async def test_trusted_new_admin_event_retains_safe_structured_snapshot(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.trustedaudit")
    headers = await auth_headers(db_session, root)

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={
            "name": "Legitimate Trusted Market",
            "logo_url": "https://cdn.example.test/trusted_logo.svg",
            "colors": {"primary": "#155d4a", "accent": "#f59e0b"},
            "barcode_prefixes": ["999"],
            "status": "active",
        },
    )
    assert resp.status_code == 201
    business_id = resp.json()["id"]

    audit_resp = await mutation_client.get("/admin/audit", headers=headers)
    assert audit_resp.status_code == 200
    items = audit_resp.json()["items"]
    event = next((ev for ev in items if ev["business_id"] == business_id), None)
    assert event is not None
    assert event["action"] == "business_created"
    assert event["admin_user_id"] == str(root.id)
    assert event["after_state"] is not None
    assert event["after_state"]["business_id"] == str(business_id)
    assert event["after_state"]["status"] == "active"
    assert event["after_state"]["configured_fields"] == [
        "barcode_prefixes",
        "colors",
        "logo_url",
        "name",
        "status",
    ]
    assert event["after_state"]["colors"] == {"configured": True}
    assert "name" not in event["after_state"]
    assert "logo_url" not in event["after_state"]
    assert "barcode_prefixes" not in event["after_state"]
    assert "Legitimate Trusted Market" not in str(event["after_state"])
    assert "#155d4a" not in str(event["after_state"])
    assert "999" not in str(event["after_state"])


@pytest.mark.asyncio
async def test_agent_api_key_cannot_be_exfiltrated_via_business_config_into_audit(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    # 1. Superadmin creates a business and an agent to get active key K
    root = await make_admin(db_session, "superadmin", None, "root.keyexfil")
    headers = await auth_headers(db_session, root)

    b_resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Exfil Target Business", "status": "active"},
    )
    assert b_resp.status_code == 201
    business_id = uuid.UUID(b_resp.json()["id"])

    # Manager for this business
    manager = await make_admin(db_session, "business_manager", business_id, "manager.keyexfil")
    manager_headers = await auth_headers(db_session, manager)

    # 2. Superadmin creates Agent and obtains active Agent API key K
    agent_resp = await mutation_client.post(
        "/admin/agents",
        headers=headers,
        json={"business_id": str(business_id)},
    )
    assert agent_resp.status_code == 201
    raw_key_k = agent_resp.json()["api_key"]
    assert raw_key_k.startswith("agk_")

    # 3. Verify key K actively works on /agent/heartbeat
    hb_resp = await mutation_client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": raw_key_k},
        json={},
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "ok"

    # 4. Superadmin performs PATCH Business with user-controlled data injecting K
    injected_logo_url = f"https://cdn.example.test/{raw_key_k}.svg"
    injected_name = f"Injected Name {raw_key_k}"
    injected_colors = {raw_key_k: "#ffffff"}
    patch_resp = await mutation_client.patch(
        f"/admin/businesses/{business_id}",
        headers=headers,
        json={
            "name": injected_name,
            "logo_url": injected_logo_url,
            "colors": injected_colors,
        },
    )
    assert patch_resp.status_code == 200
    # Business domain model stores values without breaking business operation
    assert patch_resp.json()["name"] == injected_name
    assert patch_resp.json()["logo_url"] == injected_logo_url

    # 5. Direct Database AuditLog assertion: K is NOT stored in the database row
    audit_rows = (
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.business_id == business_id, AuditLog.action == "business_updated")
        )
    ).all()
    assert len(audit_rows) == 1
    updated_audit = audit_rows[0]

    assert raw_key_k not in str(updated_audit.before_state)
    assert raw_key_k not in str(updated_audit.after_state)
    assert raw_key_k not in str(updated_audit.entity)
    assert raw_key_k not in str(updated_audit.action)
    assert raw_key_k not in str(updated_audit.actor)
    assert raw_key_k not in str(updated_audit.__dict__)

    # 6. Superadmin API assertion: GET /admin/audit does NOT disclose K
    superadmin_audit_resp = await mutation_client.get("/admin/audit", headers=headers)
    assert superadmin_audit_resp.status_code == 200
    assert raw_key_k not in superadmin_audit_resp.text

    # 7. Manager API assertion: GET /admin/audit does NOT disclose K
    manager_audit_resp = await mutation_client.get("/admin/audit", headers=manager_headers)
    assert manager_audit_resp.status_code == 200
    assert raw_key_k not in manager_audit_resp.text

    # Manager receives safe semantic metadata instead
    manager_items = manager_audit_resp.json()["items"]
    event = next(ev for ev in manager_items if ev["action"] == "business_updated")
    assert event["after_state"]["business_id"] == str(business_id)
    assert event["after_state"]["changed_fields"] == ["colors", "logo_url", "name"]
    assert event["after_state"]["colors"] == {"configured": True}
    assert "name" not in event["after_state"]
    assert "logo_url" not in event["after_state"]


@pytest.mark.asyncio
async def test_historical_trusted_business_snapshot_drops_arbitrary_free_form_values(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.historicalsafe")
    headers = await auth_headers(db_session, root)
    business = await make_business(db_session, "Historical Business")

    manager = await make_admin(db_session, "business_manager", business.id, "manager.historicalsafe")
    manager_headers = await auth_headers(db_session, manager)

    # Insert trusted-provenance fixture of old FIX-B shape directly into DB
    historical_log = AuditLog(
        actor=root.login,
        admin_user_id=root.id,
        business_id=business.id,
        action="business_updated",
        entity="business",
        before_state={"business_id": str(business.id), "status": "active"},
        after_state={
            "business_id": str(business.id),
            "name": "fixture-secret-a",
            "logo_url": "https://example.test/fixture-secret-b",
            "colors": {
                "primary": "fixture-secret-c",
            },
        },
    )
    db_session.add(historical_log)
    await db_session.commit()

    # GET /admin/audit as superadmin MUST NOT contain any of the secrets
    audit_resp = await mutation_client.get("/admin/audit", headers=headers)
    assert audit_resp.status_code == 200
    assert "fixture-secret-a" not in audit_resp.text
    assert "fixture-secret-b" not in audit_resp.text
    assert "fixture-secret-c" not in audit_resp.text

    item = next(it for it in audit_resp.json()["items"] if it["id"] == str(historical_log.id))
    assert item["after_state"] is not None
    assert item["after_state"]["business_id"] == str(business.id)
    assert item["after_state"]["changed_fields"] == ["colors", "logo_url", "name"]
    assert item["after_state"]["colors"] == {"configured": True}
    assert "name" not in item["after_state"]
    assert "logo_url" not in item["after_state"]

    # GET /admin/audit as manager MUST NOT contain any of the secrets
    manager_resp = await mutation_client.get("/admin/audit", headers=manager_headers)
    assert manager_resp.status_code == 200
    assert "fixture-secret-a" not in manager_resp.text
    assert "fixture-secret-b" not in manager_resp.text
    assert "fixture-secret-c" not in manager_resp.text


@pytest.mark.asyncio
async def test_real_business_updated_event_retains_useful_semantic_audit_metadata(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.semanticbiz")
    headers = await auth_headers(db_session, root)

    resp = await mutation_client.post(
        "/admin/businesses",
        headers=headers,
        json={"name": "Semantic Biz", "status": "active"},
    )
    assert resp.status_code == 201
    business_id = uuid.UUID(resp.json()["id"])

    patch_resp = await mutation_client.patch(
        f"/admin/businesses/{business_id}",
        headers=headers,
        json={"name": "Semantic Biz Renovated", "status": "inactive"},
    )
    assert patch_resp.status_code == 200

    audit_resp = await mutation_client.get("/admin/audit", headers=headers)
    assert audit_resp.status_code == 200
    items = audit_resp.json()["items"]
    event = next(ev for ev in items if ev["business_id"] == str(business_id) and ev["action"] == "business_updated")

    # Useful semantic fields retained
    assert event["actor"] == root.login
    assert event["action"] == "business_updated"
    assert event["entity"] == "business"
    assert event["business_id"] == str(business_id)
    assert event["admin_user_id"] == str(root.id)
    assert event["created_at"] is not None

    # Finite domain status and changed categories
    assert event["before_state"]["status"] == "active"
    assert event["after_state"]["status"] == "inactive"
    assert event["after_state"]["changed_fields"] == ["name", "status"]
    assert event["after_state"]["colors_changed"] is False

    # Raw user text absent
    assert "name" not in event["after_state"]
    assert "Semantic Biz Renovated" not in str(event["after_state"])


@pytest.mark.asyncio
async def test_agent_create_and_rotate_audit_contain_no_raw_key_or_hash(
    db_session: AsyncSession, mutation_client: AsyncClient
) -> None:
    root = await make_admin(db_session, "superadmin", None, "root.agentkeyaudit")
    headers = await auth_headers(db_session, root)
    business = await make_business(db_session, "Agent Key Audit Biz")

    # Create agent
    create_resp = await mutation_client.post(
        "/admin/agents",
        headers=headers,
        json={"business_id": str(business.id)},
    )
    assert create_resp.status_code == 201
    agent_id = uuid.UUID(create_resp.json()["agent"]["id"])
    initial_key = create_resp.json()["api_key"]

    # Rotate key
    rotate_resp = await mutation_client.post(
        f"/admin/agents/{agent_id}/rotate-key",
        headers=headers,
    )
    assert rotate_resp.status_code == 200
    rotated_key = rotate_resp.json()["api_key"]

    # Direct database AuditLog rows
    audits = (
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.business_id == business.id)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    ).all()

    for row in audits:
        assert initial_key not in str(row.before_state)
        assert initial_key not in str(row.after_state)
        assert rotated_key not in str(row.before_state)
        assert rotated_key not in str(row.after_state)
        assert "key_hash" not in str(row.before_state)
        assert "key_hash" not in str(row.after_state)

    # API audit listing
    audit_resp = await mutation_client.get("/admin/audit", headers=headers)
    assert audit_resp.status_code == 200
    assert initial_key not in audit_resp.text
    assert rotated_key not in audit_resp.text
    assert "key_hash" not in audit_resp.text


