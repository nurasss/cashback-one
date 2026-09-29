import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


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


class CustomerCardResponse(BaseModel):
    """Customer loyalty card view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    barcode: str
    balance: Decimal
    is_blocked: bool
    bound_at: datetime
    bind_method: str
    business: BusinessInfo

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
