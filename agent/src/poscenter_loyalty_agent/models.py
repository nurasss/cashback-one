from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


BARCODE_REGEX = r"^\d{6,15}$"
BARCODE_ERROR_MSG = "barcode must contain 6 to 15 digits"


def ensure_timezone_aware(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("Timestamp must be timezone-aware (UTC required)")
    return dt


class CardSyncItem(BaseModel):
    """Card snapshot to synchronize with Cloud Backend."""

    model_config = ConfigDict(extra="forbid")

    barcode: Annotated[
        str,
        Field(
            pattern=BARCODE_REGEX,
            description="Card barcode containing 6 to 15 digits (preserved with leading zeroes)",
        ),
    ]
    phone: str | None = Field(default=None, max_length=32)
    full_name: str | None = Field(default=None, max_length=255)
    balance: Decimal = Field(..., decimal_places=4, max_digits=18)
    is_blocked: bool = Field(default=False)
    updated_at: datetime = Field(..., description="Timestamp of card update in ONE")

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, v: datetime) -> datetime:
        res = ensure_timezone_aware(v)
        assert res is not None
        return res


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
            pattern=BARCODE_REGEX,
            description="Card barcode containing 6 to 15 digits",
        ),
    ]
    type: str = Field(..., min_length=1, max_length=32, description="accrual, redemption, etc.")
    amount: Decimal = Field(..., decimal_places=4, max_digits=18)
    balance_after: Decimal = Field(..., decimal_places=4, max_digits=18)
    occurred_at: datetime
    receipt_ref: str | None = Field(default=None, max_length=128)
    store: str | None = Field(default=None, max_length=255)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, v: datetime) -> datetime:
        res = ensure_timezone_aware(v)
        assert res is not None
        return res


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

    @field_validator("last_successful_sync_at")
    @classmethod
    def validate_last_successful_sync_at(cls, v: datetime | None) -> datetime | None:
        return ensure_timezone_aware(v)


class HeartbeatResult(BaseModel):
    """Response from Cloud Backend after heartbeat."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Heartbeat status")


class SourceBatch(BaseModel, Generic[T]):
    """Generic batch retrieved from a LoyaltySource."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class AgentStatus(BaseModel):
    """In-memory or persisted runtime agent status."""

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_successful_sync_at: datetime | None = None
    last_card_sync_at: datetime | None = None
    last_transaction_sync_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    cards_committed_cursor: str | None = None
    transactions_committed_cursor: str | None = None
