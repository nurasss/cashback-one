"""PostgreSQL-specific checks for Admin uniqueness, scope invariants, and refresh races."""

import asyncio
import os
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin_deps import AdminScope
from app.core.errors import AppError
from app.core.time import utcnow
from app.db.base import Base
from app.models.admin import AdminSession, AdminUser
from app.models.entities import Agent, Business, Card, User, UserCard
from app.services.admin_auth import rotate_admin_session
from app.services.admin_queries import dashboard, list_agents, search_cards, search_users
from app.services.admin_security import (
    admin_refresh_token_hash,
    generate_admin_refresh_token,
    hash_admin_password,
    normalize_admin_login,
)


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
