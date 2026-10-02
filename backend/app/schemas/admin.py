import re
import uuid
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.admin_types import AdminRole

T = TypeVar("T")


class AdminLoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.strip().lower()


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AdminBusinessIdentity(BaseModel):
    id: uuid.UUID
    name: str
    status: str


class AdminIdentity(BaseModel):
    id: uuid.UUID
    login: str
    role: AdminRole
    business: AdminBusinessIdentity | None


class AdminMeResponse(BaseModel):
    admin: AdminIdentity


class LogoutResponse(BaseModel):
    status: Literal["ok"] = "ok"


class PaginationParams(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)


class Page(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    has_more: bool


class BusinessListItem(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    colors: dict[str, object] | None
    barcode_prefixes: list[str] | None
    status: str
    created_at: datetime
    updated_at: datetime


class BusinessDetail(BusinessListItem):
    cards_count: int
    unblocked_cards_count: int
    customers_with_cards_count: int
    agents_count: int


AgentHealth = Literal["online", "stale", "never_connected", "error", "disabled"]


class AgentItem(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    business_name: str
    status: str
    health: AgentHealth
    last_seen_at: datetime | None
    version: str | None
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime


class AgentDetail(AgentItem):
    pass


class AgentHealthCounts(BaseModel):
    online: int = 0
    stale: int = 0
    never_connected: int = 0
    error: int = 0
    disabled: int = 0


class DashboardResponse(BaseModel):
    business_id: uuid.UUID | None
    business_name: str | None
    period_from: datetime
    period_to: datetime
    period_days: int
    customers_with_business_cards: int
    cards: int
    unblocked_cards: int
    transactions: int
    agents: AgentHealthCounts


class CardSearchRequest(BaseModel):
    barcode: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    business_id: uuid.UUID | None = None

    @field_validator("barcode")
    @classmethod
    def validate_barcode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not re.fullmatch(r"[0-9]{13}", cleaned):
            raise ValueError("barcode must be exactly 13 digits")
        return cleaned

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.core.phone import normalize_phone

        try:
            normalized = normalize_phone(value)
        except ValueError:
            raise ValueError("phone is invalid") from None
        if normalized is None:
            raise ValueError("phone is invalid")
        return normalized

    @model_validator(mode="after")
    def require_filter(self) -> "CardSearchRequest":
        if self.barcode is None and self.phone is None:
            raise ValueError("Provide an exact barcode or phone filter")
        return self


class CardListItem(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    business_name: str
    barcode: str
    phone_masked: str | None
    balance: str
    is_blocked: bool
    updated_at: datetime
    bind_method: str | None
    bound_at: datetime | None
    hidden_at: datetime | None


class CardDetail(CardListItem):
    full_name: str | None
    owner_language: str | None


class UserSearchRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    business_id: uuid.UUID | None = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        from app.core.phone import normalize_phone

        try:
            normalized = normalize_phone(value)
        except ValueError:
            raise ValueError("phone is invalid") from None
        if normalized is None:
            raise ValueError("phone is invalid")
        return normalized


class UserListItem(BaseModel):
    id: uuid.UUID
    phone_masked: str | None
    language: str
    created_at: datetime
    business_cards_count: int


class UserDetail(BaseModel):
    id: uuid.UUID
    phone: str | None
    language: str
    created_at: datetime
    cards: Page[CardListItem]


class AuditItem(BaseModel):
    id: uuid.UUID
    actor: str
    action: str
    entity: str
    created_at: datetime
