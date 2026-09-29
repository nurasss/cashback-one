"""Data source abstraction layer for POSCENTER ONE.

Includes:
- LoyaltySource protocol.
- StubLoyaltySource: Production-safe default raising ONE_MAPPING_NOT_CONFIGURED.
- FakeLoyaltySource: Test fixture for pagination, batching, and error injection.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import CardSyncItem, SourceBatch, TransactionSyncItem

logger = logging.getLogger(__name__)


class SourceError(Exception):
    """Base error raised by loyalty data source."""


class OneMappingNotConfiguredError(SourceError):
    """Raised when real POSCENTER ONE mapping has not yet been discovered (Stage 0)."""

    def __init__(
        self,
        message: str = (
            "ONE_MAPPING_NOT_CONFIGURED: POSCENTER ONE metadata mapping is not yet configured. "
            "Please complete Stage 0 discovery on a pilot database. See docs/ONE_STAGE0_REQUIRED.md."
        ),
    ) -> None:
        super().__init__(message)


class SourceProtocolError(SourceError):
    """Raised when source violates pagination protocol (e.g. empty page with has_more=True)."""

    def __init__(
        self,
        message: str = "SOURCE_PROTOCOL_ERROR: Source returned empty items with has_more=True.",
    ) -> None:
        super().__init__(message)
        self.code = "SOURCE_PROTOCOL_ERROR"


SourceEmptyPageWithMoreError = SourceProtocolError


@runtime_checkable
class LoyaltySource(Protocol):
    """Protocol for extracting loyalty data from POSCENTER ONE."""

    async def fetch_cards(self, cursor: str | None, limit: int) -> SourceBatch[CardSyncItem]:
        ...

    async def fetch_transactions(self, cursor: str | None, limit: int) -> SourceBatch[TransactionSyncItem]:
        ...

    async def check_health(self) -> bool:
        ...

    async def close(self) -> None:
        ...


class StubLoyaltySource:
    """Default source for production-safe deployments where Stage 0 discovery is pending.

    Fails explicitly with ONE_MAPPING_NOT_CONFIGURED instead of guessing 1C schemas.
    """

    async def fetch_cards(self, cursor: str | None, limit: int) -> SourceBatch[CardSyncItem]:
        raise OneMappingNotConfiguredError()

    async def fetch_transactions(self, cursor: str | None, limit: int) -> SourceBatch[TransactionSyncItem]:
        raise OneMappingNotConfiguredError()

    async def check_health(self) -> bool:
        # Returns False because mapping is not configured
        return False

    async def close(self) -> None:
        pass


class FakeLoyaltySource:
    """In-memory source for testing agent runtime, cursor progression, and error recovery."""

    def __init__(
        self,
        cards: list[CardSyncItem] | None = None,
        transactions: list[TransactionSyncItem] | None = None,
    ) -> None:
        self.cards: list[CardSyncItem] = list(cards or [])
        self.transactions: list[TransactionSyncItem] = list(transactions or [])
        self.is_healthy = True
        self.cards_error: Exception | None = None
        self.transactions_error: Exception | None = None
        self.simulate_stalled_cursor_on_cards = False
        self.simulate_stalled_cursor_on_transactions = False
        self.simulate_empty_page_with_more_on_cards = False
        self.simulate_empty_page_with_more_on_transactions = False
        self.is_closed = False

    async def fetch_cards(self, cursor: str | None, limit: int) -> SourceBatch[CardSyncItem]:
        if self.cards_error:
            err = self.cards_error
            self.cards_error = None
            raise err

        if self.simulate_empty_page_with_more_on_cards:
            return SourceBatch[CardSyncItem](
                items=[],
                next_cursor=cursor,
                has_more=True,
            )

        offset = int(cursor) if (cursor and cursor.isdigit()) else 0
        batch = self.cards[offset : offset + limit]
        next_offset = offset + len(batch)
        has_more = next_offset < len(self.cards)
        next_cursor = str(next_offset) if batch else cursor

        if self.simulate_stalled_cursor_on_cards:
            # Simulate buggy source where has_more is True but cursor didn't advance
            return SourceBatch[CardSyncItem](
                items=batch,
                next_cursor=cursor,
                has_more=True,
            )

        return SourceBatch[CardSyncItem](
            items=batch,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def fetch_transactions(self, cursor: str | None, limit: int) -> SourceBatch[TransactionSyncItem]:
        if self.transactions_error:
            err = self.transactions_error
            self.transactions_error = None
            raise err

        if self.simulate_empty_page_with_more_on_transactions:
            return SourceBatch[TransactionSyncItem](
                items=[],
                next_cursor=cursor,
                has_more=True,
            )

        offset = int(cursor) if (cursor and cursor.isdigit()) else 0
        batch = self.transactions[offset : offset + limit]
        next_offset = offset + len(batch)
        has_more = next_offset < len(self.transactions)
        next_cursor = str(next_offset) if batch else cursor

        if self.simulate_stalled_cursor_on_transactions:
            return SourceBatch[TransactionSyncItem](
                items=batch,
                next_cursor=cursor,
                has_more=True,
            )

        return SourceBatch[TransactionSyncItem](
            items=batch,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def check_health(self) -> bool:
        return self.is_healthy

    async def close(self) -> None:
        self.is_closed = True


def get_loyalty_source(settings: AgentSettings) -> LoyaltySource:
    """Factory creating the appropriate LoyaltySource based on configuration."""
    if settings.one_adapter_mode == "fake":
        return FakeLoyaltySource()
    # Default to StubLoyaltySource
    return StubLoyaltySource()
