from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Business, Card, Transaction
from app.services.agent_auth import issue_agent_key


@pytest.mark.asyncio
async def test_transactions_sync_initial_and_idempotent_replay(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Tx Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, key = await issue_agent_key(db_session, biz.id)
    card = Card(
        business_id=biz.id,
        barcode="1000000000001",
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()
    tx_payload = {
        "transactions": [
            {
                "external_id": "ONE-TX-1001",
                "barcode": "1000000000001",
                "type": "accrual",
                "amount": "50.1234",
                "balance_after": "550.1234",
                "occurred_at": now_iso,
                "receipt_ref": "CHECK-8877",
                "store": "Магазин №1",
            }
        ]
    }

    # 1. Initial insert
    res1 = await client.post(
        "/agent/sync/transactions",
        headers={"X-Agent-Key": key},
        json=tx_payload,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["received"] == 1
    assert data1["created"] == 1
    assert data1["duplicates"] == 0

    # Verify DB record & Decimal precision
    tx = await db_session.scalar(select(Transaction).where(Transaction.card_id == card.id))
    assert tx is not None
    assert tx.external_id == "ONE-TX-1001"
    assert tx.amount == Decimal("50.1234")
    assert tx.balance_after == Decimal("550.1234")
    assert tx.receipt_ref == "CHECK-8877"

    # 2. Replay same payload
    res2 = await client.post(
        "/agent/sync/transactions",
        headers={"X-Agent-Key": key},
        json=tx_payload,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["received"] == 1
    assert data2["created"] == 0
    assert data2["duplicates"] == 1

    # Exactly 1 transaction exists in DB
    all_txs = (await db_session.scalars(select(Transaction).where(Transaction.card_id == card.id))).all()
    assert len(all_txs) == 1


@pytest.mark.asyncio
async def test_transactions_same_external_id_on_different_cards(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Tx Multi Card Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, key = await issue_agent_key(db_session, biz.id)
    card1 = Card(business_id=biz.id, barcode="1000000000002")
    card2 = Card(business_id=biz.id, barcode="1000000000003")
    db_session.add_all([card1, card2])
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()
    shared_external_id = "CHECK-RECEIPT-999"

    # Send same external_id for card 1 and card 2
    res = await client.post(
        "/agent/sync/transactions",
        headers={"X-Agent-Key": key},
        json={
            "transactions": [
                {
                    "external_id": shared_external_id,
                    "barcode": "1000000000002",
                    "type": "accrual",
                    "amount": "10.0000",
                    "balance_after": "10.0000",
                    "occurred_at": now_iso,
                },
                {
                    "external_id": shared_external_id,
                    "barcode": "1000000000003",
                    "type": "accrual",
                    "amount": "20.0000",
                    "balance_after": "20.0000",
                    "occurred_at": now_iso,
                },
            ]
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["received"] == 2
    assert data["created"] == 2
    assert data["duplicates"] == 0


@pytest.mark.asyncio
async def test_transactions_unknown_card_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Unknown Card Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()

    # Barcode not yet synced
    res = await client.post(
        "/agent/sync/transactions",
        headers={"X-Agent-Key": key},
        json={
            "transactions": [
                {
                    "external_id": "ORPHAN-001",
                    "barcode": "9999999999999",
                    "type": "accrual",
                    "amount": "100.0000",
                    "balance_after": "100.0000",
                    "occurred_at": now_iso,
                }
            ]
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "UNKNOWN_CARD_FOR_TRANSACTION"

    # Verify no orphan transaction created in DB
    txs = (await db_session.scalars(select(Transaction))).all()
    assert len(txs) == 0


@pytest.mark.asyncio
async def test_transactions_cross_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz_a = Business(name="Biz A")
    biz_b = Business(name="Biz B")
    db_session.add_all([biz_a, biz_b])
    await db_session.commit()

    _agent_a, key_a = await issue_agent_key(db_session, biz_a.id)
    _agent_b, _key_b = await issue_agent_key(db_session, biz_b.id)

    # Card belongs strictly to Biz B
    card_b = Card(business_id=biz_b.id, barcode="5555555555555")
    db_session.add(card_b)
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()

    # Agent A attempts to write a transaction for Biz B's card barcode
    res = await client.post(
        "/agent/sync/transactions",
        headers={"X-Agent-Key": key_a},
        json={
            "transactions": [
                {
                    "external_id": "ATTACK-001",
                    "barcode": "5555555555555",
                    "type": "redemption",
                    "amount": "100.0000",
                    "balance_after": "0.0000",
                    "occurred_at": now_iso,
                }
            ]
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "UNKNOWN_CARD_FOR_TRANSACTION"

    # DB remains untampered
    txs = (await db_session.scalars(select(Transaction))).all()
    assert len(txs) == 0


@pytest.mark.asyncio
async def test_transactions_batch_size_limit(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Tx Limit Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, key = await issue_agent_key(db_session, biz.id)
    card = Card(business_id=biz.id, barcode="1000000000009")
    db_session.add(card)
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()

    oversized = [
        {
            "external_id": f"TX-{i}",
            "barcode": "1000000000009",
            "type": "accrual",
            "amount": "1.0000",
            "balance_after": "1.0000",
            "occurred_at": now_iso,
        }
        for i in range(1001)
    ]

    res = await client.post(
        "/agent/sync/transactions",
        headers={"X-Agent-Key": key},
        json={"transactions": oversized},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "SYNC_BATCH_TOO_LARGE"
