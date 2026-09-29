import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.entities import AuthSession, Business, Card, Transaction, User, UserCard
from app.services.wallet_service import auto_bind_cards_by_phone


@pytest.fixture
async def pg_engine():  # type: ignore[no-untyped-def]
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL 16 connection skipped: {exc}")

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def pg_session_maker(pg_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_pg_wallet_01_concurrent_auto_bind_same_user(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-01: Concurrent GET /me/cards requests for the same user.

    ON CONFLICT DO NOTHING guarantees:
    - Zero IntegrityError / 500 exceptions under concurrent auto-bind calls.
    - Exactly 1 binding per card created in user_cards.
    - All concurrent responses return 200 with the exact same cards including updated_at.
    """
    phone = "+77018880011"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz 1")
        s.add(biz)
        await s.flush()

        cards = [
            Card(
                business_id=biz.id,
                barcode=f"012345678901{i}",
                phone=phone,
                balance=Decimal(f"{100 + i}.0000"),
            )
            for i in range(3)
        ]
        s.add_all(cards)

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.flush()

        auth_session = AuthSession(
            user_id=user.id,
            device_id="pg-device-1",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(auth_session)
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=auth_session.id)
        user_id = user.id

    async def fetch_cards() -> tuple[int, list[dict]]:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get(
                "/me/cards",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code, resp.json()

    # Launch 5 concurrent GET /me/cards requests
    results = await asyncio.gather(*(fetch_cards() for _ in range(5)))

    for status_code, card_list in results:
        assert status_code == 200
        assert len(card_list) == 3
        for card_item in card_list:
            assert "updated_at" in card_item
            assert card_item["updated_at"] is not None

    # Check database rows in user_cards
    async with pg_session_maker() as s:
        bindings = (
            await s.scalars(
                select(UserCard).where(UserCard.user_id == user_id)
            )
        ).all()
        assert len(bindings) == 3


@pytest.mark.asyncio
async def test_pg_wallet_02_foreign_existing_owner_cannot_be_stolen(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-02: Card belongs to User A; Card.phone matches User B; User B concurrently runs auto-bind.

    Guarantees:
    - UserCard remains User A (no ownership theft).
    - User B receives no ownership (empty card list).
    - 0 IntegrityError / 0 HTTP 500 exceptions.
    - Exactly 1 binding exists in user_cards for the card.
    """
    shared_phone = "+77018880022"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz Foreign Owner")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="0123456789022",
            phone=shared_phone,
            balance=Decimal("500.0000"),
        )
        s.add(card)

        user_a = User(phone="+77011110022", language="ru")
        user_b = User(phone=shared_phone, language="en")
        s.add_all([user_a, user_b])
        await s.flush()

        # Card is bound to User A
        uc_a = UserCard(
            user_id=user_a.id,
            card_id=card.id,
            bind_method="phone_auto",
        )
        s.add(uc_a)

        # Auth session for User B
        auth_b = AuthSession(
            user_id=user_b.id,
            device_id="pg-device-b",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(auth_b)
        await s.commit()

        token_b = create_access_token(user_id=user_b.id, session_id=auth_b.id)
        card_id = card.id
        user_a_id = user_a.id
        user_b_id = user_b.id

    # 1. Concurrently run 5 GET /me/cards requests for User B
    async def call_user_b_cards() -> tuple[int, list[dict]]:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get(
                "/me/cards",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            return resp.status_code, resp.json()

    # 2. Concurrently run direct auto_bind_cards_by_phone for User B in isolated DB sessions
    async def direct_bind_worker() -> list[uuid.UUID]:
        async with pg_session_maker() as s:
            u_b = await s.get(User, user_b_id)
            assert u_b is not None
            res = await auto_bind_cards_by_phone(s, u_b)
            await s.commit()
            return res

    http_results = await asyncio.gather(*(call_user_b_cards() for _ in range(3)))
    direct_results = await asyncio.gather(*(direct_bind_worker() for _ in range(3)))

    # All HTTP responses for User B must be 200 OK with empty list (no card stolen)
    for code, cards in http_results:
        assert code == 200
        assert cards == []

    # Direct auto-bind calls must return empty list (skipped)
    for bound_list in direct_results:
        assert bound_list == []

    # Verify database state: exactly 1 binding, belonging to User A
    async with pg_session_maker() as s:
        bindings = (
            await s.scalars(
                select(UserCard).where(UserCard.card_id == card_id)
            )
        ).all()
        assert len(bindings) == 1
        assert bindings[0].user_id == user_a_id


@pytest.mark.asyncio
async def test_pg_wallet_02_concurrent_auto_bind_competing_sessions(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """Same-user competing sessions: concurrent auto_bind across isolated database sessions."""
    phone = "+77018880025"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz Competing")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="0123456789025",
            phone=phone,
            balance=Decimal("250.0000"),
        )
        s.add(card)

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.commit()

        card_id = card.id
        u_id = user.id

    async def bind_worker() -> list[uuid.UUID]:
        async with pg_session_maker() as s:
            u = await s.get(User, u_id)
            assert u is not None
            res = await auto_bind_cards_by_phone(s, u)
            await s.commit()
            return res

    results = await asyncio.gather(*(bind_worker() for _ in range(5)))
    bound_items = [r for r in results if r]
    assert len(bound_items) >= 1
    assert bound_items[0] == [card_id]

    async with pg_session_maker() as s:
        bindings = (
            await s.scalars(
                select(UserCard).where(UserCard.card_id == card_id)
            )
        ).all()
        assert len(bindings) == 1


@pytest.mark.asyncio
async def test_pg_wallet_03_concurrent_card_soft_hide(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-03: Concurrent DELETE /me/cards/{id} calls with atomic RETURNING.

    Verifies across multiple iterations with synchronization barrier:
    - Strictly 1 x 204 No Content.
    - Strictly 4 x 404 Not Found.
    - Zero 500 or IntegrityError exceptions.
    - Underlying card in cards table remains unmodified.
    - user_cards.hidden_at is NOT NULL.
    """
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        # Run 10 iterations to eliminate flakiness and guarantee concurrency safety
        for iteration in range(10):
            phone = f"+770188800{30 + iteration}"
            async with pg_session_maker() as s:
                biz = Business(name=f"PG Biz 3-{iteration}")
                s.add(biz)
                await s.flush()

                card = Card(
                    business_id=biz.id,
                    barcode=f"012345678{300 + iteration:04d}",
                    phone=phone,
                    balance=Decimal("500.0000"),
                )
                s.add(card)

                user = User(phone=phone, language="ru")
                s.add(user)
                await s.flush()

                user_card = UserCard(
                    user_id=user.id,
                    card_id=card.id,
                    bind_method="phone_auto",
                )
                s.add(user_card)

                auth_session = AuthSession(
                    user_id=user.id,
                    device_id=f"pg-device-3-{iteration}",
                    refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
                    expires_at=utcnow() + timedelta(days=30),
                )
                s.add(auth_session)
                await s.commit()

                token = create_access_token(user_id=user.id, session_id=auth_session.id)
                card_id = card.id
                initial_updated_at = card.updated_at

            barrier = asyncio.Barrier(5)

            async def call_delete(c_id: uuid.UUID, tok: str, b: asyncio.Barrier) -> int:
                await b.wait()
                resp = await ac.delete(
                    f"/me/cards/{c_id}",
                    headers={"Authorization": f"Bearer {tok}"},
                )
                return resp.status_code

            delete_results = await asyncio.gather(*(call_delete(card_id, token, barrier) for _ in range(5)))
            assert delete_results.count(204) == 1, f"Iteration {iteration}: expected 1 x 204, got {delete_results}"
            assert delete_results.count(404) == 4, f"Iteration {iteration}: expected 4 x 404, got {delete_results}"
            assert 500 not in delete_results

            # Card entity in cards table remains untouched
            async with pg_session_maker() as s:
                c = await s.get(Card, card_id)
                assert c is not None
                assert c.balance == Decimal("500.0000")
                assert c.updated_at == initial_updated_at

                uc = (
                    await s.scalars(
                        select(UserCard).where(UserCard.card_id == card_id)
                    )
                ).one()
                assert uc.hidden_at is not None


@pytest.mark.asyncio
async def test_pg_wallet_04_hidden_card_not_resurrected_by_auto_bind(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-04: User owns a soft-hidden card; concurrent auto-bind calls must NOT unhide it.

    Guarantees:
    - user_cards.hidden_at remains NOT NULL.
    - Exactly 1 UserCard record exists (no duplicate insert).
    - Subsequent GET /me/cards does not contain the hidden card.
    - 0 IntegrityError / 0 HTTP 500.
    """
    phone = "+77018880040"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz Hidden Preservation")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="0123456789040",
            phone=phone,
            balance=Decimal("750.0000"),
        )
        s.add(card)

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.flush()

        hidden_time = utcnow()
        user_card = UserCard(
            user_id=user.id,
            card_id=card.id,
            bind_method="phone_auto",
            hidden_at=hidden_time,
        )
        s.add(user_card)

        auth_session = AuthSession(
            user_id=user.id,
            device_id="pg-device-hidden",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(auth_session)
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=auth_session.id)
        card_id = card.id
        u_id = user.id

    barrier = asyncio.Barrier(6)

    # 3 concurrent HTTP GET /me/cards requests
    async def call_get_cards() -> tuple[int, list[dict]]:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            await barrier.wait()
            resp = await ac.get(
                "/me/cards",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code, resp.json()

    # 3 concurrent direct auto_bind_cards_by_phone calls
    async def call_direct_auto_bind() -> list[uuid.UUID]:
        async with pg_session_maker() as s:
            u = await s.get(User, u_id)
            assert u is not None
            await barrier.wait()
            res = await auto_bind_cards_by_phone(s, u)
            await s.commit()
            return res

    http_results, direct_results = await asyncio.gather(
        asyncio.gather(*(call_get_cards() for _ in range(3))),
        asyncio.gather(*(call_direct_auto_bind() for _ in range(3))),
    )

    # None of the HTTP responses should return the hidden card
    for code, card_list in http_results:
        assert code == 200
        assert card_list == []

    # None of direct calls should rebind the hidden card
    for bound_list in direct_results:
        assert bound_list == []

    # Verify DB: exactly 1 binding, hidden_at still NOT NULL
    async with pg_session_maker() as s:
        bindings = (
            await s.scalars(
                select(UserCard).where(UserCard.card_id == card_id)
            )
        ).all()
        assert len(bindings) == 1
        assert bindings[0].hidden_at is not None
        assert bindings[0].user_id == u_id


@pytest.mark.asyncio
async def test_pg_wallet_05_transaction_pagination_consistency(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-05: Keyset cursor pagination over PostgreSQL with composite index."""
    phone = "+77018880055"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz 5")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="0123456789055",
            phone=phone,
            balance=Decimal("1000.0000"),
        )
        s.add(card)

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.flush()

        user_card = UserCard(user_id=user.id, card_id=card.id)
        s.add(user_card)

        auth_session = AuthSession(
            user_id=user.id,
            device_id="pg-device-5",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(auth_session)

        # Seed 15 transactions
        base_time = utcnow()
        for i in range(15):
            s.add(
                Transaction(
                    card_id=card.id,
                    external_id=f"pg-tx-{i}",
                    type="accrual" if i % 2 == 0 else "redemption",
                    amount=Decimal(f"{10 + i}.0000"),
                    balance_after=Decimal(f"{500 + i * 10}.0000"),
                    occurred_at=base_time + timedelta(seconds=i * 10),
                )
            )
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=auth_session.id)
        card_id = card.id

    async def get_page(cursor: str | None = None) -> dict:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        url = f"/me/cards/{card_id}/transactions?limit=6"
        if cursor:
            url += f"&cursor={cursor}"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get(url, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
            return resp.json()

    # Page 1 (6 items)
    p1 = await get_page()
    assert len(p1["items"]) == 6
    assert p1["has_more"] is True
    assert p1["next_cursor"] is not None

    # Page 2 (6 items)
    p2 = await get_page(p1["next_cursor"])
    assert len(p2["items"]) == 6
    assert p2["has_more"] is True
    assert p2["next_cursor"] is not None

    # Page 3 (3 items, last page)
    p3 = await get_page(p2["next_cursor"])
    assert len(p3["items"]) == 3
    assert p3["has_more"] is False
    assert p3["next_cursor"] is None

    # Total unique items retrieved across all 3 pages must be 15
    all_external_ids = (
        [i["external_id"] for i in p1["items"]]
        + [i["external_id"] for i in p2["items"]]
        + [i["external_id"] for i in p3["items"]]
    )
    assert len(all_external_ids) == 15
    assert len(set(all_external_ids)) == 15
    # Order must be strictly descending: tx-14 down to tx-0
    assert all_external_ids[0] == "pg-tx-14"
    assert all_external_ids[-1] == "pg-tx-0"
