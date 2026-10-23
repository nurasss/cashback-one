import uuid
from datetime import UTC, datetime
from decimal import Decimal
from http.cookies import SimpleCookie

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope
from app.core.admin_types import AdminRole
from app.core.errors import AppError
from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.admin import AdminSession, AdminUser
from app.models.entities import (
    Agent,
    AuditLog,
    AuthSession,
    Business,
    Card,
    Transaction,
    User,
    UserCard,
)
from app.schemas.admin import CardSearchRequest
from app.services.admin_queries import (
    dashboard,
    get_user_detail,
    search_cards,
    search_users,
)
from app.services.admin_security import (
    ADMIN_REFRESH_PREFIX,
    COOKIE_NAME,
    COOKIE_PATH,
    admin_refresh_token_hash,
    create_admin_access_token,
    dummy_password_hash,
    generate_admin_refresh_token,
    hash_admin_password,
    normalize_admin_login,
    sanitize_agent_error,
    verify_admin_password,
)
from app.services.rate_limiter import _test_limiter, get_rate_limiter

ORIGIN_HEADERS = {"Origin": "https://admin.test", "X-Admin-Request": "1"}
TEST_PASSWORD = "test-fixture-passphrase-123"


@pytest.fixture(autouse=True)
def reset_admin_test_limiter() -> None:
    _test_limiter.reset()


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


async def make_business(db: AsyncSession, name: str) -> Business:
    business = Business(name=name, status="active", colors={"primary_color": "#155d4a"}, barcode_prefixes=["012"])
    db.add(business)
    await db.flush()
    return business


async def make_admin(db: AsyncSession, role: AdminRole, business_id: uuid.UUID | None, login: str) -> AdminUser:
    admin = AdminUser(
        login=normalize_admin_login(login),
        password_hash=hash_admin_password(TEST_PASSWORD),
        role=role,
        business_id=business_id,
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    return admin


async def authenticated_headers(db: AsyncSession, admin: AdminUser) -> dict[str, str]:
    session = AdminSession(
        admin_user_id=admin.id,
        refresh_token_hash=admin_refresh_token_hash(generate_admin_refresh_token()),
        expires_at=datetime.now(UTC).replace(microsecond=0) + __import__("datetime").timedelta(hours=8),
    )
    db.add(session)
    await db.flush()
    return {**ORIGIN_HEADERS, "Authorization": f"Bearer {create_admin_access_token(admin.id, session.id)}"}


async def make_card(db: AsyncSession, business_id: uuid.UUID, barcode: str, phone: str | None) -> Card:
    card = Card(
        business_id=business_id,
        barcode=barcode,
        phone=phone,
        full_name="Fixture Customer",
        balance=Decimal("125.5000"),
        is_blocked=False,
        updated_at=datetime.now(UTC),
    )
    db.add(card)
    await db.flush()
    return card


def test_login_normalization_and_argon2id_password_lifecycle() -> None:
    assert normalize_admin_login("  Manager.Example@Site  ") == "manager.example@site"
    encoded = hash_admin_password(TEST_PASSWORD)
    assert encoded.startswith("$argon2id$")
    assert verify_admin_password(encoded, TEST_PASSWORD)
    assert not verify_admin_password(encoded, "some-wrong-fixture-password")
    assert verify_admin_password(dummy_password_hash(), "some-wrong-fixture-password") is False
    with pytest.raises(ValueError):
        hash_admin_password("short")


def test_card_search_is_exact_and_never_defaults_to_an_unbounded_dump() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CardSearchRequest()
    assert CardSearchRequest(barcode=" 0123456789012 ").barcode == "0123456789012"
    assert CardSearchRequest(barcode="0001").barcode == "0001"
    assert CardSearchRequest(barcode="12345678901").barcode == "12345678901"
    assert CardSearchRequest(barcode="1234567890123").barcode == "1234567890123"
    with pytest.raises(ValidationError) as exc_5:
        CardSearchRequest(barcode="123")
    assert "barcode must contain 4 to 13 digits" in str(exc_5.value)
    with pytest.raises(ValidationError) as exc_16:
        CardSearchRequest(barcode="12345678901234")
    assert "barcode must contain 4 to 13 digits" in str(exc_16.value)
    with pytest.raises(ValidationError):
        CardSearchRequest(barcode="12345a")
    with pytest.raises(ValidationError):
        CardSearchRequest(barcode="123 456")
    assert CardSearchRequest(phone="+7 (700) 123-45-67").phone == "+77001234567"


def test_agent_error_read_view_redacts_auth_secrets_and_long_customer_numbers() -> None:
    raw = "Bearer fixture.jwt.private; api_key=agk_fixture-agent-secret; phone=+77001234567; barcode=0123456789012"
    safe = sanitize_agent_error(raw)
    assert safe is not None
    for secret in ("fixture.jwt.private", "agk_fixture-agent-secret", "+77001234567", "0123456789012"):
        assert secret not in safe


@pytest.mark.asyncio
async def test_role_business_invariant_is_enforced_by_sqlite_database(db_session: AsyncSession) -> None:
    superadmin = AdminUser(login="invalid.super", password_hash="not-used", role="superadmin", business_id=uuid.uuid4())
    db_session.add(superadmin)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_admin_login_is_independent_uses_cookie_and_returns_only_access_token(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    await make_admin(db_session, "superadmin", None, "Root.Owner")
    response = await admin_client.post(
        "/admin/auth/login", json={"login": " ROOT.OWNER ", "password": TEST_PASSWORD}, headers=ORIGIN_HEADERS
    )
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type", "expires_in"}
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 900
    cookie = SimpleCookie(response.headers["set-cookie"])[COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == COOKIE_PATH
    assert cookie["max-age"] == "28800"
    assert cookie.value.startswith(ADMIN_REFRESH_PREFIX)
    assert cookie.value not in str(response.json())
    assert await db_session.scalar(__import__("sqlalchemy").select(AdminSession)) is not None


@pytest.mark.asyncio
async def test_invalid_username_and_password_share_same_auth_response(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    await make_admin(db_session, "superadmin", None, "root.operator")
    wrong_password = await admin_client.post(
        "/admin/auth/login", json={"login": "root.operator", "password": "wrong-fixture-password"}, headers=ORIGIN_HEADERS
    )
    unknown_login = await admin_client.post(
        "/admin/auth/login", json={"login": "nobody.operator", "password": "wrong-fixture-password"}, headers=ORIGIN_HEADERS
    )
    assert wrong_password.status_code == unknown_login.status_code == 401
    assert wrong_password.json() == unknown_login.json() == {
        "error": {"code": "INVALID_CREDENTIALS", "message": "Неверный логин или пароль"}
    }


@pytest.mark.asyncio
async def test_admin_refresh_rotates_cookie_and_rejects_old_refresh_token(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    await make_admin(db_session, "superadmin", None, "root.rotate")
    login = await admin_client.post("/admin/auth/login", json={"login": "root.rotate", "password": TEST_PASSWORD}, headers=ORIGIN_HEADERS)
    old = SimpleCookie(login.headers["set-cookie"])[COOKIE_NAME].value
    rotated = await admin_client.post("/admin/auth/refresh", json={}, headers=ORIGIN_HEADERS)
    assert rotated.status_code == 200
    new = SimpleCookie(rotated.headers["set-cookie"])[COOKIE_NAME].value
    assert new != old
    assert await db_session.scalar(
        __import__("sqlalchemy").select(AdminSession.id).where(AdminSession.refresh_token_hash == admin_refresh_token_hash(old))
    ) is None
    replay = await admin_client.post("/admin/auth/refresh", json={}, headers={**ORIGIN_HEADERS, "Cookie": f"{COOKIE_NAME}={old}"})
    assert replay.status_code == 401


@pytest.mark.asyncio
async def test_customer_jwt_is_rejected_from_admin_and_admin_jwt_from_customer(
    db_session: AsyncSession, admin_client: AsyncClient, client: AsyncClient
) -> None:
    await make_business(db_session, "Fixture Store")
    admin = await make_admin(db_session, "superadmin", None, "root.token-boundary")
    admin_headers = await authenticated_headers(db_session, admin)
    foreign_admin_response = await client.get("/me/cards", headers={"Authorization": admin_headers["Authorization"]})
    assert foreign_admin_response.status_code == 401
    assert foreign_admin_response.json()["error"]["code"] in {"INVALID_TOKEN", "TOKEN_EXPIRED"}

    user = User(phone="+77001112233", language="ru", created_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.flush()
    customer_session = AuthSession(
        user_id=user.id,
        device_id="fixture-device",
        refresh_token_hash="a" * 64,
        expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=8),
    )
    db_session.add(customer_session)
    await db_session.flush()
    customer_jwt = create_access_token(user.id, customer_session.id)
    admin_response = await admin_client.get("/admin/me", headers={**ORIGIN_HEADERS, "Authorization": f"Bearer {customer_jwt}"})
    assert admin_response.status_code == 401


@pytest.mark.asyncio
async def test_manager_tenant_filters_are_in_queries_and_foreign_ids_are_hidden(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    business_a = await make_business(db_session, "Business A")
    business_b = await make_business(db_session, "Business B")
    manager = await make_admin(db_session, "business_manager", business_a.id, "manager.a")
    scoped = AdminScope(manager.id, manager.role, manager.business_id)
    card_a = await make_card(db_session, business_a.id, "0123456789012", "+77001112222")
    card_b = await make_card(db_session, business_b.id, "0123456789013", "+77004445555")
    user_a = User(phone="+77001112222", language="ru", created_at=datetime.now(UTC))
    user_b = User(phone="+77004445555", language="ru", created_at=datetime.now(UTC))
    db_session.add_all([user_a, user_b])
    await db_session.flush()
    db_session.add_all([
        UserCard(user_id=user_a.id, card_id=card_a.id, bound_at=datetime.now(UTC), bind_method="manual_barcode"),
        UserCard(user_id=user_b.id, card_id=card_b.id, bound_at=datetime.now(UTC), bind_method="manual_barcode"),
        Agent(business_id=business_a.id, key_hash="hash-a", status="active"),
        Agent(business_id=business_b.id, key_hash="Agent raw secret sentinel", status="active"),
    ])
    await db_session.flush()
    headers = await authenticated_headers(db_session, manager)

    visible = await search_cards(db_session, scoped, "0123456789012", None, None, 25, 0)
    assert [item.barcode for item in visible.items] == [card_a.barcode]
    hidden = await search_cards(db_session, scoped, card_b.barcode, None, None, 25, 0)
    assert hidden.items == []
    phone_results = await search_users(db_session, scoped, "+7 (700) 444-55-55", None, 25, 0)
    assert phone_results.items == []
    user_details = await get_user_detail(db_session, scoped, user_a.id, None, 25, 0)
    assert [item.business_id for item in user_details.cards.items] == [business_a.id]

    agents = await admin_client.get("/admin/agents", headers=headers)
    assert agents.status_code == 200
    assert {item["business_id"] for item in agents.json()["items"]} == {str(business_a.id)}
    assert "Agent raw secret sentinel" not in agents.text
    foreign_agent = await admin_client.get(f"/admin/agents/{uuid.uuid4()}", headers=headers)
    assert foreign_agent.status_code == 404
    foreign_business_filter = await admin_client.get(f"/admin/agents?business_id={business_b.id}", headers=headers)
    assert foreign_business_filter.status_code == 404
    foreign_card = await admin_client.post(
        "/admin/cards/search", json={"barcode": card_b.barcode, "business_id": str(business_b.id)}, headers=headers
    )
    assert foreign_card.status_code == 404
    foreign_user_search = await admin_client.post(
        "/admin/users/search", json={"phone": user_b.phone, "business_id": str(business_b.id)}, headers=headers
    )
    assert foreign_user_search.status_code == 404
    assert "Business B" not in foreign_card.text


@pytest.mark.asyncio
async def test_superadmin_scope_and_audit_view_is_superadmin_only(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    first = await make_business(db_session, "First")
    await make_business(db_session, "Second")
    root = await make_admin(db_session, "superadmin", None, "root.scope")
    manager = await make_admin(db_session, "business_manager", first.id, "manager.scope")
    await db_session.flush()
    db_session.add(AuditLog(actor="fixture-actor", action="fixture_event", entity="cards"))
    await db_session.commit()
    root_headers = await authenticated_headers(db_session, root)
    manager_headers = await authenticated_headers(db_session, manager)

    business_page = await admin_client.get("/admin/businesses?limit=10", headers=root_headers)
    assert {item["name"] for item in business_page.json()["items"]} == {"First", "Second"}
    manager_businesses = await admin_client.get("/admin/businesses", headers=manager_headers)
    assert manager_businesses.status_code == 403
    manager_audit = await admin_client.get("/admin/audit", headers=manager_headers)
    assert manager_audit.status_code == 200
    assert manager_audit.json()["items"] == []
    root_audit = await admin_client.get("/admin/audit", headers=root_headers)
    assert root_audit.status_code == 200
    assert root_audit.json()["items"][0]["before_state"] is None


@pytest.mark.asyncio
async def test_bearer_admin_access_authenticates_current_database_role(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    business = await make_business(db_session, "Managed Store")
    manager = await make_admin(db_session, "business_manager", business.id, "manager.identity")
    headers = await authenticated_headers(db_session, manager)
    response = await admin_client.get("/admin/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["admin"]["role"] == "business_manager"
    assert response.json()["admin"]["business"]["name"] == "Managed Store"
    assert "password_hash" not in response.text
    assert "refresh_token" not in response.text


@pytest.mark.asyncio
async def test_admin_origin_csrf_and_tls_are_required(admin_client: AsyncClient) -> None:
    no_origin = await admin_client.get("/admin/me", headers={"Authorization": "Bearer invalid"})
    assert no_origin.status_code == 403
    no_csrf = await admin_client.get("/admin/me", headers={"Origin": "https://admin.test"})
    assert no_csrf.status_code == 403
    evil_origin = await admin_client.post(
        "/admin/auth/refresh", headers={"Origin": "https://evil.example", "X-Admin-Request": "1"}
    )
    assert evil_origin.status_code == 403


@pytest.mark.asyncio
async def test_user_detail_only_returns_cards_scoped_to_manager_business(
    db_session: AsyncSession,
) -> None:
    a = await make_business(db_session, "A")
    b = await make_business(db_session, "B")
    user = User(phone="+77005556677", language="ru", created_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.flush()
    card_a = await make_card(db_session, a.id, "0000000000001", user.phone)
    card_b = await make_card(db_session, b.id, "0000000000002", user.phone)
    db_session.add_all([
        UserCard(user_id=user.id, card_id=card_a.id, bound_at=datetime.now(UTC), bind_method="phone_auto"),
        UserCard(user_id=user.id, card_id=card_b.id, bound_at=datetime.now(UTC), bind_method="phone_auto"),
    ])
    manager = await make_admin(db_session, "business_manager", a.id, "manager.shared-user")
    await db_session.flush()
    result = await get_user_detail(db_session, AdminScope(manager.id, manager.role, manager.business_id), user.id, None, 25, 0)
    assert len(result.cards.items) == 1
    assert result.cards.items[0].id == card_a.id
    with pytest.raises(AppError) as err:
        await get_user_detail(db_session, AdminScope(manager.id, manager.role, manager.business_id), user.id, b.id, 25, 0)
    assert err.value.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_aggregates_and_periods_are_tenant_scoped(db_session: AsyncSession) -> None:
    from datetime import timedelta

    a = await make_business(db_session, "Dashboard A")
    b = await make_business(db_session, "Dashboard B")
    now = datetime.now(UTC).replace(microsecond=0)
    user_a = User(phone="+77001234001", language="ru", created_at=now)
    user_b = User(phone="+77001234002", language="ru", created_at=now)
    db_session.add_all([user_a, user_b])
    await db_session.flush()
    card_a = await make_card(db_session, a.id, "0000000000001", user_a.phone)
    card_b = await make_card(db_session, b.id, "0000000000002", user_b.phone)
    card_b.is_blocked = True
    db_session.add_all([
        UserCard(user_id=user_a.id, card_id=card_a.id, bound_at=now, bind_method="manual_barcode"),
        UserCard(user_id=user_b.id, card_id=card_b.id, bound_at=now, bind_method="manual_barcode"),
        Transaction(
            card_id=card_a.id,
            external_id="admin-a-in-period",
            type="accrual",
            amount=Decimal("10.0000"),
            balance_after=Decimal("125.5000"),
            occurred_at=now,
        ),
        Transaction(
            card_id=card_b.id,
            external_id="admin-b-in-period",
            type="redemption",
            amount=Decimal("5.0000"),
            balance_after=Decimal("0.0000"),
            occurred_at=now,
        ),
        Agent(business_id=a.id, key_hash="fixture-hash-a", status="active", last_seen_at=now),
        Agent(business_id=b.id, key_hash="fixture-hash-b", status="active", last_seen_at=now - timedelta(days=2)),
    ])
    manager = await make_admin(db_session, "business_manager", a.id, "manager.dashboard")
    root = await make_admin(db_session, "superadmin", None, "root.dashboard")
    await db_session.flush()

    manager_result = await dashboard(
        db_session,
        AdminScope(manager.id, manager.role, manager.business_id),
        None,
        now,
        now,
    )
    assert manager_result.business_id == a.id
    assert manager_result.customers_with_business_cards == 1
    assert manager_result.cards == manager_result.unblocked_cards == 1
    assert manager_result.transactions == 1
    assert manager_result.agents.online == 1
    assert manager_result.agents.stale == 0
    with pytest.raises(AppError) as foreign_scope:
        await dashboard(
            db_session,
            AdminScope(manager.id, manager.role, manager.business_id),
            b.id,
            now,
            now,
        )
    assert foreign_scope.value.status_code == 404

    aggregate = await dashboard(
        db_session, AdminScope(root.id, root.role, root.business_id), None, now, now
    )
    assert aggregate.business_id is None
    assert aggregate.customers_with_business_cards == 2
    assert aggregate.cards == 2
    assert aggregate.unblocked_cards == 1
    assert aggregate.transactions == 2
    assert aggregate.agents.online == aggregate.agents.stale == 1


@pytest.mark.asyncio
async def test_admin_login_rate_limits_normalized_login_without_disclosing_account(
    db_session: AsyncSession, admin_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "admin_login_limit", 1)
    monkeypatch.setattr(settings, "admin_login_ip_limit", 50)
    first = await admin_client.post(
        "/admin/auth/login",
        json={"login": "Rate.Limited", "password": "wrong-fixture-password"},
        headers=ORIGIN_HEADERS,
    )
    repeated = await admin_client.post(
        "/admin/auth/login",
        json={"login": " rate.limited ", "password": "wrong-fixture-password"},
        headers=ORIGIN_HEADERS,
    )
    assert first.status_code == 401
    assert first.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert repeated.status_code == 429
    assert repeated.json()["error"]["code"] == "ADMIN_RATE_LIMITED"


@pytest.mark.asyncio
async def test_inactive_admin_and_expired_refresh_session_are_rejected_safely(
    db_session: AsyncSession, admin_client: AsyncClient
) -> None:
    from datetime import timedelta

    admin = await make_admin(db_session, "superadmin", None, "inactive.account")
    admin.is_active = False
    response = await admin_client.post(
        "/admin/auth/login", json={"login": admin.login, "password": TEST_PASSWORD}, headers=ORIGIN_HEADERS
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    token = generate_admin_refresh_token()
    expired = AdminSession(
        admin_user_id=admin.id,
        refresh_token_hash=admin_refresh_token_hash(token),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.add(expired)
    await db_session.commit()
    refresh = await admin_client.post(
        "/admin/auth/refresh", headers={**ORIGIN_HEADERS, "Cookie": f"{COOKIE_NAME}={token}"}
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_admin_refresh_cookie(db_session: AsyncSession, admin_client: AsyncClient) -> None:
    await make_admin(db_session, "superadmin", None, "root.logout")
    login = await admin_client.post(
        "/admin/auth/login", json={"login": "root.logout", "password": TEST_PASSWORD}, headers=ORIGIN_HEADERS
    )
    refresh_token = SimpleCookie(login.headers["set-cookie"])[COOKIE_NAME].value
    logout = await admin_client.post(
        "/admin/auth/logout", headers={**ORIGIN_HEADERS, "Cookie": f"{COOKIE_NAME}={refresh_token}"}
    )
    assert logout.status_code == 200
    refresh = await admin_client.post(
        "/admin/auth/refresh", headers={**ORIGIN_HEADERS, "Cookie": f"{COOKIE_NAME}={refresh_token}"}
    )
    assert refresh.status_code == 401
