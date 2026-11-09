"""Admin schemas for customer app content: promotions, notifications, stores, and app texts."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import as_utc, utcnow
from app.schemas.admin import _validate_logo_url

PromotionKind = Literal["banner", "offer"]


def _strip_optional(value: object) -> object:
    if isinstance(value, str):
        return value.strip() or None
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
        if val_utc < now - timedelta(minutes=5):
            raise ValueError("starts_at cannot be in the past")
        return value


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
        now = utcnow()
        val_utc = (
            value.astimezone(UTC)
            if value.tzinfo is not None
            else value.replace(tzinfo=UTC)
        )
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


class BusinessStoreCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ru: str = Field(min_length=1, max_length=160)
    title_kk: str = Field(min_length=1, max_length=160)
    address_ru: str = Field(min_length=1, max_length=255)
    address_kk: str = Field(min_length=1, max_length=255)
    map_url: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=-1000, le=1000)
    is_active: bool = True

    _title_ru = field_validator("title_ru", mode="before")(_strip_required)
    _title_kk = field_validator("title_kk", mode="before")(_strip_required)
    _address_ru = field_validator("address_ru", mode="before")(_strip_required)
    _address_kk = field_validator("address_kk", mode="before")(_strip_required)
    _map_url = field_validator("map_url", mode="before")(_validate_map_url)


class BusinessStoreUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_ru: str | None = Field(default=None, min_length=1, max_length=160)
    title_kk: str | None = Field(default=None, min_length=1, max_length=160)
    address_ru: str | None = Field(default=None, min_length=1, max_length=255)
    address_kk: str | None = Field(default=None, min_length=1, max_length=255)
    map_url: str | None = Field(default=None, max_length=1024)
    sort_order: int | None = Field(default=None, ge=-1000, le=1000)
    is_active: bool | None = None

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
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    media_type: Literal["image", "video"] | None = None
    media_url: str | None = Field(default=None, max_length=1024)
    width: int | None = Field(default=None, ge=1, le=8192)
    height: int | None = Field(default=None, ge=1, le=8192)
    duration_seconds: float | None = Field(default=None, ge=0.1, le=5.0)
    file_size: int | None = Field(default=None, ge=1, le=15_728_640)

    @model_validator(mode="after")
    def validate_splash_config(self) -> "BusinessSplashConfigUpdateRequest":
        if self.enabled:
            if not self.media_type:
                raise ValueError("media_type is required when enabled is true")
            if not self.media_url:
                raise ValueError("media_url is required when enabled is true")
            if self.media_type == "video" and (self.duration_seconds is None or self.duration_seconds > 5.0):
                raise ValueError("duration_seconds must be between 0.1 and 5.0 for video splash")
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

