import contextvars
import json
import logging
import re
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_VALID_REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")

SENSITIVE_KEYS = (
    r"password|passwd|pwd|token|secret|jwt|otp|wappi|key_hash|agent[-_]?key|api[-_]?key|"
    r"phone|barcode|full[-_]?name|credential|database_url|connection_string"
)

# Whole sensitive HTTP header lines
_HEADER_PATTERN = re.compile(
    r"(?i)\b(authorization|cookie|x[-_]?agent[-_]?key)\s*:\s*[^\r\n]+",
    re.IGNORECASE,
)

# Connection string password components (e.g. Password=...; in ONE connection strings)
_ONE_CONN_PATTERN = re.compile(
    r"(?i)\b(password|pwd)\s*=\s*(?!\[REDACTED\])[^;\r\n]+",
    re.IGNORECASE,
)

# Sensitive key-value pairs (JSON, query param, or assignment)
_KEY_VALUE_PATTERN = re.compile(
    r'(?i)((?:["\']?(?:' + SENSITIVE_KEYS + r')["\']?)\s*[:=]\s*)(?:\"[^\"]*\"|\'[^\']*\'|(?!\[REDACTED\])[^\s,;}{\]]+)'
)

# Credentials in URLs (e.g. postgresql://user:pass@host)
_CREDENTIALS_IN_URL_PATTERN = re.compile(
    r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s:@]+@",
    re.IGNORECASE,
)
_REDIS_URL_PATTERN = re.compile(r"redis://:[^/@\s]+@", re.IGNORECASE)

# Known opaque tokens and signatures
_SECRET_VALUE_PATTERN = re.compile(
    r"(?:\bagk_[A-Za-z0-9_-]+|\brfr_[A-Za-z0-9_-]+|\badm_rfr_[A-Za-z0-9_-]+|"
    r"\bBearer\s+[A-Za-z0-9._-]+|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)

# Phone numbers (E.164 or CIS formats)
_PHONE_PATTERN = re.compile(r"(?:\+?7|8)\d{10}\b")

# Barcodes (12-14 digits)
_BARCODE_PATTERN = re.compile(r"\b\d{12,14}\b")

# Path segments that should be masked to avoid PII in logs
_PATH_SENSITIVE_SEGMENT = re.compile(
    r"^(?:"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"  # UUID
    r"|\+?\d{7,16}"  # Phone / barcode / numeric ID
    r"|[0-9a-fA-F]{16,64}"  # Hex hash / ID
    r"|[A-Za-z0-9_-]{20,}"  # Long token / key
    r")$"
)


def get_current_request_id() -> str:
    return request_id_ctx.get()


def safe_route_path(path: str) -> str:
    """Masks path parameters containing identifiers, phones, barcodes, or tokens."""
    if not path:
        return ""
    # Strip any query string or fragment
    path_only = path.split("?")[0].split("#")[0]
    segments = path_only.split("/")
    safe_segments = [
        "[REDACTED]" if _PATH_SENSITIVE_SEGMENT.match(seg) else seg
        for seg in segments
    ]
    return "/".join(safe_segments)


def redact_sensitive_text(text: str) -> str:
    """Redacts sensitive values, credentials, tokens, DB passwords, and PII from string."""
    if not text:
        return text
    # 1. Header lines
    redacted = _HEADER_PATTERN.sub(r"\1: [REDACTED]", text)
    # 2. Connection string password components
    redacted = _ONE_CONN_PATTERN.sub(r"\1=[REDACTED]", redacted)
    # 3. Key-value pairs
    redacted = _KEY_VALUE_PATTERN.sub(r"\1[REDACTED]", redacted)
    # 4. URL credentials
    redacted = _CREDENTIALS_IN_URL_PATTERN.sub(
        lambda m: m.group(0).split("://")[0] + "://[REDACTED]:[REDACTED]@", redacted
    )
    redacted = _REDIS_URL_PATTERN.sub("redis://:[REDACTED]@", redacted)
    # 5. Opaque secret formats
    redacted = _SECRET_VALUE_PATTERN.sub("[REDACTED]", redacted)
    # 6. Phones and barcodes
    redacted = _PHONE_PATTERN.sub("[REDACTED]", redacted)
    redacted = _BARCODE_PATTERN.sub("[REDACTED]", redacted)
    return redacted


class StructuredJsonFormatter(logging.Formatter):
    """Production JSON formatter with automatic request correlation and log redaction."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or get_current_request_id()
        clean_msg = redact_sensitive_text(record.getMessage())

        log_entry: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": clean_msg,
        }
        if req_id:
            log_entry["request_id"] = req_id

        # Include structured HTTP metadata if available, ensuring paths are safe and no query strings
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = safe_route_path(str(record.path))
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_entry["exception"] = redact_sensitive_text(record.exc_text)

        return json.dumps(log_entry, ensure_ascii=False)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Extracts, validates, or generates X-Request-ID, binds it to contextvars,

    and logs an access summary without PII or raw query strings.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_req_id = request.headers.get("X-Request-ID", "").strip()
        if raw_req_id and _VALID_REQUEST_ID_PATTERN.match(raw_req_id):
            req_id = raw_req_id
        else:
            req_id = str(uuid.uuid4())

        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id
        start_time = time.monotonic()
        safe_path = safe_route_path(request.url.path)

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logging.getLogger("app.access").error(
                "Request failed with unhandled exception: %s",
                exc.__class__.__name__,
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": safe_path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id

        # Safe access log: logs route path without PII, never raw query
        if not request.url.path.startswith("/health/live"):
            logging.getLogger("app.access").info(
                "HTTP request completed",
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": safe_path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

        return response


def configure_logging() -> None:
    """Configures application-wide logging with JSON formatting in production."""
    root_logger = logging.getLogger()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    formatter: logging.Formatter
    if settings.log_format == "json" or settings.app_env.lower() == "production":
        formatter = StructuredJsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(request_id)s): %(message)s",
            defaults={"request_id": "-"},
        )

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # In production, silence default uvicorn.access logger so it doesn't leak raw query strings
    if settings.app_env.lower() == "production":
        uvicorn_access = logging.getLogger("uvicorn.access")
        uvicorn_access.handlers.clear()
        uvicorn_access.propagate = False
