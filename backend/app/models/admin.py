import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base, UUIDPrimaryKey


class AdminUser(Base, UUIDPrimaryKey):
    """Administrator identity, separate from mobile customer accounts."""

    __tablename__ = "admin_users"
    __table_args__ = (
        UniqueConstraint("login", name="uq_admin_users_login"),
        CheckConstraint(
            "length(login) BETWEEN 3 AND 128 AND login = lower(trim(login))",
            name="ck_admin_users_normalized_login",
        ),
        CheckConstraint("role IN ('superadmin', 'business_manager')", name="ck_admin_users_role"),
        CheckConstraint(
            "(role = 'superadmin' AND business_id IS NULL) OR "
            "(role = 'business_manager' AND business_id IS NOT NULL)",
            name="ck_admin_users_role_business",
        ),
        Index("ix_admin_users_business_id", "business_id"),
    )

    login: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AdminSession(Base, UUIDPrimaryKey):
    """Opaque refresh-token session for an administrator browser."""

    __tablename__ = "admin_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_admin_sessions_refresh_token_hash"),
        Index("ix_admin_sessions_admin_user_id", "admin_user_id"),
        Index("ix_admin_sessions_expires_at", "expires_at"),
    )

    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
