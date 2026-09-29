import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.time import as_utc
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.entities import Business, Card, Transaction
from app.services.agent_auth import issue_agent_key


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


@pytest.fixture
async def pg_client(pg_session_maker) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[no-untyped-def]
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pg_conc_01_concurrent_first_insert_card(
    pg_client: AsyncClient,
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-CONC-01: Two concurrent requests sending the same new card.

    Must result in exactly 1 Card in DB, both HTTP requests completing
    with controlled 200 responses and NO HTTP 500 / unhandled IntegrityError.
    """
    async with pg_session_maker() as s:
        biz = Business(name="PG Conc 01 Biz")
        s.add(biz)
        await s.commit()
        _agent, key = await issue_agent_key(s, biz.id)
        await s.commit()

    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "cards": [
            {
                "barcode": "1111222233334",
                "phone": "+77011112233",
                "full_name": "Concurrent New User",
                "balance": "100.0000",
                "updated_at": now_iso,
            }
        ]
    }

    # Execute two parallel HTTP requests across independent DB connections
    res1, res2 = await asyncio.gather(
        pg_client.post("/agent/sync/cards", headers={"X-Agent-Key": key}, json=payload),
        pg_client.post("/agent/sync/cards", headers={"X-Agent-Key": key}, json=payload),
    )

    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text

    # One request created the card, the second either ignored as stale or updated
    d1, d2 = res1.json(), res2.json()
    assert d1["created"] + d2["created"] == 1
    assert d1["created"] + d1["updated"] + d1["ignored_stale"] == 1
    assert d2["created"] + d2["updated"] + d2["ignored_stale"] == 1

    # Exactly 1 card exists in PostgreSQL
    async with pg_session_maker() as s:
        cards = (
            await s.scalars(
                select(Card).where(
                    Card.business_id == biz.id,
                    Card.barcode == "1111222233334",
                )
            )
        ).all()
        assert len(cards) == 1
        assert cards[0].balance == Decimal("100.0000")


@pytest.mark.asyncio
async def test_pg_conc_02_concurrent_stale_protection(
    pg_client: AsyncClient,
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-CONC-02: Concurrent updates with different timestamps.

    Existing state: 10:00 / 100
    Request A: 11:00 / 200
    Request B: 12:00 / 300

    Regardless of scheduling / commit order, the final state must be 12:00 / 300.
    Old snapshot (11:00) must never overwrite the newer snapshot (12:00).
    """
    t10 = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)
    t11 = datetime(2026, 9, 29, 11, 0, 0, tzinfo=UTC)
    t12 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)

    async with pg_session_maker() as s:
        biz = Business(name="PG Conc 02 Biz")
        s.add(biz)
        await s.commit()
        _agent, key = await issue_agent_key(s, biz.id)

        card = Card(
            business_id=biz.id,
            barcode="5555666677778",
            phone="+77025556677",
            balance=Decimal("100.0000"),
            updated_at=t10,
        )
        s.add(card)
        await s.commit()

    payload_a = {
        "cards": [
            {
                "barcode": "5555666677778",
                "balance": "200.0000",
                "updated_at": t11.isoformat(),
            }
        ]
    }
    payload_b = {
        "cards": [
            {
                "barcode": "5555666677778",
                "balance": "300.0000",
                "updated_at": t12.isoformat(),
            }
        ]
    }

    # Concurrently send both updates
    res_a, res_b = await asyncio.gather(
        pg_client.post("/agent/sync/cards", headers={"X-Agent-Key": key}, json=payload_a),
        pg_client.post("/agent/sync/cards", headers={"X-Agent-Key": key}, json=payload_b),
    )

    assert res_a.status_code == 200, res_a.text
    assert res_b.status_code == 200, res_b.text

    # Final DB record must reflect 12:00 and 300.0000
    async with pg_session_maker() as s:
        final_card = (
            await s.scalars(
                select(Card).where(
                    Card.business_id == biz.id,
                    Card.barcode == "5555666677778",
                )
            )
        ).one()
        assert final_card.balance == Decimal("300.0000")
        assert as_utc(final_card.updated_at) == t12


@pytest.mark.asyncio
async def test_pg_conc_03_concurrent_transaction_replay(
    pg_client: AsyncClient,
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-CONC-03: Two concurrent requests sending the exact same transaction.

    Both requests must succeed with 200, no 500, and exactly 1 transaction saved.
    One response will report created=1, duplicates=0; the other created=0, duplicates=1.
    """
    async with pg_session_maker() as s:
        biz = Business(name="PG Conc 03 Biz")
        s.add(biz)
        await s.commit()
        _agent, key = await issue_agent_key(s, biz.id)

        card = Card(
            business_id=biz.id,
            barcode="9999000011112",
            balance=Decimal("1000.0000"),
        )
        s.add(card)
        await s.commit()
        card_id = card.id

    now_iso = datetime.now(UTC).isoformat()
    tx_payload = {
        "transactions": [
            {
                "external_id": "CONC-TX-777",
                "barcode": "9999000011112",
                "type": "accrual",
                "amount": "50.0000",
                "balance_after": "1050.0000",
                "occurred_at": now_iso,
                "receipt_ref": "CONC-CHECK-1",
            }
        ]
    }

    res1, res2 = await asyncio.gather(
        pg_client.post("/agent/sync/transactions", headers={"X-Agent-Key": key}, json=tx_payload),
        pg_client.post("/agent/sync/transactions", headers={"X-Agent-Key": key}, json=tx_payload),
    )

    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text

    d1, d2 = res1.json(), res2.json()
    assert d1["created"] + d2["created"] == 1
    assert d1["duplicates"] + d2["duplicates"] == 1

    async with pg_session_maker() as s:
        txs = (
            await s.scalars(
                select(Transaction).where(
                    Transaction.card_id == card_id,
                    Transaction.external_id == "CONC-TX-777",
                )
            )
        ).all()
        assert len(txs) == 1
        assert txs[0].amount == Decimal("50.0000")


@pytest.mark.asyncio
async def test_pg_conc_04_tenant_isolation_under_locking(
    pg_client: AsyncClient,
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-CONC-04: Tenant isolation under locking.

    Agent A syncing cannot block or tamper with Business B.
    Agent A cannot sync transactions for Business B's cards.
    """
    async with pg_session_maker() as s:
        biz_a = Business(name="PG Biz A")
        biz_b = Business(name="PG Biz B")
        s.add_all([biz_a, biz_b])
        await s.commit()

        _agent_a, key_a = await issue_agent_key(s, biz_a.id)
        _agent_b, key_b = await issue_agent_key(s, biz_b.id)

        card_b = Card(business_id=biz_b.id, barcode="4444555566667", balance=Decimal("10.0000"))
        s.add(card_b)
        await s.commit()

    now_iso = datetime.now(UTC).isoformat()

    # Concurrent operations from Agent A and Agent B
    res_a, res_b = await asyncio.gather(
        pg_client.post(
            "/agent/sync/transactions",
            headers={"X-Agent-Key": key_a},
            json={
                "transactions": [
                    {
                        "external_id": "ATTACK-TX-001",
                        "barcode": "4444555566667",  # card belongs to biz B
                        "type": "redemption",
                        "amount": "10.0000",
                        "balance_after": "0.0000",
                        "occurred_at": now_iso,
                    }
                ]
            },
        ),
        pg_client.post(
            "/agent/sync/cards",
            headers={"X-Agent-Key": key_b},
            json={
                "cards": [
                    {
                        "barcode": "4444555566667",
                        "balance": "20.0000",
                        "updated_at": now_iso,
                    }
                ]
            },
        ),
    )

    # Agent A was rejected with 422 UNKNOWN_CARD_FOR_TRANSACTION (sanitized message)
    assert res_a.status_code == 422
    assert res_a.json()["error"]["code"] == "UNKNOWN_CARD_FOR_TRANSACTION"
    assert "Card with barcode '4444555566667' does not exist for authenticated business." in res_a.json()["error"]["message"]

    # Agent B was processed normally
    assert res_b.status_code == 200
    assert res_b.json()["updated"] == 1

    # Verify no rogue transactions created in DB
    async with pg_session_maker() as s:
        txs = (await s.scalars(select(Transaction))).all()
        assert len(txs) == 0
