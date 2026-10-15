"""In-memory test loyalty source for Pre-ONE End-to-End integration testing.

CRITICAL PROJECT BOUNDARY:
This file exists exclusively in e2e/ as a test dependency.
It is NEVER imported or available in production agent or backend code paths.
It strictly emits domain DTOs (CardSyncItem, TransactionSyncItem) without
making any assumptions about future POSCENTER ONE internal 1C schema/metadata.
"""

from __future__ import annotations

import logging
from typing import Any

from poscenter_loyalty_agent.models import CardSyncItem, SourceBatch, TransactionSyncItem
from poscenter_loyalty_agent.source import LoyaltySource

logger = logging.getLogger(__name__)


class TestLoyaltySource(LoyaltySource):
    """Deterministic in-memory LoyaltySource for Pre-ONE integration tests."""

    __test__ = False

    def __init__(
        self,
        cards: list[CardSyncItem] | None = None,
        transactions: list[TransactionSyncItem] | None = None,
    ) -> None:
        self._cards: list[CardSyncItem] = list(cards or [])
        self._transactions: list[TransactionSyncItem] = list(transactions or [])
        self._cards_error: Exception | None = None
        self._transactions_error: Exception | None = None
        self.is_healthy: bool = True
        self.is_closed: bool = False

    def set_cards(self, cards: list[CardSyncItem]) -> None:
        self._cards = list(cards)

    def add_card(self, card: CardSyncItem) -> None:
        self._cards.append(card)

    def set_transactions(self, transactions: list[TransactionSyncItem]) -> None:
        self._transactions = list(transactions)

    def add_transaction(self, transaction: TransactionSyncItem) -> None:
        self._transactions.append(transaction)

    def fail_next_cards(self, error: Exception) -> None:
        self._cards_error = error

    def fail_next_transactions(self, error: Exception) -> None:
        self._transactions_error = error

    async def fetch_cards(self, cursor: str | None, limit: int) -> SourceBatch[CardSyncItem]:
        if self._cards_error is not None:
            err = self._cards_error
            self._cards_error = None
            raise err

        offset = int(cursor) if (cursor and cursor.isdigit()) else 0
        batch = self._cards[offset : offset + limit]
        next_offset = offset + len(batch)
        has_more = next_offset < len(self._cards)
        next_cursor = str(next_offset) if batch else cursor

        return SourceBatch[CardSyncItem](
            items=batch,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def fetch_transactions(self, cursor: str | None, limit: int) -> SourceBatch[TransactionSyncItem]:
        if self._transactions_error is not None:
            err = self._transactions_error
            self._transactions_error = None
            raise err

        offset = int(cursor) if (cursor and cursor.isdigit()) else 0
        batch = self._transactions[offset : offset + limit]
        next_offset = offset + len(batch)
        has_more = next_offset < len(self._transactions)
        next_cursor = str(next_offset) if batch else cursor

        return SourceBatch[TransactionSyncItem](
            items=batch,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def check_health(self) -> bool:
        return self.is_healthy

    async def close(self) -> None:
        self.is_closed = True
