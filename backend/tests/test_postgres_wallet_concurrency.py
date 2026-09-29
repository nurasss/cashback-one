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
    - All concurrent responses return 200 with the exact same cards.
    """
    phone = "+77018880011"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz 1")
        s.add(biz)
        await s.flush()

        cards = [
            Card(
                business_id=biz.id,
                barcode=f"PG-CARD-{i}",
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

    # Check database rows in user_cards
    async with pg_session_maker() as s:
        bindings = (
            await s.scalars(
                select(UserCard).where(UserCard.user_id == user_id)
            )
        ).all()
        assert len(bindings) == 3


@pytest.mark.asyncio
async def test_pg_wallet_02_concurrent_auto_bind_competing_sessions(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-02: Concurrent auto_bind across isolated database sessions.

    PostgreSQL unique constraint on card_id and ON CONFLICT DO NOTHING ensures:
    - Zero IntegrityError / 500 exceptions under concurrent auto-bind calls.
    - Exactly 1 binding exists in user_cards for the card.
    """
    phone = "+77018880022"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz 2")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="PG-COMPETING-CARD",
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
    # At least one transaction successfully bound the card, others completed without error
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
    """PG-WALLET-03: Concurrent DELETE /me/cards/{id} calls.

    Verifies:
    - Exactly one request succeeds with 204 No Content.
    - Remaining requests encounter 404 (already hidden).
    - Zero IntegrityError or deadlock.
    - Underlying card in cards table is unmodified.
    """
    phone = "+77018880033"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz 3")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="PG-HIDE-CARD",
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
            device_id="pg-device-3",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(auth_session)
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=auth_session.id)
        card_id = card.id

    async def call_delete() -> int:
        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            async with pg_session_maker() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.delete(
                f"/me/cards/{card_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code

    delete_results = await asyncio.gather(*(call_delete() for _ in range(5)))
    assert 204 in delete_results
    assert delete_results.count(204) == 1
    assert delete_results.count(404) == 4

    # Card remains intact in database
    async with pg_session_maker() as s:
        c = await s.get(Card, card_id)
        assert c is not None
        assert c.balance == Decimal("500.0000")

        uc = (
            await s.scalars(
                select(UserCard).where(UserCard.card_id == card_id)
            )
        ).one()
        assert uc.hidden_at is not None


@pytest.mark.asyncio
async def test_pg_wallet_04_transaction_pagination_consistency(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-WALLET-04: Keyset cursor pagination over PostgreSQL with composite index."""
    phone = "+77018880044"
    async with pg_session_maker() as s:
        biz = Business(name="PG Biz 4")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode="PG-TX-PAGINATE-CARD",
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
            device_id="pg-device-4",
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
