import hashlib
import hmac
import ipaddress
import re
import secrets
import uuid
from datetime import timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher, Type
from argon2 import exceptions as argon_errors
from fastapi import Request

from app.core.admin_types import AdminRole
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_refresh_token
from app.core.time import utcnow

ADMIN_JWT_ISSUER = "cashback-one-admin"
ADMIN_JWT_AUDIENCE = "cashback-one-admin"
ADMIN_REFRESH_PREFIX = "adm_rfr_"
COOKIE_NAME = "admin_refresh"
COOKIE_PATH = "/admin"
MIN_ADMIN_PASSWORD_LENGTH = 12

_LOGIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._@-]{2,127}$")
_JWT_TOKEN_PATTERN = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)
_OPAQUE_SECRET_PATTERN = re.compile(r"\b(?:agk_|rfr_|adm_rfr_)[A-Za-z0-9_.-]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(password|passwd|token|secret|api[_-]?key|key|"
    r"access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_LONG_PHONE_OR_BARCODE_PATTERN = re.compile(r"(?<!\d)\+?\d(?:[\s().-]*\d){9,14}(?!\d)")
_LONG_NUMBER_PATTERN = re.compile(r"(?<!\d)\+?\d(?:[\s().-]*\d){9,14}(?!\d)")


@lru_cache(maxsize=1)
def password_hasher() -> PasswordHasher:
    return PasswordHasher(type=Type.ID, time_cost=3, memory_cost=65536, parallelism=4)


def normalize_admin_login(login: str) -> str:
    normalized = login.strip().lower()
    if not _LOGIN_PATTERN.fullmatch(normalized):
        raise ValueError("login must contain 3 to 128 ASCII letters, digits, '.', '_', '@' or '-'")
    return normalized


def validate_admin_password(password: str) -> None:
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters")
    if len(password.encode("utf-8")) > 1024:
        raise ValueError("password is too long")


def hash_admin_password(password: str) -> str:
    validate_admin_password(password)
    return password_hasher().hash(password)


def verify_admin_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher().verify(password_hash, password)
    except argon_errors.Argon2Error:
        return False


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return password_hasher().hash(secrets.token_urlsafe(32))


def create_admin_access_token(admin_id: uuid.UUID, session_id: uuid.UUID) -> str:
    now = utcnow()
    return jwt.encode(
        {
            "sub": str(admin_id),
            "sid": str(session_id),
            "typ": "admin_access",
            "iss": ADMIN_JWT_ISSUER,
            "aud": ADMIN_JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=settings.admin_access_token_ttl_seconds)).timestamp()),
        },
        settings.admin_jwt_signing_key,
        algorithm="HS256",
    )


def decode_admin_access_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        payload = jwt.decode(
            token,
            settings.admin_jwt_signing_key,
            algorithms=["HS256"],
            issuer=ADMIN_JWT_ISSUER,
            audience=ADMIN_JWT_AUDIENCE,
            options={"require": ["sub", "sid", "typ", "iss", "aud", "iat", "exp"]},
        )
        if payload.get("typ") != "admin_access":
            raise ValueError("wrong token type")
        return uuid.UUID(payload["sub"]), uuid.UUID(payload["sid"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as err:
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401) from err


def generate_admin_refresh_token() -> str:
    return f"{ADMIN_REFRESH_PREFIX}{secrets.token_urlsafe(48)}"


def admin_refresh_token_hash(raw_token: str) -> str:
    return hash_refresh_token(raw_token)


def login_rate_key(namespace: str, value: str) -> str:
    # HMAC protects low-entropy logins and addresses against Redis-key enumeration.
    digest = hmac.new(
        settings.admin_jwt_signing_key.encode(),
        f"admin-rate:{namespace}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"admin:{namespace}:{digest}"


def is_loopback_hostname(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def is_trusted_proxy_client(ip: str | None) -> bool:
    if not ip:
        return False
    raw_ips = settings.forwarded_allow_ips.strip() if settings.forwarded_allow_ips else ""
    if not raw_ips or raw_ips in {"*", "all"}:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for part in raw_ips.split(","):
        entry = part.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                net = ipaddress.ip_network(entry, strict=False)
                if net.prefixlen > 0 and addr in net:
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


def get_effective_scheme(request: Request) -> str:
    peer_ip = request.client.host if request.client else None
    if peer_ip and is_trusted_proxy_client(peer_ip):
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            proto = forwarded_proto.split(",")[0].strip().lower()
            if proto in {"http", "https"}:
                return proto
    if hasattr(request, "scope") and "scheme" in request.scope:
        return str(request.scope["scheme"])
    return request.url.scheme


def is_explicit_dev_http(request: Request) -> bool:
    return (
        get_effective_scheme(request) == "http"
        and settings.app_env.lower() in {"development", "test"}
        and settings.admin_allow_insecure_http
    )


def require_admin_transport(request: Request) -> None:
    scheme = get_effective_scheme(request)
    if scheme != "https" and not is_explicit_dev_http(request):
        raise AppError("ADMIN_HTTPS_REQUIRED", "Admin access requires a secure connection", 400)


def secure_admin_cookie(request: Request) -> bool:
    if is_explicit_dev_http(request):
        return False
    if settings.app_env.lower() == "production":
        return True
    return get_effective_scheme(request) == "https"


def sanitize_agent_error(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = _JWT_TOKEN_PATTERN.sub("Bearer [REDACTED]", value)
    sanitized = _OPAQUE_SECRET_PATTERN.sub("[REDACTED]", sanitized)
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", sanitized)
    sanitized = _LONG_PHONE_OR_BARCODE_PATTERN.sub("[REDACTED NUMBER]", sanitized)
    sanitized = _LONG_NUMBER_PATTERN.sub("[REDACTED NUMBER]", sanitized)
    return sanitized[:512]


def mask_phone(phone: str | None) -> str | None:
    if phone is None:
        return None
    digits = "".join(char for char in phone if char.isdigit())
    if len(digits) < 4:
        return "••••"
    return f"••••{digits[-4:]}"


def valid_admin_role(value: str) -> bool:
    return value in ("superadmin", "business_manager")


def admin_role(value: str) -> AdminRole:
    if not valid_admin_role(value):
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
    return value  # type: ignore[return-value]
