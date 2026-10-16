import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class BindCardRequest(BaseModel):
    """Request payload for manual card binding via barcode/QR."""

    barcode: str
    business_id: uuid.UUID | None = None

    @field_validator("barcode", mode="before")
    @classmethod
    def validate_barcode(cls, val: Any) -> str:
        if not isinstance(val, str):
            raise ValueError("Barcode must be a string")  # noqa: TRY004
        cleaned = val.strip()
        if not re.fullmatch(r"^\d{13}$", cleaned):
            raise ValueError("Barcode must be exactly 13 digits")
        return cleaned


class BusinessBranding(BaseModel):
    """Business branding configuration for mobile UI."""

    model_config = ConfigDict(from_attributes=True)

    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None


class BusinessInfo(BaseModel):
    """Business summary in card response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    branding: BusinessBranding | None = None


def _money(val: Decimal | None) -> str | None:
    return None if val is None else f"{val:.4f}"


class LoyaltyLevel(BaseModel):
    """One configured level of the business loyalty program."""

    level: int
    name: str | None = None
    threshold: Decimal
    percent: Decimal

    @field_serializer("threshold", "percent")
    def serialize_money(self, val: Decimal) -> str:
        return f"{val:.4f}"


class LoyaltyTierInfo(BaseModel):
    """Customer's loyalty level on a card and progress to the next level."""

    level: int
    name: str | None = None
    percent: Decimal
    max_percent: Decimal
    spend_total: Decimal | None = None
    next_level: int | None = None
    next_threshold: Decimal | None = None
    remaining: Decimal | None = None
    levels: list[LoyaltyLevel] = []

    @field_serializer("percent", "max_percent", "spend_total", "next_threshold", "remaining")
    def serialize_money(self, val: Decimal | None) -> str | None:
        return _money(val)


class CustomerCardResponse(BaseModel):
    """Customer loyalty card view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    barcode: str
    balance: Decimal
    is_blocked: bool
    updated_at: datetime
    bound_at: datetime
    bind_method: str
    business: BusinessInfo
    tier: LoyaltyTierInfo | None = None

    @field_serializer("balance")
    def serialize_balance(self, val: Decimal) -> str:
        return f"{val:.4f}"


class CustomerTransactionResponse(BaseModel):
    """Transaction item in customer card history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str
    type: str
    amount: Decimal
    balance_after: Decimal
    occurred_at: datetime
    receipt_ref: str | None = None
    store: str | None = None

    @field_serializer("amount")
    def serialize_amount(self, val: Decimal) -> str:
        return f"{val:.4f}"

    @field_serializer("balance_after")
    def serialize_balance_after(self, val: Decimal) -> str:
        return f"{val:.4f}"


class CustomerTransactionHistoryResponse(BaseModel):
    """Cursor-paginated list of customer transactions."""

    items: list[CustomerTransactionResponse]
    next_cursor: str | None = None
    has_more: bool = False
