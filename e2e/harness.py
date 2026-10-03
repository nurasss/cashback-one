"""End-to-End Test Harness for POSCENTER Loyalty Pre-ONE Integration (TASK-013 FIX-A).

Safety model (FIX-A):
- Database target is structurally parsed with SQLAlchemy ``make_url`` (never substring).
- ``POSTGRES_E2E_URL`` must have zero query params, explicit ``cashback_e2e_`` prefix,
  allowed local/CI host, and ``SELECT current_database()`` must match parsed DB
  BEFORE any migration/TRUNCATE.
- Redis single source of truth is ``REDIS_URL``. Harness, backend and cleanup use
  exactly the same resolved URL. DB0 rejected, non-empty DB refused, FLUSHDB only
  on dedicated verified DB.
- Backend runs in ``development`` mode with ephemeral secrets so real
  RedisRateLimiter is exercised (no InMemory shortcut).
- ``cleanup()``/``teardown()`` are idempotent and handle partial init.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical safety policy
# ---------------------------------------------------------------------------

E2E_DB_PREFIX = "cashback_e2e_"
E2E_DB_PATTERN = re.compile(r"^cashback_e2e_[a-z0-9_]{1,32}$")
E2E_DB_MAX_LEN = 63

ALLOWED_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres"})
ALLOWED_REDIS_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "redis", "postgres"})

# Canonical E2E runtime mode: real Redis limiter, explicit local HTTP behaviour.
E2E_APP_ENV = "development"

DEFAULT_E2E_DB_URL = "postgresql+asyncpg://nuras@localhost:5432/cashback_e2e_local"
DEFAULT_E2E_REDIS_URL = "redis://127.0.0.1:6379/14"


def _abort(prefix: str, msg: str) -> RuntimeError:
    return RuntimeError(f"{prefix}: {msg}")


def validate_e2e_db_url(url: str) -> Any:
    """Structurally validate canonical E2E PostgreSQL URL.

    Returns SQLAlchemy URL object on success, raises RuntimeError on reject.
    """
    if not url or not url.strip():
        raise _abort("DATABASE SAFETY ABORT", "Empty database URL.")
    raw = url.strip()
    try:
        parsed = make_url(raw)
    except Exception as exc:
        raise _abort("DATABASE SAFETY ABORT", f"Unparsable database URL: {exc}") from exc

    driver = (parsed.drivername or "").lower()
    if driver != "postgresql+asyncpg":
        raise _abort(
            "DATABASE SAFETY ABORT",
            f"Unsupported driver '{parsed.drivername}'. Expected 'postgresql+asyncpg'.",
        )

    db_name = parsed.database or ""
    if not db_name:
        raise _abort("DATABASE SAFETY ABORT", "Missing explicit database name.")
    # Strict prefix policy — never substring.
    if not E2E_DB_PATTERN.match(db_name):
        raise _abort(
            "DATABASE SAFETY ABORT",
            f"Database name '{db_name}' does not match strict E2E policy "
            f"'{E2E_DB_PREFIX}<run-id>' ([a-z0-9_], max 32 suffix). Refusing.",
        )
    if len(db_name) > E2E_DB_MAX_LEN:
        raise _abort("DATABASE SAFETY ABORT", f"Database name too long: '{db_name}'.")

    # Disallow any query overrides — safest: must be empty.
    query = dict(parsed.query) if parsed.query else {}
    if query:
        raise _abort(
            "DATABASE SAFETY ABORT",
            f"Query parameters forbidden in E2E DB URL (got {sorted(query)}). "
            "Refusing to run with ambiguous target overrides.",
        )

    host = (parsed.host or "").strip()
    # make_url may return None host for socket URLs — reject.
    if not host:
        raise _abort("DATABASE SAFETY ABORT", "Missing explicit database host.")
    if host.lower() not in ALLOWED_DB_HOSTS:
        raise _abort(
            "DATABASE SAFETY ABORT",
            f"Database host '{host}' not in E2E allowlist {sorted(ALLOWED_DB_HOSTS)}.",
        )

    # Environment must never be production.
    app_env = os.environ.get("APP_ENV", "").strip().lower()
    if app_env == "production":
        raise _abort(
            "ENVIRONMENT SAFETY ABORT",
            "APP_ENV is 'production'. Refusing E2E harness in production mode.",
        )
    return parsed


def safe_db_info(url: str) -> dict[str, Any]:
    """Return safe display components (host/port/name) without credentials."""
    parsed = make_url(url)
    return {
        "host": parsed.host,
        "port": parsed.port or 5432,
        "database": parsed.database,
        "driver": parsed.drivername,
    }


def validate_redis_url(url: str) -> dict[str, Any]:
    """Validate canonical E2E Redis URL. Returns {host, port, db}. Raises on reject."""
    if not url or not url.strip():
        raise _abort("REDIS SAFETY ABORT", "Empty Redis URL.")
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "redis":
        raise _abort(
            "REDIS SAFETY ABORT",
            f"Unsupported Redis scheme '{parsed.scheme}'. Expected 'redis://'.",
        )
    host = (parsed.hostname or "").strip()
    if not host or host.lower() not in ALLOWED_REDIS_HOSTS:
        raise _abort(
            "REDIS SAFETY ABORT",
            f"Redis host '{host or '<empty>'}' not in allowlist {sorted(ALLOWED_REDIS_HOSTS)}.",
        )
    port = parsed.port or 6379
    # Path must be /<db>
    path = (parsed.path or "").strip()
    if not path or path == "/":
        raise _abort("REDIS SAFETY ABORT", "Missing Redis DB index (e.g. redis://host:6379/14).")
    db_part = path.lstrip("/")
    # Reject extra path segments like /14/extra
    if "/" in db_part:
        raise _abort("REDIS SAFETY ABORT", f"Invalid Redis path '{path}'. Expected '/<db>'.")
    try:
        db_index = int(db_part)
    except ValueError as exc:
        raise _abort("REDIS SAFETY ABORT", f"Invalid Redis DB index '{db_part}'.") from exc
    if db_index == 0:
        raise _abort("REDIS SAFETY ABORT", "Redis DB0 is unsafe for destructive E2E cleanup. Use dedicated non-zero DB (e.g. 14).")
    if not (1 <= db_index <= 15):
        raise _abort("REDIS SAFETY ABORT", f"Redis DB index {db_index} out of allowed 1..15.")
    if parsed.query:
        raise _abort(
            "REDIS SAFETY ABORT",
            f"Query parameters forbidden in E2E Redis URL (got '{parsed.query}').",
        )
    return {"host": host, "port": port, "db": db_index}


def safe_redis_info(url: str) -> dict[str, Any]:
    info = validate_redis_url(url)
    return dict(info)


def find_free_port() -> int:
    """Find a random available port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class E2EConfig:
    """Configuration and ephemeral secrets for an E2E run."""

    port: int = field(default_factory=find_free_port)
    base_url: str = ""
    db_url: str = ""
    redis_url: str = DEFAULT_E2E_REDIS_URL

    jwt_signing_key: str = field(default_factory=lambda: secrets.token_hex(32))
    admin_jwt_signing_key: str = field(default_factory=lambda: secrets.token_hex(32))
    auth_challenge_hash_key: str = field(default_factory=lambda: secrets.token_hex(32))
    sms_otp_hash_key: str = field(default_factory=lambda: secrets.token_hex(32))
    wappi_secret: str = field(default_factory=lambda: secrets.token_hex(32))
    wappi_auth_header: str = "X-Wappi-Webhook-Signature"
    wappi_profile_id: str = "test-wappi-login-profile"
    whatsapp_login_number: str = "+77001234567"

    superadmin_login: str = "superadmin@loyalty.test"
    superadmin_password: str = field(
        default_factory=lambda: f"SecretPass_{secrets.token_hex(8)}!Aa"
    )

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = f"http://127.0.0.1:{self.port}"
        # Single source of truth: REDIS_URL. Detect conflicting declarations.
        env_redis = os.environ.get("REDIS_URL", "").strip()
        env_e2e_redis = os.environ.get("REDIS_E2E_URL", "").strip()
        if env_redis and env_e2e_redis and env_redis != env_e2e_redis:
            raise RuntimeError(
                "REDIS SAFETY ABORT: Conflicting REDIS_URL and REDIS_E2E_URL "
                f"('{env_redis}' vs '{env_e2e_redis}'). Use single REDIS_URL."
            )
        resolved = env_e2e_redis or env_redis or self.redis_url
        # Validate eagerly so misconfiguration fails fast.
        validate_redis_url(resolved)
        self.redis_url = resolved


class E2EHarness:
    """Controls the end-to-end integration environment."""

    def __init__(self, config: E2EConfig | None = None) -> None:
        self.config = config or E2EConfig()
        self.repo_root = Path(__file__).resolve().parent.parent
        self.backend_dir = self.repo_root / "backend"

        # Resolve Database URL with strict structural safety.
        self.db_url = self._resolve_and_validate_db_url()
        self.config.db_url = self.db_url
        # Resolve Redis URL single source of truth (already validated in config).
        self.redis_url = self.config.redis_url
        # Re-validate Redis explicitly (host/DB0/query).
        validate_redis_url(self.redis_url)

        # Ensure in-process settings can initialize (development = real Redis).
        os.environ["DATABASE_URL"] = self.db_url
        os.environ["REDIS_URL"] = self.redis_url
        os.environ["APP_ENV"] = E2E_APP_ENV
        os.environ["JWT_SIGNING_KEY"] = self.config.jwt_signing_key
        os.environ["ADMIN_JWT_SIGNING_KEY"] = self.config.admin_jwt_signing_key
        os.environ["AUTH_CHALLENGE_HASH_KEY"] = self.config.auth_challenge_hash_key
        os.environ["SMS_OTP_HASH_KEY"] = self.config.sms_otp_hash_key
        os.environ["WAPPI_WEBHOOK_AUTH_SECRET"] = self.config.wappi_secret
        os.environ["WAPPI_WEBHOOK_AUTH_HEADER"] = self.config.wappi_auth_header
        os.environ["WAPPI_LOGIN_PROFILE_ID"] = self.config.wappi_profile_id
        os.environ["WHATSAPP_LOGIN_NUMBER"] = self.config.whatsapp_login_number
        os.environ["ADMIN_ALLOWED_ORIGINS"] = json.dumps([self.config.base_url])
        os.environ["ADMIN_ALLOW_INSECURE_HTTP"] = "true"
        os.environ["SMS_PROVIDER_MODE"] = "disabled"
        os.environ["FORWARDED_ALLOW_IPS"] = "127.0.0.1"

        self.temp_dir = Path(tempfile.mkdtemp(prefix="poscenter_e2e_"))
        self.backend_log_path = self.temp_dir / "backend.log"
        self._backend_proc: subprocess.Popen[bytes] | None = None
        self._backend_log_file: Any = None
        self._engine: Any = None
        self._sessionmaker: Any = None

        # Verified immutable target state (set only after live verification).
        self._database_verified: bool = False
        self._verified_db_name: str | None = None
        self._verified_db_host: str | None = None
        self._verified_db_port: int | None = None
        self._redis_verified: bool = False
        self._redis_dedicated: bool = False
        self._verified_redis_host: str | None = None
        self._verified_redis_port: int | None = None
        self._verified_redis_db: int | None = None

    def _resolve_and_validate_db_url(self) -> str:
        """Resolve database URL and enforce strict structural safety."""
        url = (
            os.environ.get("POSTGRES_E2E_URL")
            or os.environ.get("POSTGRES_TEST_URL")
            or DEFAULT_E2E_DB_URL
        )
        validate_e2e_db_url(url)
        # Environment safety check (also inside validator, kept for clarity).
        app_env = os.environ.get("APP_ENV", "").strip().lower()
        if app_env == "production":
            raise RuntimeError(
                "ENVIRONMENT SAFETY ABORT: APP_ENV is set to 'production'. "
                "Refusing to execute E2E harness in production mode."
            )
        return url

    async def _verify_actual_database(self) -> None:
        """Connect read-only and verify SELECT current_database() matches parsed URL.

        Must run BEFORE migrations/TRUNCATE. Sets immutable verified state.
        """
        parsed = validate_e2e_db_url(self.db_url)
        expected_db: str = parsed.database or ""
        # Use a short-lived engine for verification if main engine not yet ready.
        engine = create_async_engine(self.db_url, echo=False)
        try:
            async with engine.connect() as conn:
                res = await conn.execute(text("SELECT current_database()"))
                actual = res.scalar()
            if actual != expected_db:
                raise RuntimeError(
                    "DATABASE SAFETY ABORT: "
                    f"SELECT current_database()='{actual}' != parsed URL.database='{expected_db}'. Refusing."
                )
            if not E2E_DB_PATTERN.match(str(actual)):
                raise RuntimeError(
                    f"DATABASE SAFETY ABORT: actual database '{actual}' fails strict E2E prefix policy."
                )
            self._database_verified = True
            self._verified_db_name = str(actual)
            self._verified_db_host = parsed.host
            self._verified_db_port = parsed.port or 5432
        finally:
            await engine.dispose()

    async def setup(self) -> None:
        """Prepare database, redis, backend process, and bootstrap superadmin."""
        logger.info("Initializing Pre-ONE E2E Harness on port %d...", self.config.port)

        # 0. Verify actual connected database BEFORE any destructive work.
        await self._verify_actual_database()

        # 1. Verify Redis is dedicated/empty (refuse if not empty; never flush arbitrary DB).
        await self._verify_redis_dedicated_empty()

        # 2. Run Alembic migrations to head
        self._run_alembic_migrations()

        # 3. Initialize DB engine for test bootstrapping
        self._engine = create_async_engine(self.db_url, echo=False)
        self._sessionmaker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

        # 4. Truncate tables for fresh state (requires verified target).
        await self.clean_database_tables()

        # 5. Bootstrap initial Superadmin
        await self.bootstrap_superadmin()

        # 6. Start Uvicorn backend process
        await self._start_backend()

    async def _verify_redis_dedicated_empty(self) -> None:
        """Ensure Redis target is allowed, exact DB, and EMPTY. Refuse otherwise."""
        info = validate_redis_url(self.redis_url)
        host, port, db = info["host"], info["port"], info["db"]
        try:
            r = aioredis.from_url(self.redis_url, decode_responses=True)
            try:
                await r.ping()
                size = await r.dbsize()
            finally:
                try:
                    await r.aclose()
                except Exception:
                    pass
        except Exception as exc:
            raise RuntimeError(
                f"REDIS CONNECTIVITY FAILED for host={host} port={port} db={db}: {exc}. "
                "Ensure Redis is running."
            ) from exc
        if size != 0:
            raise RuntimeError(
                f"REDIS SAFETY ABORT: Redis DB host={host} port={port} db={db} "
                f"is not empty (DBSIZE={size}). Refusing to run on non-dedicated DB."
            )
        self._redis_verified = True
        self._redis_dedicated = True
        self._verified_redis_host = host
        self._verified_redis_port = port
        self._verified_redis_db = db

    async def _verify_and_flush_redis(self) -> None:
        """Backward-compat entry: now verifies dedicated-empty (no arbitrary flush)."""
        await self._verify_redis_dedicated_empty()

    def _run_alembic_migrations(self) -> None:
        """Apply all Alembic migrations up to head."""
        if not self._database_verified:
            raise RuntimeError("DATABASE SAFETY ABORT: migrations require verified database target.")
        info = safe_db_info(self.db_url)
        logger.info(
            "Applying Alembic migrations to host=%s port=%s db=%s...",
            info["host"],
            info["port"],
            info["database"],
        )
        env = {
            **os.environ,
            "APP_ENV": E2E_APP_ENV,
            "DATABASE_URL": self.db_url,
            "REDIS_URL": self.redis_url,
            "JWT_SIGNING_KEY": self.config.jwt_signing_key,
            "ADMIN_JWT_SIGNING_KEY": self.config.admin_jwt_signing_key,
            "AUTH_CHALLENGE_HASH_KEY": self.config.auth_challenge_hash_key,
            "SMS_OTP_HASH_KEY": self.config.sms_otp_hash_key,
            "WAPPI_WEBHOOK_AUTH_SECRET": self.config.wappi_secret,
            "WAPPI_WEBHOOK_AUTH_HEADER": self.config.wappi_auth_header,
            "WAPPI_LOGIN_PROFILE_ID": self.config.wappi_profile_id,
            "WHATSAPP_LOGIN_NUMBER": self.config.whatsapp_login_number,
            "ADMIN_ALLOWED_ORIGINS": json.dumps([self.config.base_url]),
            "ADMIN_ALLOW_INSECURE_HTTP": "true",
            "SMS_PROVIDER_MODE": "disabled",
            "FORWARDED_ALLOW_IPS": "127.0.0.1",
        }

        res = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(self.backend_dir),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Alembic upgrade failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            )

    async def clean_database_tables(self) -> None:
        """Truncate all application data tables to ensure hermetic state."""
        if not self._database_verified:
            raise RuntimeError(
                "DATABASE SAFETY ABORT: clean_database_tables requires verified database target. Refusing."
            )
        if self._engine is None:
            raise RuntimeError("DATABASE SAFETY ABORT: DB engine not initialized.")
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    TRUNCATE TABLE
                        agent_commands,
                        audit_log,
                        admin_sessions,
                        admin_users,
                        wappi_webhook_events,
                        transactions,
                        user_cards,
                        cards,
                        agents,
                        login_challenges,
                        otp_codes,
                        auth_sessions,
                        devices,
                        consents,
                        users,
                        businesses
                    CASCADE;
                    """
                )
            )

    async def bootstrap_superadmin(self) -> None:
        """Create superadmin credentials directly into database."""
        from app.cli.create_admin import provision_admin

        async with self._sessionmaker() as session:
            await provision_admin(
                session=session,
                login=self.config.superadmin_login,
                password=self.config.superadmin_password,
                role="superadmin",
                business_id=None,
            )

    async def bootstrap_manager(
        self, login: str, password: str, business_id: UUID
    ) -> None:
        """Create a business manager directly into database."""
        from app.cli.create_admin import provision_admin

        async with self._sessionmaker() as session:
            await provision_admin(
                session=session,
                login=login,
                password=password,
                role="business_manager",
                business_id=business_id,
            )

    async def _start_backend(self) -> None:
        """Spawn the real Uvicorn ASGI backend process and wait for ready status."""
        logger.info(
            "Starting Uvicorn backend process at %s...", self.config.base_url
        )
        # Ensure log file handle exists even if temp_dir was cleaned unexpectedly.
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._backend_log_file = open(self.backend_log_path, "wb")

        env = {
            **os.environ,
            "APP_ENV": E2E_APP_ENV,
            "DEBUG": "false",
            "DATABASE_URL": self.db_url,
            "REDIS_URL": self.redis_url,
            "JWT_SIGNING_KEY": self.config.jwt_signing_key,
            "ADMIN_JWT_SIGNING_KEY": self.config.admin_jwt_signing_key,
            "AUTH_CHALLENGE_HASH_KEY": self.config.auth_challenge_hash_key,
            "SMS_OTP_HASH_KEY": self.config.sms_otp_hash_key,
            "WAPPI_WEBHOOK_AUTH_SECRET": self.config.wappi_secret,
            "WAPPI_WEBHOOK_AUTH_HEADER": self.config.wappi_auth_header,
            "WAPPI_LOGIN_PROFILE_ID": self.config.wappi_profile_id,
            "WHATSAPP_LOGIN_NUMBER": self.config.whatsapp_login_number,
            "ADMIN_ALLOWED_ORIGINS": json.dumps(
                [self.config.base_url, f"http://localhost:{self.config.port}"]
            ),
            "ADMIN_ALLOW_INSECURE_HTTP": "true",
            "SMS_PROVIDER_MODE": "disabled",
            "FORWARDED_ALLOW_IPS": "127.0.0.1",
            "PYTHONPATH": f"{self.backend_dir}:{os.environ.get('PYTHONPATH', '')}",
        }

        python_bin = sys.executable
        self._backend_proc = subprocess.Popen(
            [
                python_bin,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.config.port),
                "--log-level",
                "info",
            ],
            cwd=str(self.backend_dir),
            env=env,
            stdout=self._backend_log_file,
            stderr=subprocess.STDOUT,
        )

        # Bounded readiness poll (up to 15 seconds)
        ready_url = f"{self.config.base_url}/health/ready"
        start_time = time.monotonic()
        timeout = 15.0

        async with httpx.AsyncClient() as client:
            while time.monotonic() - start_time < timeout:
                if self._backend_proc.poll() is not None:
                    break
                try:
                    resp = await client.get(ready_url, timeout=1.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "ready":
                            logger.info("Backend is READY at %s", self.config.base_url)
                            return
                except Exception:
                    pass
                await asyncio.sleep(0.3)

        # Failed to become ready: diagnose and raise
        try:
            if self._backend_log_file:
                self._backend_log_file.flush()
            with open(self.backend_log_path, "r", errors="replace") as f:
                logs = f.read()
        except Exception:
            logs = "<unavailable>"

        await self.teardown()
        raise RuntimeError(
            f"BACKEND FAILED TO BECOME READY at {ready_url} within {timeout}s.\nLogs:\n{logs}"
        )

    def scan_logs_for_secrets(self, sensitive_strings: list[str]) -> list[str]:
        """Scan backend log output for prohibited cleartext secrets."""
        try:
            if not self.backend_log_path.exists():
                return []
        except Exception:
            return []
        with open(self.backend_log_path, "r", errors="replace") as f:
            log_content = f.read()

        found: list[str] = []
        for secret_str in sensitive_strings:
            if not secret_str or len(secret_str) < 6:
                continue
            if secret_str in log_content:
                found.append(secret_str)
        return found

    async def cleanup(self) -> None:
        """Idempotent cleanup handling partially-initialized resources."""
        logger.info("Tearing down Pre-ONE E2E Harness...")

        # 1. Terminate backend process
        try:
            proc = self._backend_proc
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            pass
                except Exception:
                    pass
        finally:
            self._backend_proc = None

        if self._backend_log_file is not None:
            try:
                if not self._backend_log_file.closed:
                    try:
                        self._backend_log_file.close()
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self._backend_log_file = None

        # 2. Close DB engine
        if self._engine is not None:
            try:
                await self._engine.dispose()
            except Exception:
                pass
            finally:
                self._engine = None
        self._sessionmaker = None

        # 3. Clean Redis test db ONLY if dedicated verified same target.
        try:
            if self._redis_dedicated and self._redis_verified:
                try:
                    current = validate_redis_url(self.redis_url)
                except Exception:
                    current = None
                if (
                    current
                    and current["host"] == self._verified_redis_host
                    and current["port"] == self._verified_redis_port
                    and current["db"] == self._verified_redis_db
                ):
                    try:
                        r = aioredis.from_url(self.redis_url)
                        try:
                            await r.flushdb()
                        finally:
                            try:
                                await r.aclose()
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self._redis_dedicated = False
            self._redis_verified = False

        # 4. Remove temp directory
        try:
            tmp = getattr(self, "temp_dir", None)
            if tmp is not None:
                try:
                    p = Path(tmp)
                    if p.exists():
                        shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    pass
        except Exception:
            pass
        logger.info("E2E Teardown complete.")

    async def teardown(self) -> None:
        """Backward-compat alias for cleanup()."""
        await self.cleanup()
