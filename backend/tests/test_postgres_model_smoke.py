import os
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.time import utcnow
from app.db.base import Base
from app.models.entities import Business, Card, Transaction
from app.services.agent_auth import issue_agent_key

PG_URL = os.environ.get(
    "POSTGRES_TEST_URL",
    "postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test",
)


@pytest.mark.asyncio
async def test_postgres_model_types_smoke() -> None:
    """PostgreSQL 16 basic model smoke test: verify DDL, foreign keys, and 4-decimal precision."""
    try:
        engine = create_async_engine(PG_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL 16 connection skipped: {exc}")

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Create Business & Agent
        biz = Business(name="Postgres Production Pilot")
        session.add(biz)
        await session.commit()

        _agent, _raw_key = await issue_agent_key(session, biz.id, version="1.0.0-pg")
        await session.commit()

        # Insert Card with 4-decimal balance
        card = Card(
            business_id=biz.id,
            barcode="7777777777777",
            phone="+77007777777",
            full_name="Postgres Verified User",
            balance=Decimal("9999.8888"),
        )
        session.add(card)
        await session.commit()

        # Insert Transaction
        tx = Transaction(
            card_id=card.id,
            external_id="PG-TX-001",
            type="accrual",
            amount=Decimal("123.4500"),
            balance_after=Decimal("9999.8888"),
            occurred_at=utcnow(),
            receipt_ref="REC-PG-1",
            store="Алматы Молл",
        )
        session.add(tx)
        await session.commit()

        # Verify query and types in PostgreSQL
        loaded_card = await session.scalar(select(Card).where(Card.id == card.id))
        assert loaded_card is not None
        assert loaded_card.balance == Decimal("9999.8888")
        assert loaded_card.phone == "+77007777777"

        loaded_tx = await session.scalar(select(Transaction).where(Transaction.card_id == card.id))
        assert loaded_tx is not None
        assert loaded_tx.amount == Decimal("123.4500")

    await engine.dispose()
