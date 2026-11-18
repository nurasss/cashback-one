"""Admin schemas for customer app content: promotions, notifications, stores, and app texts."""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import as_utc, utcnow
from app.schemas.admin import _validate_logo_url

PromotionKind = Literal["banner", "offer"]


def _strip_optional(value: object) -> object:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _reject_bool(value: object) -> object:
    """JSON `true`/`false` must not be silently read as 1/0 in a numeric field."""
    if isinstance(value, bool):
        raise ValueError("a boolean is not a valid number")  # noqa: TRY004 - pydantic turns only ValueError into a 422
    return value


def _strip_required(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped
    return value


class PromotionAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID | None
    kind: str
    title: str
    subtitle: str | None
    badge: str | None
    body: str | None
    image_url: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class _PromotionFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtitle: str | None = Field(default=None, max_length=255)
    badge: str | None = Field(default=None, max_length=40)
    body: str | None = Field(default=None, max_length=4000)
    image_url: str | None = Field(default=None, max_length=1024)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sort_order: int = Field(default=0, ge=-1000, le=1000)
    is_active: bool = True

    _optional = field_validator("subtitle", "badge", "body", "image_url", mode="before")(
        _strip_optional
    )
    _image = field_validator("image_url")(_validate_logo_url)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_4_digit_year(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        try:
            utc_dt = as_utc(value)
        except (ValueError, OverflowError) as exc:
            raise ValueError("Год должен состоять ровно из четырёх цифр") from exc
        if not (1000 <= value.year <= 9999 and 1000 <= utc_dt.year <= 9999):
            raise ValueError("Год должен состоять ровно из четырёх цифр")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "_PromotionFields":
        if self.starts_at and self.ends_at and as_utc(self.ends_at) <= as_utc(self.starts_at):
            raise ValueError("ends_at must be after starts_at")
        return self


class PromotionCreateRequest(_PromotionFields):
    business_id: uuid.UUID | None = None
    kind: PromotionKind = "offer"
    title: str = Field(min_length=1, max_length=120)

    _title = field_validator("title", mode="before")(_strip_required)

    @field_validator("starts_at")
    @classmethod
    def validate_starts_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        now = utcnow()
        val_utc = as_utc(value)
        # Tight tolerance for network latency only (15 seconds, no arbitrary 5-minute past allowance)
        if val_utc < now - timedelta(seconds=15):
            raise ValueError("starts_at cannot be in the past")
        return value

    @model_validator(mode="after")
    def validate_create_window(self) -> "PromotionCreateRequest":
        now = utcnow()
        effective_start = as_utc(self.starts_at) if self.starts_at is not None else now
        if self.ends_at is not None and as_utc(self.ends_at) <= effective_start:
            raise ValueError("ends_at must be after starts_at")
        return self


class PromotionUpdateRequest(_PromotionFields):
    kind: PromotionKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    sort_order: int | None = Field(default=None, ge=-1000, le=1000)  # type: ignore[assignment]
    is_active: bool | None = None  # type: ignore[assignment]

    _title = field_validator("title", mode="before")(_strip_required)

    @model_validator(mode="after")
    def require_fields(self) -> "PromotionUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        for required in ("title", "kind", "sort_order", "is_active"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null")
        return self


class BroadcastPushResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["sent", "disabled", "skipped", "failed"]
    devices: int
    delivered: int


class NotificationAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID | None
    user_id: uuid.UUID | None
    kind: str
    title: str
    body: str
    created_at: datetime
    scheduled_at: datetime | None = None
    push_sent_at: datetime | None = None
    push: BroadcastPushResult | None = None


class NotificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    send_push: bool = True
    scheduled_at: datetime | None = None

    _text = field_validator("title", "body", mode="before")(_strip_required)

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        try:
            val_utc = as_utc(value)
        except (ValueError, OverflowError) as exc:
            raise ValueError("Год должен состоять ровно из четырёх цифр") from exc
        if not (1000 <= value.year <= 9999 and 1000 <= val_utc.year <= 9999):
            raise ValueError("Год должен состоять ровно из четырёх цифр")
        now = utcnow()
        if val_utc <= now:
            raise ValueError("Время отправки не может быть в прошлом")
        if val_utc > now + timedelta(days=30):
            raise ValueError("Время отправки не может быть позже, чем через 30 дней")
        return val_utc


ImagePurpose = Literal["promotion", "logo"]


class ImageUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    width: int
    height: int
    bytes: int


def _validate_map_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("map_url must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 1024:
        raise ValueError("map_url is too long (max 1024 characters)")
    lower = normalized.lower()
    if lower.startswith(("javascript:", "data:")):
        raise ValueError("map_url scheme is forbidden")
    try:
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
    except ValueError:
        raise ValueError("map_url must be a valid HTTPS URL") from None
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(ord(c) < 32 for c in normalized)
    ):
        raise ValueError("map_url must be a valid HTTPS URL with a valid host")
    return normalized


class BusinessStoreAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    title_ru: str
    title_kk: str
    address_ru: str
    address_kk: str
    map_url: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    latitude: float | None = None
    longitude: float | None = None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _convert_float(cls, v: Any) -> float | None:
        if v is None:
            return None
        return float(v)


class BusinessStoreCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ru: str = Field(min_length=1, max_length=160)
    title_kk: str = Field(min_length=1, max_length=160)
    address_ru: str = Field(min_length=1, max_length=255)
    address_kk: str = Field(min_length=1, max_length=255)
    map_url: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=-1000, le=1000)
    is_active: bool = True
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)

    _title_ru = field_validator("title_ru", mode="before")(_strip_required)
    _title_kk = field_validator("title_kk", mode="before")(_strip_required)
    _address_ru = field_validator("address_ru", mode="before")(_strip_required)
    _address_kk = field_validator("address_kk", mode="before")(_strip_required)
    _map_url = field_validator("map_url", mode="before")(_validate_map_url)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> "BusinessStoreCreateRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must either both be provided or both be null")
        return self


class BusinessStoreUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ru: str | None = Field(default=None, min_length=1, max_length=160)
    title_kk: str | None = Field(default=None, min_length=1, max_length=160)
    address_ru: str | None = Field(default=None, min_length=1, max_length=255)
    address_kk: str | None = Field(default=None, min_length=1, max_length=255)
    map_url: str | None = Field(default=None, max_length=1024)
    sort_order: int | None = Field(default=None, ge=-1000, le=1000)
    is_active: bool | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)

    _title_ru = field_validator("title_ru", mode="before")(_strip_required)
    _title_kk = field_validator("title_kk", mode="before")(_strip_required)
    _address_ru = field_validator("address_ru", mode="before")(_strip_required)
    _address_kk = field_validator("address_kk", mode="before")(_strip_required)
    _map_url = field_validator("map_url", mode="before")(_validate_map_url)

    @model_validator(mode="after")
    def require_fields(self) -> "BusinessStoreUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        for required in ("title_ru", "title_kk", "address_ru", "address_kk", "sort_order", "is_active"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null")
        return self


class StoreCoordinateCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str
    latitude: float
    longitude: float


class StoreResolveCoordinatesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=1024)
    url: str | None = Field(default=None, max_length=1024)
    address: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def validate_has_query(self) -> "StoreResolveCoordinatesRequest":
        q = (self.query or "").strip()
        u = (self.url or "").strip()
        a = (self.address or "").strip()
        if not (q or u or a):
            raise ValueError("Необходимо указать ссылку 2ГИС или адрес магазина")
        return self


class StoreResolveCoordinatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["found", "ambiguous", "not_found", "error"]
    message: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    resolved_address: str | None = None
    candidates: list[StoreCoordinateCandidate] = Field(default_factory=list)


def _clean_localized_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > 2000:
            raise ValueError("text cannot exceed 2000 characters")
        return stripped
    return str(value)


class LocalizedAppText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ru: str | None = Field(default=None, max_length=2000)
    kk: str | None = Field(default=None, max_length=2000)

    _clean_ru = field_validator("ru", mode="before")(_clean_localized_text)
    _clean_kk = field_validator("kk", mode="before")(_clean_localized_text)


class AppTextsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_text: LocalizedAppText = Field(default_factory=LocalizedAppText)
    home_store_note_lead: LocalizedAppText = Field(default_factory=LocalizedAppText)
    balance_delay_note: LocalizedAppText = Field(default_factory=LocalizedAppText)


class AppTextsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_text: LocalizedAppText | None = None
    home_store_note_lead: LocalizedAppText | None = None
    balance_delay_note: LocalizedAppText | None = None


class SplashMediaUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    media_type: Literal["image", "video"]
    width: int
    height: int
    duration_seconds: float | None = None
    bytes: int


class BusinessSplashConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    enabled: bool = False
    media_type: Literal["image", "video"] | None = None
    media_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    file_size: int | None = None
    version: str | None = None

class BusinessSplashConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool
    media_url: str | None = Field(default=None, max_length=1024)
    media_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    file_size: int | None = None

    @model_validator(mode="after")
    def validate_splash_config(self) -> "BusinessSplashConfigUpdateRequest":
        if self.enabled and not self.media_url:
            raise ValueError("media_url is required when enabled is true")
        return self


class PublicSplashResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID | None = None
    enabled: bool = False
    media_type: Literal["image", "video"] | None = None
    media_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    file_size: int | None = None
    version: str | None = None


class BusinessLoyaltyTierAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    level: int
    priority: int
    name_ru: str
    name_kk: str
    description_ru: str | None = None
    description_kk: str | None = None
    image_url: str | None = None
    turnover_period_months: int
    min_turnover: Decimal
    max_turnover: Decimal | None = None
    percent: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessLoyaltyTierCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1, le=100)
    priority: int | None = Field(default=None, ge=1, le=1000)
    name_ru: str = Field(min_length=1, max_length=120)
    name_kk: str = Field(min_length=1, max_length=120)
    description_ru: str | None = Field(default=None, max_length=2000)
    description_kk: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=1024)
    # Lifetime turnover: the period is no longer a business rule. Optional for compatibility with old clients;
    # when given it is stored as a historical value and is never used in any calculation.
    turnover_period_months: int | None = Field(default=None, ge=1, le=36)
    # Numeric(14,2) / Numeric(5,2): a value that does not fit is refused, never rounded or cut in silence.
    min_turnover: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    max_turnover: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    is_active: bool = True

    _name_ru = field_validator("name_ru", mode="before")(_strip_required)
    _name_kk = field_validator("name_kk", mode="before")(_strip_required)
    _desc_ru = field_validator("description_ru", mode="before")(_strip_optional)
    _desc_kk = field_validator("description_kk", mode="before")(_strip_optional)
    _numbers = field_validator(
        "level", "priority", "turnover_period_months", "min_turnover", "max_turnover", "percent", mode="before"
    )(_reject_bool)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BusinessLoyaltyTierCreateRequest":
        if "turnover_period_months" in self.model_fields_set and self.turnover_period_months is None:
            raise ValueError("turnover_period_months must be omitted or a number, not null")
        if self.max_turnover is not None and self.max_turnover <= self.min_turnover:
            raise ValueError("max_turnover must be greater than min_turnover")
        return self


class BusinessLoyaltyTierUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int | None = Field(default=None, ge=1, le=100)
    priority: int | None = Field(default=None, ge=1, le=1000)
    name_ru: str | None = Field(default=None, min_length=1, max_length=120)
    name_kk: str | None = Field(default=None, min_length=1, max_length=120)
    description_ru: str | None = Field(default=None, max_length=2000)
    description_kk: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=1024)
    turnover_period_months: int | None = Field(default=None, ge=1, le=36)
    min_turnover: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    max_turnover: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    is_active: bool | None = None

    _name_ru = field_validator("name_ru", mode="before")(_strip_required)
    _name_kk = field_validator("name_kk", mode="before")(_strip_required)
    _desc_ru = field_validator("description_ru", mode="before")(_strip_optional)
    _desc_kk = field_validator("description_kk", mode="before")(_strip_optional)
    _numbers = field_validator(
        "level", "priority", "turnover_period_months", "min_turnover", "max_turnover", "percent", mode="before"
    )(_reject_bool)

    @model_validator(mode="after")
    def require_fields(self) -> "BusinessLoyaltyTierUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        for required in ("level", "name_ru", "name_kk", "turnover_period_months", "min_turnover", "percent", "is_active"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null")
        return self


class LoyaltyScaleTierRequest(BaseModel):
    """One existing tier row inside an atomic scale save.

    `id`, `min_turnover`, `max_turnover` (explicit null = no upper bound) and `percent` are mandatory so
    the request always states the final financial values of every row. Optional text/image/activity
    fields are left untouched when omitted. `level`, `priority` and the legacy period are not editable
    here (unknown fields are refused), which removes unique-constraint swaps and keeps ordering stable.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    min_turnover: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    max_turnover: Decimal | None = Field(ge=0, max_digits=14, decimal_places=2)
    percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    name_ru: str | None = Field(default=None, min_length=1, max_length=120)
    name_kk: str | None = Field(default=None, min_length=1, max_length=120)
    description_ru: str | None = Field(default=None, max_length=2000)
    description_kk: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=1024)
    is_active: bool | None = None

    _name_ru = field_validator("name_ru", mode="before")(_strip_required)
    _name_kk = field_validator("name_kk", mode="before")(_strip_required)
    _desc_ru = field_validator("description_ru", mode="before")(_strip_optional)
    _desc_kk = field_validator("description_kk", mode="before")(_strip_optional)
    _numbers = field_validator("min_turnover", "max_turnover", "percent", mode="before")(_reject_bool)

    @model_validator(mode="after")
    def no_null_required_text(self) -> "LoyaltyScaleTierRequest":
        for required in ("name_ru", "name_kk", "is_active"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null")
        return self


class LoyaltyScaleSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    tiers: list[LoyaltyScaleTierRequest] = Field(min_length=1, max_length=100)


class LoyaltyScaleResponse(BaseModel):
    business_id: uuid.UUID
    version: int
    tiers: list[BusinessLoyaltyTierAdminItem]


class LoyaltyScaleSaveResponse(LoyaltyScaleResponse):
    changed: bool
