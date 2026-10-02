import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
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


class AgentCommand(Base, UUIDPrimaryKey):
    """Durable Admin request for work an Agent may execute in a later protocol."""

    __tablename__ = "agent_commands"
    __table_args__ = (
        CheckConstraint(
            "command_type IN ('full_resync')", name="ck_agent_commands_command_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_agent_commands_status",
        ),
        Index(
            "uq_agent_commands_active_full_resync_per_agent",
            "agent_id",
            unique=True,
            postgresql_where=text(
                "command_type = 'full_resync' AND status IN ('pending', 'running')"
            ),
            sqlite_where=text(
                "command_type = 'full_resync' AND status IN ('pending', 'running')"
            ),
        ),
        Index("ix_agent_commands_agent_created_at", "agent_id", "created_at"),
        Index("ix_agent_commands_business_created_at", "business_id", "created_at"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("agents.id", name="fk_agent_commands_agent_id_agents", ondelete="RESTRICT"),
        nullable=False,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", name="fk_agent_commands_business_id_businesses", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("admin_users.id", name="fk_agent_commands_admin_id_admin_users", ondelete="RESTRICT"),
        nullable=False,
    )
    command_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
