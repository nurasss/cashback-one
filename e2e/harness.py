"""End-to-End Test Harness for POSCENTER Loyalty Pre-ONE Integration (TASK-013).

Orchestrates:
1. Real PostgreSQL database validation (fail-closed, must contain 'test' or 'e2e').
2. Alembic schema migration.
3. Real Redis verification and test namespace flush.
4. Real Uvicorn ASGI backend subprocess with ephemeral cryptographic secrets.
5. Readiness polling with bounded waits.
6. Admin bootstrapping via internal service.
7. Subprocess and data cleanup on shutdown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import httpx
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


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
    redis_url: str = "redis://127.0.0.1:6379/15"

    jwt_signing_key: str = field(default_factory=lambda: secrets.token_hex(32))
    admin_jwt_signing_key: str = field(default_factory=lambda: secrets.token_hex(32))
    auth_challenge_hash_key: str = field(default_factory=lambda: secrets.token_hex(32))
    sms_otp_hash_key: str = field(default_factory=lambda: secrets.token_hex(32))
    wappi_secret: str = field(default_factory=lambda: secrets.token_hex(32))
    wappi_auth_header: str = "X-Wappi-Webhook-Signature"
    wappi_profile_id: str = "test-wappi-login-profile"

    superadmin_login: str = "superadmin@loyalty.test"
    superadmin_password: str = field(
        default_factory=lambda: f"SecretPass_{secrets.token_hex(8)}!Aa"
    )

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = f"http://127.0.0.1:{self.port}"


class E2EHarness:
    """Controls the end-to-end integration environment."""

    def __init__(self, config: E2EConfig | None = None) -> None:
        self.config = config or E2EConfig()
        self.repo_root = Path(__file__).resolve().parent.parent
        self.backend_dir = self.repo_root / "backend"

        # Resolve Database URL with safety constraints
        self.db_url = self._resolve_and_validate_db_url()
        self.config.db_url = self.db_url

        # Ensure in-process settings can initialize
        os.environ["DATABASE_URL"] = self.db_url
        os.environ["REDIS_URL"] = self.config.redis_url
        os.environ["APP_ENV"] = "test"
        os.environ["JWT_SIGNING_KEY"] = self.config.jwt_signing_key
        os.environ["ADMIN_JWT_SIGNING_KEY"] = self.config.admin_jwt_signing_key
        os.environ["AUTH_CHALLENGE_HASH_KEY"] = self.config.auth_challenge_hash_key
        os.environ["SMS_OTP_HASH_KEY"] = self.config.sms_otp_hash_key
        os.environ["WAPPI_WEBHOOK_AUTH_SECRET"] = self.config.wappi_secret
        os.environ["WAPPI_WEBHOOK_AUTH_HEADER"] = self.config.wappi_auth_header
        os.environ["WAPPI_LOGIN_PROFILE_ID"] = self.config.wappi_profile_id
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

    def _resolve_and_validate_db_url(self) -> str:
        """Resolve database URL and enforce strict safety requirements."""
        url = (
            os.environ.get("POSTGRES_E2E_URL")
            or os.environ.get("POSTGRES_TEST_URL")
            or "postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_e2e_test"
        )

        parsed = urlparse(url)
        db_name = parsed.path.lstrip("/").lower()

        # Database safety check: MUST contain 'test' or 'e2e'
        if "test" not in db_name and "e2e" not in db_name:
            raise RuntimeError(
                f"DATABASE SAFETY ABORT: Database name '{db_name}' does not contain 'test' or 'e2e'. "
                "Refusing to execute E2E harness against potentially non-test databases."
            )

        # Environment safety check
        app_env = os.environ.get("APP_ENV", "test").strip().lower()
        if app_env == "production":
            raise RuntimeError(
                "ENVIRONMENT SAFETY ABORT: APP_ENV is set to 'production'. "
                "Refusing to execute E2E harness in production mode."
            )

        return url

    async def setup(self) -> None:
        """Prepare database, redis, backend process, and bootstrap superadmin."""
        logger.info("Initializing Pre-ONE E2E Harness on port %d...", self.config.port)

        # 1. Verify Redis connectivity & flush test db
        await self._verify_and_flush_redis()

        # 2. Run Alembic migrations to head
        self._run_alembic_migrations()

        # 3. Initialize DB engine for test bootstrapping
        self._engine = create_async_engine(self.db_url, echo=False)
        self._sessionmaker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

        # 4. Truncate tables for fresh state
        await self.clean_database_tables()

        # 5. Bootstrap initial Superadmin
        await self.bootstrap_superadmin()

        # 6. Start Uvicorn backend process
        await self._start_backend()

    async def _verify_and_flush_redis(self) -> None:
        """Ensure Redis is accessible and clear the dedicated test db."""
        try:
            r = aioredis.from_url(self.config.redis_url)
            await r.ping()
            await r.flushdb()
            await r.aclose()
        except Exception as exc:
            raise RuntimeError(
                f"REDIS CONNECTIVITY FAILED for '{self.config.redis_url}': {exc}. "
                "Ensure Redis is running (e.g. `redis-server --daemonize yes` or docker run redis:7)."
            ) from exc

    def _run_alembic_migrations(self) -> None:
        """Apply all Alembic migrations up to head."""
        logger.info("Applying Alembic migrations to %s...", self.db_url)
        env = {
            **os.environ,
            "APP_ENV": "test",
            "DATABASE_URL": self.db_url,
            "REDIS_URL": self.config.redis_url,
            "JWT_SIGNING_KEY": self.config.jwt_signing_key,
            "ADMIN_JWT_SIGNING_KEY": self.config.admin_jwt_signing_key,
            "AUTH_CHALLENGE_HASH_KEY": self.config.auth_challenge_hash_key,
            "SMS_OTP_HASH_KEY": self.config.sms_otp_hash_key,
            "WAPPI_WEBHOOK_AUTH_SECRET": self.config.wappi_secret,
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
        self._backend_log_file = open(self.backend_log_path, "wb")

        env = {
            **os.environ,
            "APP_ENV": "test",
            "DEBUG": "false",
            "DATABASE_URL": self.db_url,
            "REDIS_URL": self.config.redis_url,
            "JWT_SIGNING_KEY": self.config.jwt_signing_key,
            "ADMIN_JWT_SIGNING_KEY": self.config.admin_jwt_signing_key,
            "AUTH_CHALLENGE_HASH_KEY": self.config.auth_challenge_hash_key,
            "SMS_OTP_HASH_KEY": self.config.sms_otp_hash_key,
            "WAPPI_WEBHOOK_AUTH_SECRET": self.config.wappi_secret,
            "WAPPI_WEBHOOK_AUTH_HEADER": self.config.wappi_auth_header,
            "WAPPI_LOGIN_PROFILE_ID": self.config.wappi_profile_id,
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
        self._backend_log_file.flush()
        with open(self.backend_log_path, "r", errors="replace") as f:
            logs = f.read()

        await self.teardown()
        raise RuntimeError(
            f"BACKEND FAILED TO BECOME READY at {ready_url} within {timeout}s.\nLogs:\n{logs}"
        )

    def scan_logs_for_secrets(self, sensitive_strings: list[str]) -> list[str]:
        """Scan backend log output for prohibited cleartext secrets."""
        if not self.backend_log_path.exists():
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

    async def teardown(self) -> None:
        """Gracefully shut down backend subprocess, clean temporary assets, and close DB engine."""
        logger.info("Tearing down Pre-ONE E2E Harness...")

        # 1. Terminate backend process
        if self._backend_proc and self._backend_proc.poll() is None:
            self._backend_proc.terminate()
            try:
                self._backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._backend_proc.kill()
                self._backend_proc.wait()
            self._backend_proc = None

        if self._backend_log_file and not self._backend_log_file.closed:
            self._backend_log_file.close()

        # 2. Close DB engine
        if self._engine:
            await self._engine.dispose()
            self._engine = None

        # 3. Clean Redis test db
        try:
            r = aioredis.from_url(self.config.redis_url)
            await r.flushdb()
            await r.aclose()
        except Exception:
            pass

        # 4. Remove temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("E2E Teardown complete.")
