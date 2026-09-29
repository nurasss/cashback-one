"""Data transfer objects and domain models for POSCENTER Loyalty Agent."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class CardSyncItem(BaseModel):
    """Card snapshot to synchronize with Cloud Backend."""

    model_config = ConfigDict(extra="forbid")

    barcode: Annotated[
        str,
        Field(
            pattern=r"^\d{13}$",
            description="13-digit card barcode (preserved with leading zeroes)",
        ),
    ]
    phone: str | None = Field(default=None, max_length=32)
    full_name: str | None = Field(default=None, max_length=255)
    balance: Decimal = Field(..., decimal_places=4, max_digits=18)
    is_blocked: bool = Field(default=False)
    updated_at: datetime = Field(..., description="Timestamp of card update in ONE")


class CardsSyncPayload(BaseModel):
    """Payload for POST /agent/sync/cards."""

    model_config = ConfigDict(extra="forbid")

    cards: list[CardSyncItem] = Field(..., description="Batch of cards from ONE")


class CardsSyncResult(BaseModel):
    """Response from Cloud Backend after cards sync."""

    model_config = ConfigDict(extra="ignore")

    received: int
    created: int
    updated: int
    ignored_stale: int


class TransactionSyncItem(BaseModel):
    """Transaction entry to synchronize with Cloud Backend."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(..., min_length=1, max_length=128)
    barcode: Annotated[
        str,
        Field(
            pattern=r"^\d{13}$",
            description="13-digit card barcode",
        ),
    ]
    type: str = Field(..., min_length=1, max_length=32, description="accrual, redemption, etc.")
    amount: Decimal = Field(..., decimal_places=4, max_digits=18)
    balance_after: Decimal = Field(..., decimal_places=4, max_digits=18)
    occurred_at: datetime
    receipt_ref: str | None = Field(default=None, max_length=128)
    store: str | None = Field(default=None, max_length=255)


class TransactionsSyncPayload(BaseModel):
    """Payload for POST /agent/sync/transactions."""

    model_config = ConfigDict(extra="forbid")

    transactions: list[TransactionSyncItem] = Field(
        ..., description="Batch of bonus transactions from ONE"
    )


class TransactionsSyncResult(BaseModel):
    """Response from Cloud Backend after transactions sync."""

    model_config = ConfigDict(extra="ignore")

    received: int
    created: int
    duplicates: int


class HeartbeatPayload(BaseModel):
    """Payload for POST /agent/heartbeat."""

    model_config = ConfigDict(extra="forbid")

    version: str | None = Field(default=None, max_length=64)
    last_successful_sync_at: datetime | None = None
    error: str | None = Field(default=None, max_length=1024)


class HeartbeatResult(BaseModel):
    """Response from Cloud Backend after heartbeat."""

    model_config = ConfigDict(extra="ignore")

    status: str = "ok"


class SourceBatch(BaseModel, Generic[T]):
    """Generic batch retrieved from a LoyaltySource."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class AgentStatus(BaseModel):
    """In-memory or persisted runtime agent status."""

    started_at: datetime = Field(default_factory=lambda: datetime.now())
    last_successful_sync_at: datetime | None = None
    last_card_sync_at: datetime | None = None
    last_transaction_sync_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    cards_committed_cursor: str | None = None
    transactions_committed_cursor: str | None = None
