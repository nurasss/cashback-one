"""PostgreSQL-specific checks for Admin uniqueness, scope invariants, and refresh races."""

import asyncio
import os
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin_deps import AdminScope
from app.core.errors import AppError
from app.core.time import utcnow
from app.db.base import Base
from app.models.admin import AdminSession, AdminUser, AgentCommand
from app.models.entities import Agent, AuditLog, Business, Card, User, UserCard
from app.schemas.admin import BusinessCreateRequest
from app.services.admin_auth import rotate_admin_session
from app.services.admin_mutations import (
    create_business,
    request_full_resync,
    rotate_agent_api_key,
    unbind_card,
)
from app.services.admin_queries import dashboard, list_agents, search_cards, search_users
from app.services.admin_security import (
    admin_refresh_token_hash,
    generate_admin_refresh_token,
    hash_admin_password,
    normalize_admin_login,
)
from app.services.agent_auth import hash_agent_key, issue_agent_key


@pytest.fixture
async def pg_admin_sessions():  # type: ignore[no-untyped-def]
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")
    engine = create_async_engine(pg_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL Admin regression skipped: {type(exc).__name__}")
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_admin_normalized_login_and_role_business_constraints(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    from app.cli.create_admin import provision_admin

    async with pg_admin_sessions() as session:
        await provision_admin(session, "Root.Operator", "fixture-superadmin-password", "superadmin", None)
        with pytest.raises(ValueError, match="already provisioned"):
            await provision_admin(session, " ROOT.OPERATOR ", "fixture-superadmin-password", "superadmin", None)

        business = Business(name="Fixture tenant", status="active")
        session.add(business)
        await session.flush()
        session.add(
            AdminUser(
                login=normalize_admin_login("tenant.manager"),
                password_hash=hash_admin_password("fixture-manager-password"),
                role="business_manager",
                business_id=business.id,
            )
        )
        await session.commit()

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    AdminUser(
                        login="invalid.manager",
                        password_hash="unused",
                        role="business_manager",
                        business_id=None,
                    )
                )
                await session.flush()
        await session.rollback()


@pytest.mark.asyncio
async def test_postgres_admin_refresh_rotation_has_one_concurrent_winner(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    raw_refresh = generate_admin_refresh_token()
    async with pg_admin_sessions() as session:
        admin = AdminUser(
            login="root.concurrent",
            password_hash=hash_admin_password("fixture-concurrent-password"),
            role="superadmin",
            business_id=None,
        )
        session.add(admin)
        await session.flush()
        session.add(
            AdminSession(
                admin_user_id=admin.id,
                refresh_token_hash=admin_refresh_token_hash(raw_refresh),
                expires_at=utcnow() + timedelta(hours=8),
            )
        )
        await session.commit()

    async def rotate() -> bool:
        async with pg_admin_sessions() as session:
            try:
                await rotate_admin_session(session, raw_refresh)
                return True
            except AppError:
                await session.rollback()
                return False

    results = await asyncio.gather(rotate(), rotate())
    assert sorted(results) == [False, True]
    async with pg_admin_sessions() as session:
        sessions = (await session.scalars(select(AdminSession))).all()
        assert len(sessions) == 1
        assert sessions[0].refresh_token_hash != admin_refresh_token_hash(raw_refresh)


@pytest.mark.asyncio
async def test_postgres_admin_tenant_queries_never_return_foreign_rows(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    async with pg_admin_sessions() as session:
        tenant_a = Business(name="Admin PG tenant A", status="active")
        tenant_b = Business(name="Admin PG tenant B", status="active")
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        user_a = User(phone="+77001000101", language="ru")
        user_b = User(phone="+77001000102", language="ru")
        session.add_all([user_a, user_b])
        await session.flush()
        card_a = Card(
            business_id=tenant_a.id,
            barcode="0000000000123",
            phone=user_a.phone,
            full_name="Fixture A",
            balance=Decimal("10.0000"),
        )
        card_b = Card(
            business_id=tenant_b.id,
            barcode="0000000000456",
            phone=user_b.phone,
            full_name="Fixture B",
            balance=Decimal("20.0000"),
        )
        session.add_all([card_a, card_b])
        await session.flush()
        session.add_all([
            UserCard(user_id=user_a.id, card_id=card_a.id),
            UserCard(user_id=user_b.id, card_id=card_b.id),
            Agent(business_id=tenant_a.id, key_hash="fixture-agent-hash-a", status="active"),
            Agent(business_id=tenant_b.id, key_hash="fixture-agent-hash-b", status="active"),
        ])
        manager = AdminUser(
            login="manager.pgscope",
            password_hash=hash_admin_password("fixture-pg-scope-password"),
            role="business_manager",
            business_id=tenant_a.id,
        )
        session.add(manager)
        await session.commit()
        scope = AdminScope(manager.id, "business_manager", tenant_a.id)

        cards = await search_cards(session, scope, card_b.barcode, None, None, 25, 0)
        users = await search_users(session, scope, user_b.phone or "", None, 25, 0)
        agents = await list_agents(session, scope, None, 25, 0)
        now = datetime.now(UTC)
        stats = await dashboard(session, scope, None, now - timedelta(days=1), now + timedelta(days=1))

        assert cards.items == []
        assert users.items == []
        assert len(agents.items) == 1
        assert agents.items[0].business_id == tenant_a.id
        assert stats.business_id == tenant_a.id
        assert stats.cards == stats.customers_with_business_cards == 1


@pytest.mark.asyncio
async def test_postgres_concurrent_admin_agent_rotations_leave_one_key_and_audit_each(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    async with pg_admin_sessions() as session:
        business = Business(name="Concurrent rotation tenant", status="active")
        admin = AdminUser(
            login="root.pgrotate",
            password_hash=hash_admin_password("fixture-pg-rotate-password"),
            role="superadmin",
        )
        session.add_all([business, admin])
        await session.flush()
        agent, old_key = await issue_agent_key(session, business.id)
        await session.commit()
        admin_id = admin.id
        agent_id = agent.id

    async def rotate() -> str:
        async with pg_admin_sessions() as session:
            actor = await session.get(AdminUser, admin_id)
            assert actor is not None
            _agent, new_key = await rotate_agent_api_key(session, actor, agent_id)
            return new_key

    keys = await asyncio.gather(rotate(), rotate())
    assert keys[0] != keys[1]
    async with pg_admin_sessions() as session:
        current = await session.get(Agent, agent_id)
        assert current is not None
        assert current.key_hash in {hash_agent_key(keys[0]), hash_agent_key(keys[1])}
        assert current.key_hash != hash_agent_key(old_key)
        events = (
            await session.scalars(
                select(AuditLog).where(AuditLog.action == "agent_key_rotated")
            )
        ).all()
        assert len(events) == 2
        assert all(key not in str(events) for key in [*keys, old_key])


@pytest.mark.asyncio
async def test_postgres_concurrent_resync_requests_return_one_durable_command(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    async with pg_admin_sessions() as session:
        business = Business(name="Concurrent resync tenant", status="active")
        admin = AdminUser(
            login="root.pgresync",
            password_hash=hash_admin_password("fixture-pg-resync-password"),
            role="superadmin",
        )
        session.add_all([business, admin])
        await session.flush()
        agent, _raw_key = await issue_agent_key(session, business.id)
        await session.commit()
        admin_id = admin.id
        agent_id = agent.id

    async def request() -> tuple[uuid.UUID, bool]:
        async with pg_admin_sessions() as session:
            actor = await session.get(AdminUser, admin_id)
            assert actor is not None
            command, created = await request_full_resync(session, actor, agent_id)
            return command.id, created

    results = await asyncio.gather(request(), request())
    assert len({command_id for command_id, _ in results}) == 1
    assert sorted(created for _, created in results) == [False, True]
    async with pg_admin_sessions() as session:
        assert await session.scalar(
            select(func.count(AgentCommand.id)).where(
                AgentCommand.agent_id == agent_id,
                AgentCommand.status.in_(("pending", "running")),
            )
        ) == 1
        assert await session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "agent_full_resync_requested"
            )
        ) == 1


@pytest.mark.asyncio
async def test_postgres_concurrent_card_unbind_is_idempotent_and_audited_once(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    from app.api.admin_deps import AdminScope

    async with pg_admin_sessions() as session:
        business = Business(name="Concurrent unbind tenant", status="active")
        session.add(business)
        await session.flush()
        admin = AdminUser(
            login="manager.pgunbind",
            password_hash=hash_admin_password("fixture-pg-unbind-password"),
            role="business_manager",
            business_id=business.id,
        )
        session.add(admin)
        user = User(phone="+77009990011", language="ru")
        card = Card(
            business_id=business.id,
            barcode="0000000000789",
            phone=user.phone,
            balance=Decimal("88.2500"),
        )
        session.add_all([user, card])
        await session.flush()
        session.add(UserCard(user_id=user.id, card_id=card.id))
        await session.commit()
        admin_id = admin.id
        business_id = business.id
        card_id = card.id
        user_id = user.id

    async def remove_binding() -> str:
        async with pg_admin_sessions() as session:
            actor = await session.get(AdminUser, admin_id)
            assert actor is not None
            return await unbind_card(
                session,
                actor,
                AdminScope(admin_id, "business_manager", business_id),
                card_id,
            )

    results = await asyncio.gather(remove_binding(), remove_binding())
    assert sorted(results) == ["already_unbound", "unbound"]
    async with pg_admin_sessions() as session:
        assert await session.scalar(select(UserCard.id).where(UserCard.card_id == card_id)) is None
        assert await session.get(User, user_id) is not None
        card = await session.get(Card, card_id)
        assert card is not None and card.balance == Decimal("88.2500")
        events = (
            await session.scalars(select(AuditLog).where(AuditLog.action == "card_unbound"))
        ).all()
        assert len(events) == 1
        assert events[0].admin_user_id == admin_id
        assert events[0].business_id == business_id
        assert events[0].before_state == {
            "card_id": str(card_id),
            "business_id": str(business_id),
            "user_id": str(user_id),
        }


@pytest.mark.asyncio
async def test_postgres_business_mutation_and_audit_roll_back_together(pg_admin_sessions) -> None:  # type: ignore[no-untyped-def]
    async with pg_admin_sessions() as session:
        admin = AdminUser(
            login="root.pgauditatomic",
            password_hash=hash_admin_password("fixture-pg-audit-password"),
            role="superadmin",
        )
        session.add(admin)
        await session.commit()
        admin_id = admin.id
        await session.execute(
            text(
                "ALTER TABLE audit_log ADD CONSTRAINT ck_test_reject_business_created "
                "CHECK (action <> 'business_created')"
            )
        )
        await session.commit()

    async with pg_admin_sessions() as session:
        actor = await session.get(AdminUser, admin_id)
        assert actor is not None
        with pytest.raises(IntegrityError):
            await create_business(session, actor, BusinessCreateRequest(name="Must roll back"))
        await session.rollback()
        assert await session.scalar(
            select(func.count(Business.id)).where(Business.name == "Must roll back")
        ) == 0
        assert await session.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.action == "business_created")
        ) == 0
