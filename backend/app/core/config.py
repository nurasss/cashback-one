import ipaddress
import re
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_FORBIDDEN_WEAK_SECRETS: set[str] = {
    "changeme",
    "secret",
    "development-secret",
    "test-secret",
    "default-key",
    "admin123",
    "password",
}


def _is_weak_secret(val: str) -> bool:
    normalized = val.strip().lower()
    if normalized in _FORBIDDEN_WEAK_SECRETS:
        return True
    if normalized.startswith(("change_me", "changeme")):
        return True
    return bool(normalized.startswith(("test_", "default")) or "fixture" in normalized)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "POSCENTER Loyalty Backend"
    app_version: str = "0.4.0"
    app_env: str = "development"
    database_url: str = Field(
        default="",
        description="Database connection URL. Must be explicitly provided via environment or .env.",
    )
    redis_url: str = Field(
        default="",
        description="Redis connection URL for rate limiting and cache. Required in dev/prod.",
    )

    # Auth secrets & configuration (TASK-003)
    jwt_signing_key: str = Field(
        default="",
        description="HMAC secret key for signing customer access JWTs (min 32 chars).",
    )
    auth_challenge_hash_key: str = Field(
        default="",
        description="HMAC secret key for challenge code digests (min 32 chars).",
    )
    whatsapp_login_number: str = Field(
        default="",
        description="WhatsApp business login number in E.164 format (+77001234567).",
    )

    # Wappi Webhook Configuration (TASK-004)
    wappi_login_profile_id: str = Field(
        default="",
        description="Wappi WhatsApp instance/profile ID for login messages.",
    )
    wappi_webhook_auth_header: str = Field(
        default="",
        description="Header name used to authenticate incoming Wappi webhooks (must be explicitly configured).",
    )
    wappi_webhook_auth_secret: str = Field(
        default="",
        description="Shared secret for incoming Wappi webhook authentication (min 32 chars).",
    )
    wappi_webhook_max_body_bytes: int = Field(
        default=65536,
        description="Maximum allowed body size for Wappi webhook requests (default 64KB).",
    )

    # Admin browser authentication and operational console.
    admin_jwt_signing_key: str = Field(default="", description="Independent admin JWT signing key (minimum 32 characters).")
    admin_access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    admin_refresh_token_ttl_seconds: int = Field(default=28800, ge=900, le=28800)
    admin_allowed_origins: list[str] = Field(default_factory=list)
    admin_login_limit: int = Field(default=5, ge=1, le=50)
    admin_login_ip_limit: int = Field(default=20, ge=1, le=200)
    admin_login_rate_window_seconds: int = Field(default=300, ge=30, le=3600)
    admin_agent_stale_seconds: int = Field(default=900, ge=60, le=86400)
    admin_max_stats_period_days: int = Field(default=90, ge=1, le=365)
    admin_allow_insecure_http: bool = False

    # Production runtime, connection pool, and security settings (TASK-012)
    debug: bool = Field(default=False, description="Debug mode. Must be False in production.")
    db_pool_size: int = Field(default=10, ge=1, le=100, description="Database connection pool size.")
    db_max_overflow: int = Field(default=20, ge=0, le=100, description="Max overflow connections beyond pool size.")
    db_pool_timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0, description="Database pool checkout timeout.")
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400, description="Database connection recycle seconds.")
    db_pool_pre_ping: bool = Field(default=True, description="Enable connection health pre-ping.")
    db_statement_timeout_ms: int = Field(default=10000, ge=100, le=60000, description="PostgreSQL statement timeout in ms.")

    redis_connect_timeout_seconds: float = Field(default=2.0, ge=0.1, le=30.0, description="Redis connection timeout in seconds.")
    redis_socket_timeout_seconds: float = Field(default=2.0, ge=0.1, le=30.0, description="Redis operation socket timeout in seconds.")

    forwarded_allow_ips: str = Field(default="127.0.0.1", description="Trusted proxy IPs for forwarded headers. Never '*' in production.")
    log_format: str = Field(default="json", description="Structured logging format: 'json' or 'text'.")
    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR.")

    # SMS OTP Fallback Configuration (TASK-007)
    sms_otp_hash_key: str = Field(
        default="",
        description="HMAC secret key for SMS OTP code digests (min 32 chars).",
    )
    sms_otp_ttl_seconds: int = 300  # 5 minutes
    sms_otp_max_attempts: int = 5
    # Cap on wrong verification attempts per phone across ALL codes in the window,
    # so re-requesting fresh codes cannot be used to brute-force the 6-digit space.
    sms_otp_phone_failed_attempts_limit: int = 15
    sms_otp_phone_failed_attempts_window_seconds: int = 86400  # 24 hours
    sms_otp_request_phone_limit: int = 3
    sms_otp_request_device_limit: int = 5
    sms_otp_request_ip_limit: int = 20
    sms_otp_rate_window_seconds: int = 300
    sms_provider_mode: str = Field(
        default="disabled",
        description="SMS provider mode: 'disabled' or 'fake'.",
    )

    # Auth TTL and limits
    challenge_ttl_seconds: int = 180  # 3 minutes
    # Window to exchange a confirmed challenge for tokens, counted from confirmation time
    challenge_exchange_ttl_seconds: int = 300  # 5 minutes
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 14 * 86400  # customer session is remembered for 14 days

    auth_challenge_device_limit: int = 5
    auth_challenge_ip_limit: int = 20
    auth_challenge_rate_window_seconds: int = 300

    # Outbound WhatsApp messages (login OTP, redemption codes) via Wappi send API.
    # 'disabled' rejects sends, 'fake' records them in memory (APP_ENV=test only),
    # 'log' prints them to the server log (local development only), 'wappi' sends.
    whatsapp_provider_mode: str = Field(default="disabled")
    wappi_api_base_url: str = Field(default="https://wappi.pro")
    wappi_api_token: str = Field(default="")
    # Profile used to send messages; defaults to WAPPI_LOGIN_PROFILE_ID
    wappi_sender_profile_id: str = Field(default="")
    wappi_send_timeout_seconds: float = 10.0
    whatsapp_otp_request_phone_limit: int = 3
    whatsapp_otp_request_device_limit: int = 5
    whatsapp_otp_request_ip_limit: int = 20

    # Dynamic card QR: signed token lifetime
    qr_token_ttl_seconds: int = 60

    # POS bonus write-off confirmation codes sent to the customer's WhatsApp
    redemption_code_ttl_seconds: int = 300
    redemption_code_max_attempts: int = 5
    redemption_card_request_limit: int = 5
    redemption_card_rate_window_seconds: int = 600

    # Manual card bind attempts per customer (anti barcode enumeration)
    card_bind_user_limit: int = 20
    card_bind_rate_window_seconds: int = 300

    # "Add to Wallet" passes: the card's static barcode as a QR (the in-app QR stays dynamic).
    # Each wallet is enabled only when all of its settings are present.
    wallet_public_base_url: str = Field(default="", description="Public HTTPS URL of this API, e.g. https://api.example.kz")
    wallet_organization_name: str = "POSCENTER ONE"
    wallet_link_ttl_seconds: int = 600
    apple_pass_type_id: str = ""
    apple_team_id: str = ""
    apple_pass_cert_file: str = Field(default="", description="PEM certificate of the Pass Type ID")
    apple_pass_key_file: str = Field(default="", description="PEM private key of the Pass Type ID certificate")
    apple_pass_key_password: str = ""
    apple_wwdr_cert_file: str = Field(default="", description="PEM Apple WWDR intermediate certificate")
    google_wallet_issuer_id: str = ""
    google_wallet_service_account_file: str = Field(default="", description="Service account JSON key with Wallet access")

    # Agent sync limits
    sync_max_cards_batch: int = 500
    sync_max_transactions_batch: int = 1000

    @field_validator("app_env", mode="before")
    @classmethod
    def validate_app_env(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise TypeError(f"APP_ENV must be a string, got {type(v).__name__}")
        normalized = v.strip().lower()
        if normalized not in {"test", "development", "production"}:
            raise ValueError(
                f"Invalid APP_ENV '{v}'. Allowed environments: development, production, test"
            )
        return normalized

    @field_validator("admin_allowed_origins", mode="before")
    @classmethod
    def parse_admin_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            clean = v.strip()
            if not clean:
                return []
            if clean.startswith("[") and clean.endswith("]"):
                try:
                    import json

                    parsed = json.loads(clean)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except (ValueError, TypeError):
                    pass
            return [p.strip() for p in clean.split(",") if p.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        db_url = self.database_url.strip() if self.database_url else ""
        if not db_url:
            raise ValueError(
                "DATABASE_URL must be explicitly provided in environment or .env"
            )
        if self.app_env in {"development", "production"} and db_url.startswith("sqlite"):
            raise ValueError(
                "SQLite is only permitted when APP_ENV=test. DATABASE_URL must not use SQLite in production or development. PostgreSQL is required."
            )

        # Validate SMS provider mode
        clean_provider_mode = (
            self.sms_provider_mode.strip().lower() if self.sms_provider_mode else ""
        )
        if clean_provider_mode not in ("disabled", "fake"):
            raise ValueError(
                f"Invalid SMS_PROVIDER_MODE '{self.sms_provider_mode}'. Supported modes: 'disabled', 'fake'."
            )
        self.sms_provider_mode = clean_provider_mode

        clean_whatsapp_mode = (self.whatsapp_provider_mode or "").strip().lower()
        if clean_whatsapp_mode not in ("disabled", "fake", "log", "wappi"):
            raise ValueError(
                f"Invalid WHATSAPP_PROVIDER_MODE '{self.whatsapp_provider_mode}'. "
                "Supported modes: 'disabled', 'fake', 'log', 'wappi'."
            )
        if clean_whatsapp_mode == "log" and self.app_env == "production":
            raise ValueError("WHATSAPP_PROVIDER_MODE 'log' prints one-time codes and is forbidden in production.")
        self.whatsapp_provider_mode = clean_whatsapp_mode
        if clean_whatsapp_mode == "fake" and self.app_env != "test":
            raise ValueError("WHATSAPP_PROVIDER_MODE 'fake' is strictly forbidden outside APP_ENV=test.")
        if clean_whatsapp_mode == "wappi":
            if not self.wappi_api_token.strip():
                raise ValueError("WAPPI_API_TOKEN must be provided when WHATSAPP_PROVIDER_MODE=wappi")
            if not self.wappi_api_base_url.strip().startswith("https://"):
                raise ValueError("WAPPI_API_BASE_URL must use HTTPS")

        base = self.wallet_public_base_url.strip().rstrip("/")
        if base and not base.startswith("https://") and self.app_env == "production":
            raise ValueError("WALLET_PUBLIC_BASE_URL must use HTTPS")
        self.wallet_public_base_url = base

        if self.app_env.lower() == "test":
            # Provide deterministic defaults for test execution
            if not self.redis_url:
                self.redis_url = "redis://localhost:6379/15"
            if not self.jwt_signing_key:
                self.jwt_signing_key = "test_jwt_signing_key_at_least_32_chars_long_12345"
            if not self.auth_challenge_hash_key:
                self.auth_challenge_hash_key = "test_challenge_hash_key_at_least_32_chars_long_12345"
            if not self.sms_otp_hash_key:
                self.sms_otp_hash_key = "test_sms_otp_hash_key_min_32_characters_12345"
            if not self.whatsapp_login_number:
                self.whatsapp_login_number = "+77001234567"
            if not self.wappi_login_profile_id:
                self.wappi_login_profile_id = "test-wappi-login-profile"
            if not self.wappi_webhook_auth_header:
                self.wappi_webhook_auth_header = "X-Test-Wappi-Auth"
            if not self.wappi_webhook_auth_secret:
                self.wappi_webhook_auth_secret = "test_wappi_webhook_secret_min_32_characters_12345"
            if not self.admin_jwt_signing_key:
                self.admin_jwt_signing_key = "test_only_admin_signing_key_distinct_678901234567"
            if not self.admin_allowed_origins:
                self.admin_allowed_origins = ["https://admin.test"]
        else:
            if not self.redis_url or not self.redis_url.strip():
                raise ValueError("REDIS_URL must be explicitly provided in environment or .env")
            if not self.jwt_signing_key or len(self.jwt_signing_key.strip()) < 32:
                raise ValueError("JWT_SIGNING_KEY must be provided and be at least 32 characters long")
            if not self.auth_challenge_hash_key or len(self.auth_challenge_hash_key.strip()) < 32:
                raise ValueError("AUTH_CHALLENGE_HASH_KEY must be provided and be at least 32 characters long")
            if not self.sms_otp_hash_key or len(self.sms_otp_hash_key.strip()) < 32:
                raise ValueError("SMS_OTP_HASH_KEY must be explicitly provided and be at least 32 characters long")
            if not self.wappi_login_profile_id or not self.wappi_login_profile_id.strip():
                raise ValueError("WAPPI_LOGIN_PROFILE_ID must be provided in environment or .env")
            if not self.wappi_webhook_auth_header or not self.wappi_webhook_auth_header.strip():
                raise ValueError("WAPPI_WEBHOOK_AUTH_HEADER must be provided in environment or .env")
            if not self.wappi_webhook_auth_secret or len(self.wappi_webhook_auth_secret.strip()) < 32:
                raise ValueError("WAPPI_WEBHOOK_AUTH_SECRET must be provided and be at least 32 characters long")
            if self.sms_provider_mode == "fake":
                raise ValueError("SMS_PROVIDER_MODE 'fake' is strictly forbidden in development/production.")
            if self.sms_provider_mode != "disabled":
                raise ValueError(
                    f"SMS_PROVIDER_MODE '{self.sms_provider_mode}' is not permitted in development/production. "
                    "Only 'disabled' is currently supported."
                )

            if not self.admin_jwt_signing_key or len(self.admin_jwt_signing_key.strip()) < 32:
                raise ValueError("ADMIN_JWT_SIGNING_KEY must be provided and at least 32 characters long")
            if self.admin_jwt_signing_key == self.jwt_signing_key:
                raise ValueError("ADMIN_JWT_SIGNING_KEY must be different from JWT_SIGNING_KEY")
            if not self.admin_allowed_origins:
                raise ValueError("ADMIN_ALLOWED_ORIGINS must explicitly list trusted browser origins")

            if self.app_env.lower() == "production":
                if self.debug:
                    raise ValueError("DEBUG must be disabled (False) in production")
                if db_url.startswith("sqlite"):
                    raise ValueError("DATABASE_URL must not use SQLite in production. PostgreSQL is required.")
                if not db_url.startswith(("postgresql+asyncpg://", "postgresql://")):
                    raise ValueError("DATABASE_URL must be a PostgreSQL connection URL in production")
                if self.admin_allow_insecure_http:
                    raise ValueError("HTTP admin origins require explicit development opt-in: ADMIN_ALLOW_INSECURE_HTTP is strictly forbidden in production")
                # Check FORWARDED_ALLOW_IPS
                raw_ips = self.forwarded_allow_ips.strip() if self.forwarded_allow_ips else ""
                if not raw_ips:
                    raise ValueError("FORWARDED_ALLOW_IPS must be explicitly specified in production")
                entries = [p.strip() for p in raw_ips.split(",") if p.strip()]
                if not entries:
                    raise ValueError("FORWARDED_ALLOW_IPS must contain at least one valid IP or CIDR in production")
                for entry in entries:
                    if entry in {"*", "all"}:
                        raise ValueError(f"FORWARDED_ALLOW_IPS must not trust all IPs or wildcard '{entry}' in production")
                    try:
                        if "/" in entry:
                            net = ipaddress.ip_network(entry, strict=False)
                            if net.prefixlen == 0:
                                raise ValueError(
                                    f"FORWARDED_ALLOW_IPS must not trust broad network prefix /0 ('{entry}') in production"
                                )
                        else:
                            ipaddress.ip_address(entry)
                    except ValueError as err:
                        raise ValueError(f"Invalid IP or CIDR in FORWARDED_ALLOW_IPS: '{entry}'") from err

                # Check weak / default secrets
                for name, secret in [
                    ("JWT_SIGNING_KEY", self.jwt_signing_key),
                    ("ADMIN_JWT_SIGNING_KEY", self.admin_jwt_signing_key),
                    ("AUTH_CHALLENGE_HASH_KEY", self.auth_challenge_hash_key),
                    ("SMS_OTP_HASH_KEY", self.sms_otp_hash_key),
                    ("WAPPI_WEBHOOK_AUTH_SECRET", self.wappi_webhook_auth_secret),
                ]:
                    if _is_weak_secret(secret):
                        raise ValueError(f"{name} uses an insecure or default secret forbidden in production")

                for raw_origin in self.admin_allowed_origins:
                    if not raw_origin.strip().startswith("https://"):
                        raise ValueError(f"All ADMIN_ALLOWED_ORIGINS must use HTTPS in production: '{raw_origin}'")

        # CORS and cookie origins are exact HTTP(S) origins, never wildcard URLs.
        from urllib.parse import urlsplit

        normalized_origins: list[str] = []
        for raw_origin in self.admin_allowed_origins:
            origin = raw_origin.strip()
            try:
                parsed_origin = urlsplit(origin)
                hostname = parsed_origin.hostname
                port = parsed_origin.port
            except ValueError as err:
                raise ValueError("ADMIN_ALLOWED_ORIGINS contains an invalid origin") from err
            if (
                not hostname
                or parsed_origin.username
                or parsed_origin.password
                or parsed_origin.path
                or parsed_origin.query
                or parsed_origin.fragment
                or parsed_origin.scheme not in {"https", "http"}
            ):
                raise ValueError("ADMIN_ALLOWED_ORIGINS must contain exact HTTP(S) origins, never wildcard URLs")
            if parsed_origin.scheme == "http" and (
                self.app_env.lower() not in {"test", "development"}
                or not self.admin_allow_insecure_http
            ):
                raise ValueError("HTTP admin origins require explicit development opt-in")
            default_port = (parsed_origin.scheme == "https" and port == 443) or (
                parsed_origin.scheme == "http" and port == 80
            )
            host = hostname.lower()
            authority = host if port is None or default_port else f"{host}:{port}"
            if ":" in host and not host.startswith("["):
                authority = f"[{host}]" if port is None or default_port else f"[{host}]:{port}"
            normalized_origins.append(f"{parsed_origin.scheme}://{authority}")
        if len(set(normalized_origins)) != len(normalized_origins):
            raise ValueError("ADMIN_ALLOWED_ORIGINS must not contain duplicate origins")
        self.admin_allowed_origins = normalized_origins

        # Validate WHATSAPP_LOGIN_NUMBER format (E.164)
        if not self.whatsapp_login_number or not self.whatsapp_login_number.strip():
            raise ValueError("WHATSAPP_LOGIN_NUMBER must be provided in environment or .env")
        self.whatsapp_login_number = self.whatsapp_login_number.strip()
        if not re.match(r"^\+[1-9]\d{7,14}$", self.whatsapp_login_number):
            raise ValueError(
                "WHATSAPP_LOGIN_NUMBER must be in valid E.164 format (+[1-9] followed by 7-14 digits, e.g. +77001234567)"
            )

        return self



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
