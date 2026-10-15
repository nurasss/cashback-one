"""Customer app schemas: profile, promotions, notifications, badges, dynamic QR."""
import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import utcnow

Gender = Literal["male", "female"]
Language = Literal["ru", "kz"]

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def iin_is_valid(iin: str) -> bool:
    """Kazakhstan IIN: 12 digits with a mod-11 check digit (two weight passes)."""
    if not re.fullmatch(r"\d{12}", iin):
        return False
    digits = [int(c) for c in iin]
    for weights in (range(1, 12), [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]):
        control = sum(d * w for d, w in zip(digits[:11], weights, strict=True)) % 11
        if control != 10:
            return control == digits[11]
    return False


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phone: str | None
    language: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    gender: str | None = None
    city: str | None = None
    address: str | None = None
    birth_date: date | None = None
    iin: str | None = None
    company: str | None = None


class ProfileUpdateRequest(BaseModel):
    """Partial update: only fields present in the payload are changed; null/"" clears a field."""

    model_config = ConfigDict(extra="forbid")

    language: Language | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    gender: Gender | None = None
    city: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    birth_date: date | None = None
    iin: str | None = Field(default=None, max_length=12)
    company: str | None = Field(default=None, max_length=255)

    _strip = field_validator(
        "first_name", "last_name", "email", "city", "address", "iin", "company", "gender",
        mode="before",
    )(_blank_to_none)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _EMAIL.fullmatch(value):
            raise ValueError("Invalid e-mail address")
        return value.lower()

    @field_validator("iin")
    @classmethod
    def validate_iin(cls, value: str | None) -> str | None:
        if value is not None and not iin_is_valid(value):
            raise ValueError("IIN must be 12 digits with a valid check digit")
        return value

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        if value > utcnow().date() or value.year < 1900:
            raise ValueError("Birth date is out of range")
        return value


class PromotionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID | None
    kind: str
    title: str
    subtitle: str | None = None
    badge: str | None = None
    body: str | None = None
    image_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_new: bool = False


class PromotionsResponse(BaseModel):
    banners: list[PromotionItem]
    offers: list[PromotionItem]
    has_new: bool


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str
    created_at: datetime
    is_unread: bool = False


class NotificationsResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int


class BadgesResponse(BaseModel):
    promotions_new: bool
    notifications_unread: int


class CardQrResponse(BaseModel):
    token: str
    expires_at: datetime
    ttl_seconds: int
