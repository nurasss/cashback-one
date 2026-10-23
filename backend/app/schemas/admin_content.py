"""Admin schemas for customer app content: promotions and notifications."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class PromotionCreateRequest(_PromotionFields):
    business_id: uuid.UUID | None = None
    kind: PromotionKind = "offer"
    title: str = Field(min_length=1, max_length=120)

    _title = field_validator("title", mode="before")(_strip_required)


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


class NotificationAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID | None
    user_id: uuid.UUID | None
    kind: str
    title: str
    body: str
    created_at: datetime


class NotificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)

    _text = field_validator("title", "body", mode="before")(_strip_required)


ImagePurpose = Literal["promotion", "logo"]


class ImageUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    width: int
    height: int
    bytes: int

