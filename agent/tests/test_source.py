"""Tests for LoyaltySource implementations (StubLoyaltySource and FakeLoyaltySource)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from poscenter_loyalty_agent.models import CardSyncItem
from poscenter_loyalty_agent.source import (
    FakeLoyaltySource,
    OneMappingNotConfiguredError,
    StubLoyaltySource,
)


@pytest.mark.asyncio
async def test_stub_loyalty_source_fails_with_one_mapping_not_configured() -> None:
    source = StubLoyaltySource()
    assert not await source.check_health()

    with pytest.raises(OneMappingNotConfiguredError, match="ONE_MAPPING_NOT_CONFIGURED"):
        await source.fetch_cards(cursor=None, limit=10)

    with pytest.raises(OneMappingNotConfiguredError, match="ONE_MAPPING_NOT_CONFIGURED"):
        await source.fetch_transactions(cursor=None, limit=10)


@pytest.mark.asyncio
async def test_fake_loyalty_source_pagination() -> None:
    now = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)
    cards = [
        CardSyncItem(
            barcode=f"10000000000{i:02d}",
            balance=Decimal("100.00"),
            updated_at=now,
        )
        for i in range(5)
    ]
    source = FakeLoyaltySource(cards=cards)

    # First batch of 2
    batch1 = await source.fetch_cards(cursor=None, limit=2)
    assert len(batch1.items) == 2
    assert batch1.has_more is True
    assert batch1.next_cursor == "2"

    # Second batch of 2
    batch2 = await source.fetch_cards(cursor=batch1.next_cursor, limit=2)
    assert len(batch2.items) == 2
    assert batch2.has_more is True
    assert batch2.next_cursor == "4"

    # Final batch of 1
    batch3 = await source.fetch_cards(cursor=batch2.next_cursor, limit=2)
    assert len(batch3.items) == 1
    assert batch3.has_more is False
    assert batch3.next_cursor == "5"


@pytest.mark.asyncio
async def test_fake_source_stalled_cursor_simulation() -> None:
    now = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)
    cards = [
        CardSyncItem(
            barcode="1000000000001",
            balance=Decimal("50.00"),
            updated_at=now,
        )
    ]
    source = FakeLoyaltySource(cards=cards)
    source.simulate_stalled_cursor_on_cards = True

    batch = await source.fetch_cards(cursor="stalled_cursor", limit=10)
    assert batch.has_more is True
    assert batch.next_cursor == "stalled_cursor"
