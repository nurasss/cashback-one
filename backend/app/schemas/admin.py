import json
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.admin_types import AdminRole
from app.schemas.common import BARCODE_ERROR_MSG, BARCODE_REGEX

T = TypeVar("T")
BusinessStatus = Literal["active", "inactive"]


def _normalize_business_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("name must not be empty")
    return normalized


def _validate_logo_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if len(normalized) > 1024:
        raise ValueError("logo_url is too long")
    try:
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        raise ValueError("logo_url must be a valid HTTPS URL") from None
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(ord(character) < 32 for character in normalized)
    ):
        raise ValueError("logo_url must be a valid HTTPS URL without embedded credentials")
    return normalized


_KNOWN_BRANDING_COLOR_KEYS = {"primary", "primary_color", "accent", "accent_color"}


def _validate_colors(value: dict[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    if len(value) > 64:
        raise ValueError("colors may contain at most 64 entries")

    for key in _KNOWN_BRANDING_COLOR_KEYS:
        if key in value:
            color_val = value[key]
            if color_val is not None and not isinstance(color_val, str):
                raise ValueError(f"{key} must be a string or null")
            if isinstance(color_val, str) and len(color_val) > 128:
                raise ValueError(f"{key} is too long")

    def check(item: object, depth: int = 0) -> None:
        if depth > 5:
            raise ValueError("colors JSON nesting is too deep")
        if isinstance(item, dict):
            if len(item) > 64 or any(not isinstance(key, str) or len(key) > 64 for key in item):
                raise ValueError("colors JSON object is too large")
            for child in item.values():
                check(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 64:
                raise ValueError("colors JSON array is too large")
            for child in item:
                check(child, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("colors must contain only JSON values")

    check(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("colors must be valid JSON") from None
    if len(encoded.encode("utf-8")) > 8192:
        raise ValueError("colors JSON exceeds 8 KiB")
    return value


def _validate_barcode_prefixes(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if len(value) > 64:
        raise ValueError("barcode_prefixes may contain at most 64 entries")
    if any(not prefix or prefix != prefix.strip() or len(prefix) > 32 for prefix in value):
        raise ValueError("barcode prefixes must be non-empty strings up to 32 characters")
    return value


class BusinessCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    logo_url: str | None = Field(default=None, max_length=1024)
    colors: dict[str, object] | None = None
    barcode_prefixes: list[str] | None = Field(default=None, max_length=64)
    status: BusinessStatus = "active"
    create_manager: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_business_name(value) or ""

    _logo = field_validator("logo_url")(_validate_logo_url)
    _colors = field_validator("colors")(_validate_colors)
    _prefixes = field_validator("barcode_prefixes")(_validate_barcode_prefixes)

    @model_validator(mode="after")
    def enforce_payload_bound(self) -> "BusinessCreateRequest":
        encoded = json.dumps(self.model_dump(), ensure_ascii=False, default=str, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("business payload exceeds 16 KiB")
        return self


class LoyaltyTier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1, le=99)
    name: str | None = Field(default=None, max_length=40)
    threshold: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    percent: Decimal = Field(ge=0, le=100, max_digits=6, decimal_places=2)

    @field_serializer("threshold", "percent")
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value.normalize(), "f")


def _validate_tiers(value: list[LoyaltyTier] | None) -> list[LoyaltyTier] | None:
    if value is None:
        return None
    if not 1 <= len(value) <= 10:
        raise ValueError("loyalty_tiers must contain 1 to 10 levels")
    ordered = sorted(value, key=lambda tier: tier.threshold)
    if ordered[0].threshold != 0:
        raise ValueError("the first loyalty level must start at threshold 0")
    if len({tier.level for tier in value}) != len(value) or len({t.threshold for t in value}) != len(value):
        raise ValueError("loyalty levels and thresholds must be unique")
    if [tier.level for tier in ordered] != sorted(tier.level for tier in value):
        raise ValueError("higher levels must have higher thresholds")
    return ordered


class BusinessUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=1024)
    colors: dict[str, object] | None = None
    barcode_prefixes: list[str] | None = Field(default=None, max_length=64)
    status: BusinessStatus | None = None
    loyalty_tiers: list[LoyaltyTier] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return _normalize_business_name(value)

    _logo = field_validator("logo_url")(_validate_logo_url)
    _colors = field_validator("colors")(_validate_colors)
    _prefixes = field_validator("barcode_prefixes")(_validate_barcode_prefixes)
    _tiers = field_validator("loyalty_tiers")(_validate_tiers)

    @model_validator(mode="after")
    def require_fields_and_non_null_required_values(self) -> "BusinessUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one business field to update")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self

    @model_validator(mode="after")
    def enforce_payload_bound(self) -> "BusinessUpdateRequest":
        encoded = json.dumps(
            self.model_dump(exclude_unset=True), ensure_ascii=False, default=str, separators=(",", ":")
        )
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("business update exceeds 16 KiB")
        return self

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


class CardListPaginationParams(BaseModel):
    limit: int = Field(default=25, ge=1, le=30)
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
    loyalty_tiers: list[dict[str, object]] | None = None
    created_at: datetime
    updated_at: datetime


class BusinessDetail(BusinessListItem):
    cards_count: int
    unblocked_cards_count: int
    customers_with_cards_count: int
    agents_count: int


class ManagerAccessDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    password: str
    login_url: str
    one_time: Literal[True] = True


class BusinessCreatedResponse(BusinessDetail):
    manager_access: ManagerAccessDisclosure | None = None


AgentHealth = Literal["online", "stale", "never_connected", "error", "disabled"]
AgentCommandStatus = Literal["pending", "running", "completed", "failed"]
CardUnbindStatus = Literal["unbound", "already_unbound"]


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


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID


class AgentDetail(AgentItem):
    pass


class AgentKeyDisclosureResponse(BaseModel):
    agent: AgentItem
    api_key: str


class AgentRevokeResponse(BaseModel):
    agent: AgentItem
    status: Literal["revoked"] = "revoked"


class AgentCommandResponse(BaseModel):
    command_id: uuid.UUID
    status: AgentCommandStatus
    execution: Literal["deferred"] = "deferred"


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
        if not re.fullmatch(BARCODE_REGEX, cleaned):
            raise ValueError(BARCODE_ERROR_MSG)
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
    admin_user_id: uuid.UUID | None
    business_id: uuid.UUID | None
    action: str
    entity: str
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    created_at: datetime


class CardUnbindResponse(BaseModel):
    status: CardUnbindStatus
