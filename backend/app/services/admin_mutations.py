"""Atomic, audited administrative mutations for TASK-011B."""

import math
import re
import uuid
from collections.abc import Mapping
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope, scope_for_admin
from app.core.config import settings
from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.models.admin import AdminSession, AdminUser, AgentCommand
from app.models.entities import Agent, AuditLog, Business, Card, PosKey, UserCard
from app.schemas.admin import (
    BusinessCreateRequest,
    BusinessUpdateRequest,
    ManagerAccessDisclosure,
)
from app.services.admin_security import (
    generate_base_login,
    generate_manager_password,
    hash_admin_password,
    normalize_admin_login,
    random_slug,
)
from app.services.agent_auth import issue_agent_key, revoke_agent, rotate_agent_key
from app.services.media_storage import MediaStorage, maybe_cleanup_old_media_file
from app.services.pos_auth import issue_pos_key, revoke_pos_key

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
    r"(?:\bagk_[A-Za-z0-9_-]+|\bpos_[A-Za-z0-9_-]+|\brfr_[A-Za-z0-9_-]+|\badm_rfr_[A-Za-z0-9_-]+|"
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
    "business_manager_created",
    "business_manager_password_reset",
    "media_uploaded",
    "pos_key_created",
    "pos_key_revoked",
    "loyalty_scale_updated",
    "loyalty_tier_created",
    "loyalty_tier_updated",
    "loyalty_tier_deleted",
    "store_created",
    "store_updated",
    "store_deleted",
    "app_texts_updated",
    "business_splash_updated",
}

# Legacy name of the app-texts event: projected through the same strict whitelist.
_ACTION_ALIASES: dict[str, str] = {"business_app_texts_updated": "app_texts_updated"}

_ALLOWED_BUSINESS_STATUSES: set[str] = {"active", "inactive"}
_ALLOWED_AGENT_STATUSES: set[str] = {"active", "revoked", "suspended", "inactive"}
_ALLOWED_COMMAND_STATUSES: set[str] = {"pending", "processing", "completed", "failed"}
_ALLOWED_BUSINESS_FIELDS: set[str] = {
    "android_app_id",
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


def _redact_audit_text(text: str) -> str:
    """Admin-authored content text kept verbatim, except credential-looking content (fail-closed)."""
    if _CONTAINS_CREDENTIALS.search(text):
        return "[REDACTED]"
    return _SECRET_VALUE.sub("[REDACTED]", text)


def _put_audit_text(out: dict[str, Any], key: str, raw: Any, *, max_length: int) -> None:
    """Project one stored text field of a content event.

    The exact stored string is kept (no strip, no truncation, multi-line preserved). An explicit
    null means "saved as empty"; a key that is absent in the stored snapshot is never added here.
    A non-string or an over-limit value is dropped as unknown, never cut.
    """
    if raw is None:
        out[key] = None
        return
    if not isinstance(raw, str) or len(raw) > max_length:
        return
    out[key] = _redact_audit_text(raw)


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


def _clean_decimal_2(val: Any, *, max_value: Decimal) -> str | None:
    """Existing states hold str(Decimal) (e.g. "2", "100000", "1E+5"); emit a normalized two-decimal string.
    Only finite non-negative values within `max_value` are accepted; everything else is dropped."""
    if not isinstance(val, str) or not val.strip() or len(val) > 40:
        return None
    try:
        number = Decimal(val.strip())
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or number > max_value:
        return None
    return f"{number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


_MONEY_MAX = Decimal("999999999999.99")  # Numeric(14,2)
_PERCENT_MAX = Decimal(100)


def _plain_int(val: Any, lo: int, hi: int) -> int | None:
    if isinstance(val, int) and not isinstance(val, bool) and lo <= val <= hi:
        return val
    return None


_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)

_APP_TEXT_BLOCKS: tuple[str, ...] = (
    "home_text",
    "home_store_note_lead",
    "balance_delay_note",
)
_ALLOWED_APP_TEXT_BLOCKS: set[str] = set(_APP_TEXT_BLOCKS)
_APP_TEXT_VALUE_MAX = 2000  # same limit as LocalizedAppText
_PROMOTION_TEXT_LIMITS: tuple[tuple[str, int], ...] = (
    ("subtitle", 255),
    ("badge", 40),
    ("body", 4000),
)  # same limits as the promotion editor; there is no separate "description" field
_NOTIFICATION_BODY_MAX = 2000  # same limit as NotificationCreateRequest.body
_APP_TEXT_LOCALES: tuple[str, ...] = ("ru", "kk")
_ALLOWED_APP_TEXT_LOCALE_PAIRS: set[str] = {
    f"{block}.{lang}" for block in _APP_TEXT_BLOCKS for lang in _APP_TEXT_LOCALES
}


def _clean_iso_datetime(val: Any) -> str | None:
    if not isinstance(val, str):
        return None
    trimmed = val.strip()
    if not trimmed or len(trimmed) > 64 or not _ISO_DATETIME_RE.fullmatch(trimmed):
        return None
    try:
        parsed = datetime.fromisoformat(trimmed)
        utc_dt = as_utc(parsed)
    except (ValueError, OverflowError):
        return None
    if not (1000 <= parsed.year <= 9999 and 1000 <= utc_dt.year <= 9999):
        return None
    return utc_dt.isoformat()


def _project_promotion_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for id_key in ("promotion_id", "business_id"):
        cid = _clean_uuid_str(value.get(id_key))
        if cid:
            out[id_key] = cid
    if isinstance(value.get("is_active"), bool):
        out["is_active"] = value["is_active"]
    kind = value.get("kind")
    if isinstance(kind, str) and kind in ("banner", "offer", "info"):
        out["kind"] = kind
    title = _clean_str(value.get("title"), max_length=120)
    if title:
        out["title"] = title
    for text_key, text_limit in _PROMOTION_TEXT_LIMITS:
        if text_key in value:
            _put_audit_text(out, text_key, value[text_key], max_length=text_limit)
    sort_order = _plain_int(value.get("sort_order"), -1000, 1000)
    if sort_order is not None:
        out["sort_order"] = sort_order
    for dt_key in ("starts_at", "ends_at"):
        if dt_key not in value:
            continue
        raw_dt = value[dt_key]
        if raw_dt is None:
            out[dt_key] = None
        else:
            cleaned_dt = _clean_iso_datetime(raw_dt)
            if cleaned_dt is not None:
                out[dt_key] = cleaned_dt
    return out


def _project_notification_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for id_key in ("notification_id", "business_id"):
        cid = _clean_uuid_str(value.get(id_key))
        if cid:
            out[id_key] = cid
    if isinstance(value.get("targeted_user"), bool):
        out["targeted_user"] = value["targeted_user"]
    for count_key in ("push_devices", "push_delivered"):
        count = value.get(count_key)
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            out[count_key] = count
    kind = value.get("kind")
    if isinstance(kind, str) and kind in ("banner", "offer", "info"):
        out["kind"] = kind
    # Personal (targeted) messages never expose their texts in the audit.
    if value.get("targeted_user") is not True:
        title = _clean_str(value.get("title"), max_length=120)
        if title:
            out["title"] = title
        if "body" in value:
            _put_audit_text(out, "body", value["body"], max_length=_NOTIFICATION_BODY_MAX)
    for dt_key in ("scheduled_at", "push_sent_at"):
        if dt_key not in value:
            continue
        raw_dt = value[dt_key]
        if raw_dt is None:
            out[dt_key] = None
        else:
            cleaned_dt = _clean_iso_datetime(raw_dt)
            if cleaned_dt is not None:
                out[dt_key] = cleaned_dt
    return out


def _project_app_texts_state(value: Mapping[str, Any]) -> dict[str, Any]:
    """Strict whitelist for app_texts_updated: boolean presence flags, changed identifiers and, for
    changed block/locale pairs only, the stored text values (`texts`). No other keys pass."""
    out: dict[str, Any] = {}
    for block in _APP_TEXT_BLOCKS:
        raw_block = value.get(block)
        if not isinstance(raw_block, Mapping):
            continue
        flags: dict[str, bool] = {}
        for lang in _APP_TEXT_LOCALES:
            flag = raw_block.get(lang)
            if isinstance(flag, bool):
                flags[lang] = flag
        if flags:
            out[block] = flags
    for list_key, allowed in (
        ("configured_fields", _ALLOWED_APP_TEXT_BLOCKS),
        ("changed_fields", _ALLOWED_APP_TEXT_BLOCKS),
        ("changed_locales", _ALLOWED_APP_TEXT_LOCALE_PAIRS),
    ):
        raw_items = value.get(list_key)
        if isinstance(raw_items, (list, tuple)):
            out[list_key] = sorted(
                {item for item in raw_items[:256] if isinstance(item, str) and item in allowed}
            )
    raw_texts = value.get("texts")
    if isinstance(raw_texts, Mapping):
        texts_out: dict[str, dict[str, str | None]] = {}
        for block in _APP_TEXT_BLOCKS:
            raw_block_texts = raw_texts.get(block)
            if not isinstance(raw_block_texts, Mapping):
                continue
            per_lang: dict[str, str | None] = {}
            for lang in _APP_TEXT_LOCALES:
                if lang in raw_block_texts:
                    _put_audit_text(per_lang, lang, raw_block_texts[lang], max_length=_APP_TEXT_VALUE_MAX)
            if per_lang:
                texts_out[block] = per_lang
        if texts_out:
            out["texts"] = texts_out
    return out


_SPLASH_MEDIA_TYPES: set[str] = {"image", "video"}


def _project_splash_state(value: Mapping[str, Any]) -> dict[str, Any]:
    """Strict whitelist for business_splash_updated: flags and technical media metadata only.

    Never passes media_url, file path, version token, raw config or media contents. A value of an
    unexpected type is dropped (fail-closed); a key that is absent stays absent.
    """
    out: dict[str, Any] = {}
    for flag in ("configured", "enabled", "has_media", "media_changed"):
        if isinstance(value.get(flag), bool):
            out[flag] = value[flag]
    if "media_type" in value:
        media_type = value["media_type"]
        if media_type is None:
            out["media_type"] = None
        elif isinstance(media_type, str) and media_type in _SPLASH_MEDIA_TYPES:
            out["media_type"] = media_type
    for dim in ("width", "height"):
        if dim in value:
            if value[dim] is None:
                out[dim] = None
            else:
                clean_dim = _plain_int(value[dim], 0, 100_000)
                if clean_dim is not None:
                    out[dim] = clean_dim
    if "file_size" in value:
        if value["file_size"] is None:
            out["file_size"] = None
        else:
            clean_size = _plain_int(value["file_size"], 0, 2_147_483_647)
            if clean_size is not None:
                out["file_size"] = clean_size
    if "duration_seconds" in value:
        duration = value["duration_seconds"]
        if duration is None:
            out["duration_seconds"] = None
        elif (
            isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and math.isfinite(duration)
            and 0 <= duration <= 86_400
        ):
            out["duration_seconds"] = float(duration)
    return out


def _project_tier_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    """Strict whitelist of an existing loyalty tier state. A key that is absent stays absent;
    an explicit null is kept ONLY for max_turnover (it means "no upper bound")."""
    out: dict[str, Any] = {}
    tid = _clean_uuid_str(value.get("tier_id"))
    if tid:
        out["tier_id"] = tid
    for key, lo, hi in (("level", 1, 100), ("priority", 1, 1000)):
        number = _plain_int(value.get(key), lo, hi)
        if number is not None:
            out[key] = number
    for key in ("name_ru", "name_kk"):
        text = _clean_str(value.get(key), max_length=120)
        if text:
            out[key] = text
    for key in ("min_turnover", "max_turnover", "percent"):
        if key not in value:
            continue
        raw = value[key]
        if raw is None and key == "max_turnover":
            out[key] = None
        else:
            cleaned = _clean_decimal_2(raw, max_value=_PERCENT_MAX if key == "percent" else _MONEY_MAX)
            if cleaned is not None:
                out[key] = cleaned
    if isinstance(value.get("is_active"), bool):
        out["is_active"] = value["is_active"]
    return out


def _project_store_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    """Strict whitelist of an existing store state: public title/address only, no map URL/coordinates."""
    out: dict[str, Any] = {}
    sid = _clean_uuid_str(value.get("store_id"))
    if sid:
        out["store_id"] = sid
    for key, limit in (("title_ru", 160), ("title_kk", 160), ("address_ru", 255), ("address_kk", 255)):
        text = _clean_str(value.get(key), max_length=limit)
        if text:
            out[key] = text
    order = _plain_int(value.get("sort_order"), -1000, 1000)
    if order is not None:
        out["sort_order"] = order
    if isinstance(value.get("is_active"), bool):
        out["is_active"] = value["is_active"]
    return out


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
    ):
        projected.update(_project_promotion_fields(value))

    elif action in (
        "notification_created",
        "notification_deleted",
    ):
        projected.update(_project_notification_fields(value))

    elif action in ("business_manager_created", "business_manager_password_reset"):
        for k, v in value.items():
            if k in ("id", "manager_id", "admin_user_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected["id"] = cid
            elif k == "login":
                clean_login = _clean_str(v, max_length=128)
                if clean_login:
                    projected["login"] = clean_login

    elif action == "media_uploaded":
        for k, v in value.items():
            if k == "purpose":
                if isinstance(v, str) and v in ("promotion", "logo"):
                    projected["purpose"] = v
            elif k == "bytes":
                if isinstance(v, int) and v >= 0:
                    projected["bytes"] = v
            elif k in ("width", "height"):
                if isinstance(v, int) and v >= 0:
                    projected[k] = v
            elif k == "url":
                clean_url = _clean_str(v, max_length=1024)
                if clean_url:
                    projected["url"] = clean_url

    elif action == "pos_key_created":
        for k, v in value.items():
            if k in ("pos_key_id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "name":
                cname = _clean_str(v, max_length=100)
                if cname:
                    projected["name"] = cname
            elif k == "created_at":
                ccreated = _clean_str(v, max_length=64)
                if ccreated:
                    projected["created_at"] = ccreated

    elif action == "pos_key_revoked":
        for k, v in value.items():
            if k in ("pos_key_id", "business_id"):
                cid = _clean_uuid_str(v) or _clean_str(v, max_length=64)
                if cid:
                    projected[k] = cid
            elif k == "name":
                cname = _clean_str(v, max_length=100)
                if cname:
                    projected["name"] = cname
            elif k == "status":
                if isinstance(v, str) and v in ("active", "revoked"):
                    projected["status"] = v
            elif k == "revoked_at":
                crev = _clean_str(v, max_length=64)
                if crev:
                    projected["revoked_at"] = crev

    elif action == "loyalty_scale_updated":
        # Numbers, ids and activity only: no names/descriptions/image URLs.
        version = value.get("version")
        if isinstance(version, int) and not isinstance(version, bool):
            projected["version"] = version
        tiers = value.get("tiers")
        if isinstance(tiers, (list, tuple)):
            rows: list[dict[str, Any]] = []
            for row in tiers[:100]:
                if not isinstance(row, Mapping):
                    continue
                item = _project_tier_fields(row)
                item.pop("priority", None)
                item.pop("name_ru", None)
                item.pop("name_kk", None)
                if item:
                    rows.append(item)
            if rows:
                projected["tiers"] = rows

    elif action in ("loyalty_tier_created", "loyalty_tier_updated", "loyalty_tier_deleted"):
        projected.update(_project_tier_fields(value))

    elif action in ("store_created", "store_updated", "store_deleted"):
        projected.update(_project_store_fields(value))

    elif action == "app_texts_updated":
        projected.update(_project_app_texts_state(value))

    elif action == "business_splash_updated":
        projected.update(_project_splash_state(value))

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
    - business_id != None (except media_uploaded which can be global)

    Legacy and unknown events project to None to prevent disclosure of arbitrary
    or historical secrets. Known Admin mutation actions project only explicitly
    allowlisted safe shapes and scalar types, dropping any malformed or unexpected nested fields.
    """
    if value is None or not isinstance(value, Mapping):
        return None
    if action:
        action = _ACTION_ALIASES.get(action, action)
    if not action or action not in _KNOWN_ADMIN_ACTIONS:
        return None
    if admin_user_id is None:
        return None
    if business_id is None and action not in (
        "media_uploaded",
        "notification_created",
        "notification_deleted",
        "promotion_created",
        "promotion_updated",
        "promotion_deleted",
    ):
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
        for field in (
            "android_app_id",
            "barcode_prefixes",
            "colors",
            "loyalty_tiers",
            "logo_url",
            "name",
            "status",
        )
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


async def generate_unique_manager_login(db: AsyncSession, business_name: str) -> str:
    base = generate_base_login(business_name)
    candidate = base
    for _ in range(20):
        normalized = normalize_admin_login(candidate)
        exists = await db.scalar(
            select(func.count(AdminUser.id)).where(AdminUser.login == normalized)
        )
        if not exists:
            return normalized
        suffix = random_slug(4)
        prefix = base[:120] if len(base) > 120 else base
        candidate = f"{prefix}-{suffix}"
    fallback = f"biz-{random_slug(6)}"
    return normalize_admin_login(fallback)


async def create_business(
    db: AsyncSession, actor: AdminUser, request: BusinessCreateRequest
) -> tuple[Business, ManagerAccessDisclosure | None]:
    actor_scope = scope_for_admin(actor)
    actor_scope.require_superadmin()
    payload = request.model_dump()
    create_manager = payload.pop("create_manager", True)
    app_id = payload.get("android_app_id")
    if app_id:
        existing = await db.scalar(
            select(Business.id).where(Business.android_app_id == app_id)
        )
        if existing:
            raise AppError(
                "DUPLICATE_ANDROID_APP_ID",
                f"Business with android_app_id '{app_id}' already exists",
                422,
            )
    business = Business(**payload)
    db.add(business)
    try:
        await db.flush()
    except IntegrityError as exc:
        if "android_app_id" in str(exc).lower():
            raise AppError(
                "DUPLICATE_ANDROID_APP_ID",
                f"Business with android_app_id '{app_id}' already exists",
                422,
            ) from exc
        raise
    _audit(
        db,
        actor,
        business.id,
        "business_created",
        "business",
        None,
        _business_state(business),
    )
    manager_access: ManagerAccessDisclosure | None = None
    if create_manager:
        login = await generate_unique_manager_login(db, business.name)
        password = generate_manager_password(16)
        password_hash = hash_admin_password(password)
        manager = AdminUser(
            login=login,
            password_hash=password_hash,
            role="business_manager",
            business_id=business.id,
            is_active=True,
        )
        db.add(manager)
        await db.flush()
        _audit(
            db,
            actor,
            business.id,
            "business_manager_created",
            "admin_user",
            None,
            {"id": str(manager.id), "login": manager.login},
        )
        manager_access = ManagerAccessDisclosure(
            login=manager.login,
            password=password,
            login_url=settings.admin_public_url,
            one_time=True,
        )
    await db.commit()
    await db.refresh(business)
    return business, manager_access


async def reset_or_create_business_manager(
    db: AsyncSession, actor: AdminUser, business_id: uuid.UUID
) -> ManagerAccessDisclosure:
    scope_for_admin(actor).require_superadmin()
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)

    result = await db.execute(
        select(AdminUser)
        .where(
            AdminUser.business_id == business_id,
            AdminUser.role == "business_manager",
        )
        .order_by(AdminUser.created_at.asc())
        .with_for_update()
    )
    manager = result.scalars().first()

    if manager is None:
        login = await generate_unique_manager_login(db, business.name)
        password = generate_manager_password(16)
        password_hash = hash_admin_password(password)
        manager = AdminUser(
            login=login,
            password_hash=password_hash,
            role="business_manager",
            business_id=business.id,
            is_active=True,
        )
        db.add(manager)
        await db.flush()
        _audit(
            db,
            actor,
            business.id,
            "business_manager_created",
            "admin_user",
            None,
            {"id": str(manager.id), "login": manager.login},
        )
        await db.commit()
        await db.refresh(manager)
        return ManagerAccessDisclosure(
            login=manager.login,
            password=password,
            login_url=settings.admin_public_url,
            one_time=True,
        )
    else:
        password = generate_manager_password(16)
        password_hash = hash_admin_password(password)
        manager.password_hash = password_hash
        manager.is_active = True
        now = utcnow()
        await db.execute(
            update(AdminSession)
            .where(
                AdminSession.admin_user_id == manager.id,
                AdminSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        _audit(
            db,
            actor,
            business.id,
            "business_manager_password_reset",
            "admin_user",
            None,
            {"id": str(manager.id), "login": manager.login},
        )
        await db.commit()
        await db.refresh(manager)
        return ManagerAccessDisclosure(
            login=manager.login,
            password=password,
            login_url=settings.admin_public_url,
            one_time=True,
        )


async def update_business(
    db: AsyncSession,
    actor: AdminUser,
    business_id: uuid.UUID,
    request: BusinessUpdateRequest,
    *,
    storage: MediaStorage | None = None,
    settings: Any | None = None,
) -> Business:
    actor_scope = scope_for_admin(actor)
    actor_scope.require_superadmin()
    business = await db.scalar(
        select(Business).where(Business.id == business_id).with_for_update()
    )
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    before = _business_state(business)
    old_logo_url = business.logo_url
    fields = request.model_dump(mode="json", exclude_unset=True)
    if fields.get("android_app_id"):
        app_id = fields["android_app_id"]
        existing = await db.scalar(
            select(Business.id).where(
                Business.android_app_id == app_id,
                Business.id != business_id,
            )
        )
        if existing:
            raise AppError(
                "DUPLICATE_ANDROID_APP_ID",
                f"Business with android_app_id '{app_id}' already exists",
                422,
            )
    previous_colors = business.colors
    for field, value in fields.items():
        setattr(business, field, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        if "android_app_id" in str(exc).lower():
            raise AppError(
                "DUPLICATE_ANDROID_APP_ID",
                f"Business with android_app_id '{fields.get('android_app_id')}' already exists",
                422,
            ) from exc
        raise
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

    if (
        storage is not None
        and settings is not None
        and "logo_url" in fields
        and old_logo_url
        and old_logo_url != business.logo_url
    ):
        await maybe_cleanup_old_media_file(db, storage, old_logo_url, settings)

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


async def create_pos_key_mutation(
    db: AsyncSession, actor: AdminUser, business_id: uuid.UUID, name: str
) -> tuple[PosKey, str]:
    scope_for_admin(actor).require_superadmin()
    clean_name = name.strip()
    if not clean_name:
        raise AppError("VALIDATION_ERROR", "POS key name cannot be empty", 422)
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    pos_key, raw_key = await issue_pos_key(db, business_id, clean_name)
    _audit(
        db,
        actor,
        business_id,
        "pos_key_created",
        "pos_key",
        None,
        {
            "pos_key_id": str(pos_key.id),
            "business_id": str(business_id),
            "name": pos_key.name,
            "created_at": pos_key.created_at.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(pos_key)
    return pos_key, raw_key


async def revoke_pos_key_mutation(
    db: AsyncSession, actor: AdminUser, key_id: uuid.UUID
) -> PosKey:
    scope_for_admin(actor).require_superadmin()
    pos_key = await db.scalar(select(PosKey).where(PosKey.id == key_id).with_for_update())
    if pos_key is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    if pos_key.revoked_at is not None:
        return pos_key
    before = {
        "pos_key_id": str(pos_key.id),
        "business_id": str(pos_key.business_id),
        "name": pos_key.name,
        "status": "active",
    }
    await revoke_pos_key(db, pos_key)
    _audit(
        db,
        actor,
        pos_key.business_id,
        "pos_key_revoked",
        "pos_key",
        before,
        {
            "pos_key_id": str(pos_key.id),
            "business_id": str(pos_key.business_id),
            "name": pos_key.name,
            "status": "revoked",
            "revoked_at": pos_key.revoked_at.isoformat() if pos_key.revoked_at else None,
        },
    )
    await db.commit()
    await db.refresh(pos_key)
    return pos_key
