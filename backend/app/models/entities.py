import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Business(Base, UUIDPrimaryKey, Timestamps):
    """Client organization (tenant) operating on POSCENTER ONE."""

    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    colors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    barcode_prefixes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Agent(Base, UUIDPrimaryKey):
    """Synchronization agent instance running as a Windows service at a business site."""

    __tablename__ = "agents"

    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Card(Base, UUIDPrimaryKey):
    """Loyalty/bonus card mirror from POSCENTER ONE."""

    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("business_id", "barcode", name="uq_cards_business_barcode"),
        Index("ix_cards_phone", "phone"),
        Index("ix_cards_updated_at", "updated_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    barcode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0.0000"), nullable=False
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, UUIDPrimaryKey):
    """Mobile app customer account."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_phone", "phone"),)

    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserCard(Base, UUIDPrimaryKey):
    """Binding between a customer and a loyalty card.

    Invariant: A card cannot simultaneously belong to multiple users (UNIQUE on card_id).
    """

    __tablename__ = "user_cards"
    __table_args__ = (
        UniqueConstraint("card_id", name="uq_user_cards_card_id"),
        Index("ix_user_cards_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    bind_method: Mapped[str] = mapped_column(String(32), default="phone_auto", nullable=False)


class Transaction(Base, UUIDPrimaryKey):
    """Bonus movement record mirrored from POSCENTER ONE.

    Invariant: A movement cannot be duplicated for a given card (UNIQUE on card_id, external_id).
    """

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("card_id", "external_id", name="uq_transactions_card_external"),
        Index("ix_transactions_occurred_at", "occurred_at"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    receipt_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class LoginChallenge(Base, UUIDPrimaryKey):
    """One-time challenge code for WhatsApp reverse login flow."""

    __tablename__ = "login_challenges"
    __table_args__ = (
        Index("ix_login_challenges_code_hash", "code_hash"),
        Index("ix_login_challenges_device_id", "device_id"),
        Index("ix_login_challenges_expires_at", "expires_at"),
    )

    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class OtpCode(Base, UUIDPrimaryKey):
    """SMS OTP codes for fallback authentication."""

    __tablename__ = "otp_codes"
    __table_args__ = (
        Index("ix_otp_codes_phone", "phone"),
        Index("ix_otp_codes_expires_at", "expires_at"),
    )

    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Consent(Base, UUIDPrimaryKey):
    """User privacy and personal data processing consents."""

    __tablename__ = "consents"
    __table_args__ = (Index("ix_consents_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    given_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Device(Base, UUIDPrimaryKey):
    """User push notification device registration (Stage 2 infrastructure)."""

    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    push_token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AuditLog(Base, UUIDPrimaryKey):
    """Administrative action audit trail."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_entity", "entity"),
    )

    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
