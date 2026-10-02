"""Atomic, audited administrative mutations for TASK-011B."""

import re
import uuid
from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope, scope_for_admin
from app.core.errors import AppError
from app.core.time import utcnow
from app.models.admin import AdminUser, AgentCommand
from app.models.entities import Agent, AuditLog, Business, Card, UserCard
from app.schemas.admin import BusinessCreateRequest, BusinessUpdateRequest
from app.services.agent_auth import issue_agent_key, revoke_agent, rotate_agent_key

_SENSITIVE_AUDIT_KEY = re.compile(
    r"(?:password|passwd|token|secret|jwt|otp|wappi|key_hash|agent.?key|api.?key|phone|barcode|full.?name)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:\bagk_[A-Za-z0-9_-]+|\brfr_[A-Za-z0-9_-]+|\badm_rfr_[A-Za-z0-9_-]+|"
    r"\bBearer\s+[A-Za-z0-9._-]+|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


def _is_sensitive_audit_key(key: str) -> bool:
    # Business barcode prefixes are configured routing data; card barcodes are never audited.
    return key.lower() != "barcode_prefixes" and _SENSITIVE_AUDIT_KEY.search(key) is not None


def _redact_url_query(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme == "https" and (parsed.query or parsed.fragment):
        query = "[REDACTED]" if parsed.query else ""
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    return value


def sanitize_admin_audit_state(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return cast(dict[str, Any], _safe_audit_value(value))


def _safe_audit_value(value: Any, *, key: str = "") -> Any:
    if _is_sensitive_audit_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(child_key): _safe_audit_value(child, key=str(child_key))
            for child_key, child in value.items()
            if not _is_sensitive_audit_key(str(child_key))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_audit_value(child) for child in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[REDACTED]", _redact_url_query(value))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _audit(
    db: AsyncSession,
    actor: AdminUser,
    business_id: uuid.UUID | None,
    action: str,
    entity: str,
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any] | None,
) -> None:
    db.add(
        AuditLog(
            actor=actor.login,
            admin_user_id=actor.id,
            business_id=business_id,
            action=action,
            entity=entity,
            before_state=sanitize_admin_audit_state(before_state),
            after_state=sanitize_admin_audit_state(after_state),
        )
    )


def _business_state(
    business: Business, *, colors_changed: bool | None = None
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "name": business.name,
        "logo_url": business.logo_url,
        "colors": None if business.colors is None else {
            "configured": True,
            "keys": sorted(
                key for key in business.colors if not _is_sensitive_audit_key(key)
            ),
        },
        "barcode_prefixes": business.barcode_prefixes,
        "status": business.status,
    }
    if colors_changed is not None:
        state["colors_changed"] = colors_changed
    return state


async def create_business(
    db: AsyncSession, actor: AdminUser, request: BusinessCreateRequest
) -> Business:
    actor_scope = scope_for_admin(actor)
    actor_scope.require_superadmin()
    business = Business(**request.model_dump())
    db.add(business)
    await db.flush()
    _audit(
        db,
        actor,
        business.id,
        "business_created",
        "business",
        None,
        _business_state(business, colors_changed=business.colors is not None),
    )
    await db.commit()
    await db.refresh(business)
    return business


async def update_business(
    db: AsyncSession,
    actor: AdminUser,
    business_id: uuid.UUID,
    request: BusinessUpdateRequest,
) -> Business:
    actor_scope = scope_for_admin(actor)
    actor_scope.require_superadmin()
    business = await db.scalar(
        select(Business).where(Business.id == business_id).with_for_update()
    )
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    before = _business_state(business)
    fields = request.model_dump(exclude_unset=True)
    previous_colors = business.colors
    for field, value in fields.items():
        setattr(business, field, value)
    await db.flush()
    _audit(
        db,
        actor,
        business.id,
        "business_updated",
        "business",
        before,
        _business_state(
            business,
            colors_changed="colors" in fields and previous_colors != business.colors,
        ),
    )
    await db.commit()
    await db.refresh(business)
    return business


async def create_agent(
    db: AsyncSession, actor: AdminUser, business_id: uuid.UUID
) -> tuple[Agent, str]:
    scope_for_admin(actor).require_superadmin()
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    agent, raw_key = await issue_agent_key(db, business_id)
    _audit(
        db,
        actor,
        business_id,
        "agent_created",
        "agent",
        None,
        {"agent_id": agent.id, "business_id": business_id, "status": agent.status},
    )
    await db.commit()
    await db.refresh(agent)
    return agent, raw_key


async def rotate_agent_api_key(
    db: AsyncSession, actor: AdminUser, agent_id: uuid.UUID
) -> tuple[Agent, str]:
    scope_for_admin(actor).require_superadmin()
    agent = await db.scalar(select(Agent).where(Agent.id == agent_id).with_for_update())
    if agent is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    if agent.status != "active":
        raise AppError("ADMIN_AGENT_REVOKED", "Only an active agent can rotate its key", 409)
    raw_key = await rotate_agent_key(db, agent)
    rotated_at = utcnow()
    _audit(
        db,
        actor,
        agent.business_id,
        "agent_key_rotated",
        "agent",
        {"agent_id": agent.id, "business_id": agent.business_id},
        {
            "agent_id": agent.id,
            "business_id": agent.business_id,
            "key_rotated": True,
            "rotated_at": rotated_at.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(agent)
    return agent, raw_key


async def revoke_agent_access(
    db: AsyncSession, actor: AdminUser, agent_id: uuid.UUID
) -> tuple[Agent, bool]:
    scope_for_admin(actor).require_superadmin()
    agent = await db.scalar(select(Agent).where(Agent.id == agent_id).with_for_update())
    if agent is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    if agent.status == "revoked":
        return agent, False
    before = {"agent_id": agent.id, "business_id": agent.business_id, "status": agent.status}
    await revoke_agent(db, agent)
    _audit(
        db,
        actor,
        agent.business_id,
        "agent_revoked",
        "agent",
        before,
        {"agent_id": agent.id, "business_id": agent.business_id, "status": agent.status},
    )
    await db.commit()
    await db.refresh(agent)
    return agent, True


async def request_full_resync(
    db: AsyncSession, actor: AdminUser, agent_id: uuid.UUID
) -> tuple[AgentCommand, bool]:
    scope_for_admin(actor).require_superadmin()
    agent = await db.scalar(select(Agent).where(Agent.id == agent_id).with_for_update())
    if agent is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    if agent.status != "active":
        raise AppError("ADMIN_AGENT_REVOKED", "Only an active agent can receive a resync request", 409)
    current = await db.scalar(
        select(AgentCommand)
        .where(
            AgentCommand.agent_id == agent.id,
            AgentCommand.command_type == "full_resync",
            AgentCommand.status.in_(("pending", "running")),
        )
        .order_by(AgentCommand.created_at.desc(), AgentCommand.id.desc())
        .limit(1)
    )
    if current is not None:
        return current, False

    command = AgentCommand(
        agent_id=agent.id,
        business_id=agent.business_id,
        created_by_admin_id=actor.id,
        command_type="full_resync",
        status="pending",
    )
    try:
        db.add(command)
        await db.flush()
        _audit(
            db,
            actor,
            agent.business_id,
            "agent_full_resync_requested",
            "agent_command",
            None,
            {"command_id": command.id, "agent_id": agent.id, "business_id": agent.business_id},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        current = await db.scalar(
            select(AgentCommand)
            .where(
                AgentCommand.agent_id == agent_id,
                AgentCommand.command_type == "full_resync",
                AgentCommand.status.in_(("pending", "running")),
            )
            .order_by(AgentCommand.created_at.desc(), AgentCommand.id.desc())
            .limit(1)
        )
        if current is not None:
            return current, False
        raise
    await db.refresh(command)
    return command, True


async def unbind_card(
    db: AsyncSession, actor: AdminUser, scope: AdminScope, card_id: uuid.UUID
) -> str:
    card = await db.scalar(
        select(Card)
        .where(Card.id == card_id, scope.predicate(Card.business_id))
        .with_for_update()
    )
    if card is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    binding = await db.scalar(
        select(UserCard).where(UserCard.card_id == card.id).with_for_update()
    )
    if binding is None:
        return "already_unbound"

    before_state = {
        "card_id": card.id,
        "business_id": card.business_id,
        "user_id": binding.user_id,
    }
    user_id = binding.user_id
    await db.delete(binding)
    await db.flush()
    _audit(
        db,
        actor,
        card.business_id,
        "card_unbound",
        "card",
        before_state,
        {"card_id": card.id, "business_id": card.business_id, "user_id": user_id, "unbound": True},
    )
    await db.commit()
    return "unbound"
