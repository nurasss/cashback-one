"""POS-side agent API schemas: dynamic QR resolution and redemption confirmation codes."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


class QrResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=4, max_length=64)


class QrResolveResponse(BaseModel):
    card_id: uuid.UUID
    barcode: str


class RedemptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barcode: str | None = Field(default=None, pattern=r"^\d{13}$")
    qr_token: str | None = Field(default=None, min_length=4, max_length=64)
    amount: Decimal = Field(..., gt=0, decimal_places=4, max_digits=18)

    @model_validator(mode="after")
    def one_card_reference(self) -> "RedemptionRequest":
        if (self.barcode is None) == (self.qr_token is None):
            raise ValueError("Provide exactly one of barcode or qr_token")
        return self


class RedemptionRequestResponse(BaseModel):
    redemption_id: uuid.UUID
    expires_at: datetime
    recipient: str


class RedemptionVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., pattern=r"^\d{6}$")


class RedemptionVerifyResponse(BaseModel):
    status: str
    barcode: str
    amount: Decimal

    @field_serializer("amount")
    def serialize_amount(self, val: Decimal) -> str:
        return f"{val:.4f}"
