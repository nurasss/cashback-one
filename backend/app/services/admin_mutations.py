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
    r"(?:password|passwd|pwd|token|secret|jwt|otp|wappi|key_hash|agent.?key|api.?key|"
    r"phone|barcode(?!_prefixes)|full.?name|credential|database_url|connection_string|"
    r"connection_password|authorization|cookie|signing_key|private_key)",
    re.IGNORECASE,
)
_CONTAINS_CREDENTIALS = re.compile(
    r"(?:password|pwd|secret|token)\s*=|"
    r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s:@]+@",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:\bagk_[A-Za-z0-9_-]+|\brfr_[A-Za-z0-9_-]+|\badm_rfr_[A-Za-z0-9_-]+|"
    r"\bBearer\s+[A-Za-z0-9._-]+|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)

_KNOWN_ADMIN_ACTIONS: set[str] = {
    "business_created",
    "business_updated",
    "agent_created",
    "agent_key_rotated",
    "agent_revoked",
    "agent_full_resync_requested",
    "card_unbound",
    "promotion_created",
    "promotion_updated",
    "promotion_deleted",
    "notification_created",
    "notification_deleted",
}

_ALLOWED_BUSINESS_STATUSES: set[str] = {"active", "inactive"}
_ALLOWED_AGENT_STATUSES: set[str] = {"active", "revoked", "suspended", "inactive"}
_ALLOWED_COMMAND_STATUSES: set[str] = {"pending", "processing", "completed", "failed"}
_ALLOWED_BUSINESS_FIELDS: set[str] = {
    "barcode_prefixes",
    "colors",
    "loyalty_tiers",
    "logo_url",
    "name",
    "status",
}


def _is_sensitive_audit_key(key: str) -> bool:
    normalized = key.strip().lower()
    # Business barcode prefixes are configured routing data; card barcodes are never audited.
    if normalized == "barcode_prefixes":
        return False
    return _SENSITIVE_AUDIT_KEY.search(normalized) is not None


def _redact_url_query(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme == "https" and (parsed.query or parsed.fragment):
        query = "[REDACTED]" if parsed.query else ""
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    return value


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
        redacted = _redact_url_query(value)
        if _CONTAINS_CREDENTIALS.search(redacted):
            return "[REDACTED]"
        return _SECRET_VALUE.sub("[REDACTED]", redacted)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _clean_str(val: Any, *, max_length: int = 255) -> str | None:
    if not isinstance(val, str):
        return None
    trimmed = val.strip()
    if not trimmed or len(trimmed) > max_length:
        return None
    cleaned = _safe_audit_value(trimmed)
    if not isinstance(cleaned, str):
        return None
    return cleaned


def _clean_uuid_str(val: Any) -> str | None:
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, str):
        try:
            return str(uuid.UUID(val))
        except (ValueError, TypeError, AttributeError):
            return None
    return None


def _clean_url(val: Any) -> str | None:
    if val is None:
        return None
    if not isinstance(val, str):
        return None
    if len(val) > 1024:
        return None
    redacted = _redact_url_query(val)
    if _CONTAINS_CREDENTIALS.search(redacted):
        return "[REDACTED]"
    return redacted


def _clean_barcode_prefixes(val: Any) -> list[str] | None:
    if val is None:
        return None
    if not isinstance(val, list):
        return None
    if len(val) > 64:
        return None
    cleaned_prefixes: list[str] = []
    for item in val:
        if not isinstance(item, str):
            return None
        trimmed = item.strip()
        if not trimmed or len(trimmed) > 32:
            return None
        cleaned_prefixes.append(trimmed)
    return cleaned_prefixes


def _clean_colors(val: Any) -> dict[str, Any] | None:
    if val is None or not isinstance(val, Mapping) or not val:
        return None

    # Safe metadata shape: {"configured": bool}
    if "configured" in val and isinstance(val.get("configured"), bool):
        return {"configured": val["configured"]}

    # Safe conversion from historical or raw colors mapping:
    # Colors were configured, but free-form keys and values are stripped fail-closed.
    return {"configured": True}


def _project_action_snapshot(action: str, value: Mapping[str, Any]) -> dict[str, Any] | None:
    projected: dict[str, Any] = {}

    if action in ("business_created", "business_updated"):
        for k, v in value.items():
            if k in ("id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
                    projected["business_id"] = cid
            elif k == "status":
                if isinstance(v, str) and v in _ALLOWED_BUSINESS_STATUSES:
                    projected["status"] = v
            elif k == "colors":
                colors_meta = _clean_colors(v)
                if colors_meta is not None:
                    projected["colors"] = colors_meta
            elif k == "colors_changed":
                if isinstance(v, bool):
                    projected["colors_changed"] = v
            elif k == "configured_fields":
                if isinstance(v, (list, tuple)):
                    safe_fields = sorted(
                        f for f in v if isinstance(f, str) and f in _ALLOWED_BUSINESS_FIELDS
                    )
                    if safe_fields:
                        projected["configured_fields"] = safe_fields
            elif k == "changed_fields":
                if isinstance(v, (list, tuple)):
                    safe_fields = sorted(
                        f for f in v if isinstance(f, str) and f in _ALLOWED_BUSINESS_FIELDS
                    )
                    if safe_fields:
                        projected["changed_fields"] = safe_fields

        # Historical compatibility: If neither configured_fields nor changed_fields was present
        # in the raw snapshot, safely derive the category list from recognized safe keys present.
        if action == "business_created" and "configured_fields" not in projected:
            derived_configured: list[str] = []
            if "name" in value and isinstance(value["name"], str):
                derived_configured.append("name")
            if "logo_url" in value and isinstance(value["logo_url"], str):
                derived_configured.append("logo_url")
            if "colors" in value and isinstance(value["colors"], Mapping) and value["colors"]:
                derived_configured.append("colors")
            if (
                "barcode_prefixes" in value
                and isinstance(value["barcode_prefixes"], list)
                and all(isinstance(x, str) for x in value["barcode_prefixes"])
            ):
                derived_configured.append("barcode_prefixes")
            if (
                "status" in value
                and isinstance(value["status"], str)
                and value["status"] in _ALLOWED_BUSINESS_STATUSES
            ):
                derived_configured.append("status")
            if derived_configured:
                projected["configured_fields"] = sorted(derived_configured)

        if action == "business_updated" and "changed_fields" not in projected:
            derived_changed: list[str] = []
            if "name" in value and isinstance(value["name"], str):
                derived_changed.append("name")
            if "logo_url" in value and isinstance(value["logo_url"], str):
                derived_changed.append("logo_url")
            if "colors" in value and (
                (isinstance(value["colors"], Mapping) and bool(value["colors"]))
                or bool(value.get("colors_changed"))
            ):
                derived_changed.append("colors")
            if (
                "barcode_prefixes" in value
                and isinstance(value["barcode_prefixes"], list)
                and all(isinstance(x, str) for x in value["barcode_prefixes"])
            ):
                derived_changed.append("barcode_prefixes")
            if (
                "status" in value
                and isinstance(value["status"], str)
                and value["status"] in _ALLOWED_BUSINESS_STATUSES
            ):
                derived_changed.append("status")
            if derived_changed:
                projected["changed_fields"] = sorted(derived_changed)

    elif action == "agent_created":
        for k, v in value.items():
            if k in ("agent_id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "status":
                if isinstance(v, str) and v in _ALLOWED_AGENT_STATUSES:
                    projected["status"] = v

    elif action == "agent_key_rotated":
        for k, v in value.items():
            if k in ("agent_id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "key_rotated":
                if isinstance(v, bool):
                    projected["key_rotated"] = v
            elif k == "rotated_at":
                crot = _clean_str(v, max_length=64)
                if crot:
                    projected["rotated_at"] = crot

    elif action == "agent_revoked":
        for k, v in value.items():
            if k in ("agent_id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "status":
                if isinstance(v, str) and v in _ALLOWED_AGENT_STATUSES:
                    projected["status"] = v

    elif action == "agent_full_resync_requested":
        for k, v in value.items():
            if k in ("command_id", "agent_id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "status":
                if isinstance(v, str) and v in _ALLOWED_COMMAND_STATUSES:
                    projected["status"] = v

    elif action == "card_unbound":
        for k, v in value.items():
            if k in ("card_id", "business_id", "user_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "unbound":
                if isinstance(v, bool):
                    projected["unbound"] = v

    elif action in (
        "promotion_created",
        "promotion_updated",
        "promotion_deleted",
        "notification_created",
        "notification_deleted",
    ):
        for k, v in value.items():
            if k in ("promotion_id", "notification_id", "business_id"):
                cid = _clean_uuid_str(v)
                if cid:
                    projected[k] = cid
            elif k in ("is_active", "targeted_user"):
                if isinstance(v, bool):
                    projected[k] = v
            elif k == "kind":
                if isinstance(v, str) and v in ("banner", "offer", "info"):
                    projected[k] = v

    if not projected:
        return None
    return projected


def safe_audit_snapshot(
    action: str | None,
    value: Mapping[str, Any] | None,
    *,
    admin_user_id: uuid.UUID | str | None = None,
    business_id: uuid.UUID | str | None = None,
) -> dict[str, Any] | None:
    """Fail-closed audit state sanitizer and strict safe projector.

    Requires verified Admin structural provenance:
    - admin_user_id != None
    - business_id != None (all 7 Admin mutation actions are tenant-scoped)

    Legacy and unknown events project to None to prevent disclosure of arbitrary
    or historical secrets. Known Admin mutation actions project only explicitly
    allowlisted safe shapes and scalar types, dropping any malformed or unexpected nested fields.
    """
    if value is None or not isinstance(value, Mapping):
        return None
    if not action or action not in _KNOWN_ADMIN_ACTIONS:
        return None
    if admin_user_id is None or business_id is None:
        return None

    return _project_action_snapshot(action, value)


def sanitize_admin_audit_state(
    value: Mapping[str, Any] | None,
    *,
    action: str | None = None,
    admin_user_id: uuid.UUID | str | None = None,
    business_id: uuid.UUID | str | None = None,
) -> dict[str, Any] | None:
    if value is None or not isinstance(value, Mapping):
        return None
    if action is not None:
        return safe_audit_snapshot(
            action,
            value,
            admin_user_id=admin_user_id,
            business_id=business_id,
        )
    return cast(dict[str, Any], _safe_audit_value(value))


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
            before_state=safe_audit_snapshot(
                action,
                before_state,
                admin_user_id=actor.id,
                business_id=business_id,
            ),
            after_state=safe_audit_snapshot(
                action,
                after_state,
                admin_user_id=actor.id,
                business_id=business_id,
            ),
        )
    )


def _business_state(
    business: Business,
    *,
    changed_fields: list[str] | None = None,
    colors_changed: bool | None = None,
) -> dict[str, Any]:
    configured = sorted(
        field
        for field in ("barcode_prefixes", "colors", "loyalty_tiers", "logo_url", "name", "status")
        if getattr(business, field, None) is not None
    )
    state: dict[str, Any] = {
        "business_id": str(business.id),
        "status": business.status if business.status in _ALLOWED_BUSINESS_STATUSES else None,
    }
    if changed_fields is not None:
        state["changed_fields"] = sorted(
            f for f in changed_fields if f in _ALLOWED_BUSINESS_FIELDS
        )
    else:
        state["configured_fields"] = configured
    if colors_changed is not None:
        state["colors_changed"] = colors_changed
    if business.colors is not None:
        state["colors"] = {"configured": True}
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
        _business_state(business),
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
    fields = request.model_dump(mode="json", exclude_unset=True)
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
            changed_fields=list(fields.keys()),
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
