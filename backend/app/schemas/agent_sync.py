from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BARCODE_REGEX


class CardSyncItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barcode: Annotated[
        str,
        Field(
            pattern=BARCODE_REGEX,
            description="Card barcode (6 to 15 digits, preserved with leading zeroes)",
        ),
    ]
    phone: str | None = Field(default=None, max_length=32)
    full_name: str | None = Field(default=None, max_length=255)
    balance: Decimal = Field(..., decimal_places=4, max_digits=18)
    is_blocked: bool = Field(default=False)
    spend_total: Decimal | None = Field(
        default=None,
        decimal_places=4,
        max_digits=18,
        ge=0,
        description="Cumulative purchase amount in ONE (drives loyalty level progress)",
    )
    updated_at: datetime = Field(..., description="Timestamp of card update in ONE")


class CardsSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[CardSyncItem] = Field(..., description="Batch of cards from ONE")


class CardsSyncResponse(BaseModel):
    received: int
    created: int
    updated: int
    ignored_stale: int


class TransactionSyncItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(..., min_length=1, max_length=128)
    barcode: Annotated[
        str,
        Field(
            pattern=BARCODE_REGEX,
            description="Card barcode (6 to 15 digits)",
        ),
    ]
    type: str = Field(..., min_length=1, max_length=32, description="accrual, redemption, etc.")
    amount: Decimal = Field(..., decimal_places=4, max_digits=18)
    balance_after: Decimal = Field(..., decimal_places=4, max_digits=18)
    occurred_at: datetime
    receipt_ref: str | None = Field(default=None, max_length=128)
    store: str | None = Field(default=None, max_length=255)


class TransactionsSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transactions: list[TransactionSyncItem] = Field(
        ..., description="Batch of bonus transactions from ONE"
    )


class TransactionsSyncResponse(BaseModel):
    received: int
    created: int
    duplicates: int


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str | None = Field(default=None, max_length=64)
    last_successful_sync_at: datetime | None = None
    error: str | None = Field(default=None, max_length=1024)


class HeartbeatResponse(BaseModel):
    status: str = "ok"
