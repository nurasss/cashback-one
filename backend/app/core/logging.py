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

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|pwd|token|secret|jwt|otp|wappi|key_hash|agent.?key|api.?key|"
    r"phone|barcode|full.?name|credential|database_url|connection_string|authorization|cookie)",
    re.IGNORECASE,
)

_SECRET_VALUE_PATTERN = re.compile(
    r"(?:\bagk_[A-Za-z0-9_-]+|\brfr_[A-Za-z0-9_-]+|\badm_rfr_[A-Za-z0-9_-]+|"
    r"\bBearer\s+[A-Za-z0-9._-]+|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)

_CREDENTIALS_IN_URL_PATTERN = re.compile(
    r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s:@]+@",
    re.IGNORECASE,
)


def get_current_request_id() -> str:
    return request_id_ctx.get()


def redact_sensitive_text(text: str) -> str:
    """Redacts sensitive values, credentials, tokens, and DB passwords from string."""
    if not text:
        return text
    # Redact URL credentials like postgresql://user:pass@host
    redacted = _CREDENTIALS_IN_URL_PATTERN.sub(lambda m: m.group(0).split("://")[0] + "://[REDACTED]:[REDACTED]@", text)
    # Redact token patterns
    redacted = _SECRET_VALUE_PATTERN.sub("[REDACTED]", redacted)
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

        # Include structured HTTP metadata if available
        for attr in ("method", "path", "status", "duration_ms"):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)

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

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logging.getLogger("app.access").error(
                "Request failed with unhandled exception",
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id

        # Safe access log: logs route path, never raw query with potential PII
        if not request.url.path.startswith("/health/live"):
            logging.getLogger("app.access").info(
                "HTTP request completed",
                extra={
                    "request_id": req_id,
                    "method": request.method,
                    "path": request.url.path,
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
