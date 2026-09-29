from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Business, Card
from app.services.agent_auth import issue_agent_key


@pytest.mark.asyncio
async def test_cards_sync_initial_and_update(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Card Sync Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    time_1 = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC).isoformat()
    time_2 = datetime(2026, 9, 29, 11, 0, 0, tzinfo=UTC).isoformat()

    # Initial insert
    res1 = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={
            "cards": [
                {
                    "barcode": "0123456789012",  # leading zero
                    "phone": "87001112233",
                    "full_name": "Иванов Иван",
                    "balance": "100.5000",
                    "is_blocked": False,
                    "updated_at": time_1,
                }
            ]
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["received"] == 1
    assert data1["created"] == 1
    assert data1["updated"] == 0
    assert data1["ignored_stale"] == 0

    # Verify stored card and leading zero
    card = await db_session.scalar(select(Card).where(Card.business_id == biz.id))
    assert card is not None
    assert card.barcode == "0123456789012"
    assert card.phone == "+77001112233"  # normalized
    assert card.balance == Decimal("100.5000")

    # Update with newer timestamp
    res2 = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={
            "cards": [
                {
                    "barcode": "0123456789012",
                    "phone": "87001112233",
                    "full_name": "Иванов Иван Иванович",
                    "balance": "250.0000",
                    "is_blocked": False,
                    "updated_at": time_2,
                }
            ]
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["created"] == 0
    assert data2["updated"] == 1
    assert data2["ignored_stale"] == 0

    # Check updated balance in DB
    await db_session.refresh(card)
    assert card.balance == Decimal("250.0000")
    assert card.full_name == "Иванов Иван Иванович"


@pytest.mark.asyncio
async def test_cards_sync_stale_data_protection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Stale Test Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    time_newer = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC).isoformat()
    time_older = datetime(2026, 9, 29, 11, 0, 0, tzinfo=UTC).isoformat()

    # Sync newer snapshot
    await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={
            "cards": [
                {
                    "barcode": "2222222222222",
                    "balance": "500.0000",
                    "updated_at": time_newer,
                }
            ]
        },
    )

    # Reconnect send older snapshot
    res_stale = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={
            "cards": [
                {
                    "barcode": "2222222222222",
                    "balance": "300.0000",
                    "updated_at": time_older,
                }
            ]
        },
    )
    assert res_stale.status_code == 200
    data = res_stale.json()
    assert data["created"] == 0
    assert data["updated"] == 0
    assert data["ignored_stale"] == 1

    # In DB, balance must remain 500.0000
    card = await db_session.scalar(select(Card).where(Card.barcode == "2222222222222"))
    assert card is not None
    assert card.balance == Decimal("500.0000")


@pytest.mark.asyncio
async def test_cards_sync_multi_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz_a = Business(name="Biz A")
    biz_b = Business(name="Biz B")
    db_session.add_all([biz_a, biz_b])
    await db_session.commit()

    _, key_a = await issue_agent_key(db_session, biz_a.id)
    _, key_b = await issue_agent_key(db_session, biz_b.id)
    await db_session.commit()

    shared_barcode = "3333333333333"
    now_iso = datetime.now(UTC).isoformat()

    # Agent A syncs card
    res_a = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key_a},
        json={
            "cards": [
                {
                    "barcode": shared_barcode,
                    "balance": "100.0000",
                    "updated_at": now_iso,
                }
            ]
        },
    )
    assert res_a.status_code == 200

    # Agent B syncs card with same barcode
    res_b = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key_b},
        json={
            "cards": [
                {
                    "barcode": shared_barcode,
                    "balance": "200.0000",
                    "updated_at": now_iso,
                }
            ]
        },
    )
    assert res_b.status_code == 200

    cards = (await db_session.scalars(select(Card).where(Card.barcode == shared_barcode))).all()
    assert len(cards) == 2
    assert {c.business_id for c in cards} == {biz_a.id, biz_b.id}


@pytest.mark.asyncio
async def test_cards_sync_validation_errors(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Validation Biz")
    db_session.add(biz)
    await db_session.commit()

    _, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()

    # 1. Invalid barcode: not 13 digits
    res_bad_barcode = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={
            "cards": [
                {
                    "barcode": "12345",  # invalid
                    "balance": "10.0000",
                    "updated_at": now_iso,
                }
            ]
        },
    )
    assert res_bad_barcode.status_code == 422

    # 2. Invalid phone
    res_bad_phone = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={
            "cards": [
                {
                    "barcode": "4444444444444",
                    "phone": "invalid-letters",
                    "balance": "10.0000",
                    "updated_at": now_iso,
                }
            ]
        },
    )
    assert res_bad_phone.status_code == 422
    assert res_bad_phone.json()["error"]["code"] == "INVALID_PHONE_FORMAT"


@pytest.mark.asyncio
async def test_cards_sync_batch_size_limit(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Limit Biz")
    db_session.add(biz)
    await db_session.commit()

    _, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    now_iso = datetime.now(UTC).isoformat()

    # Create batch exceeding 500 limit
    oversized = [
        {
            "barcode": f"{i:013d}",
            "balance": "1.0000",
            "updated_at": now_iso,
        }
        for i in range(501)
    ]

    res = await client.post(
        "/agent/sync/cards",
        headers={"X-Agent-Key": key},
        json={"cards": oversized},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "SYNC_BATCH_TOO_LARGE"
