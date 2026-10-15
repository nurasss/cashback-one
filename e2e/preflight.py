"""Canonical E2E preflight (FIX-B).

Single implementation of destructive safety validation. Reads URLs from
environment (never CLI args to avoid ps/history leaks). Prints only safe
metadata (host/port/database, host/port/db). Fails closed before pytest.

Usage:
    python -m e2e.preflight
"""

from __future__ import annotations

import os
import sys

# Ensure repo root importable when run as module (runner sets PYTHONPATH already).
try:
    from e2e.harness import (
        E2ESafetyError,
        safe_db_info,
        safe_redis_info,
        validate_e2e_db_url,
        validate_redis_url,
    )
except Exception as exc:
    print("E2E preflight is not available.", file=sys.stderr)
    sys.exit(2)


def _resolve_db_url() -> str:
    return (
        os.environ.get("POSTGRES_E2E_URL", "").strip()
        or os.environ.get("POSTGRES_TEST_URL", "").strip()
        or ""
    )


def _resolve_redis_url() -> str:
    # Single source: REDIS_URL (REDIS_E2E_URL only if equal, else abort safe).
    r = os.environ.get("REDIS_URL", "").strip()
    e = os.environ.get("REDIS_E2E_URL", "").strip()
    if r and e and r != e:
        raise E2ESafetyError(
            "REDIS SAFETY ABORT: Conflicting REDIS_URL and REDIS_E2E_URL. Use single REDIS_URL."
        )
    return e or r or ""


async def _live_checks(db_url: str, redis_url: str) -> tuple[dict, dict]:
    """Non-destructive live verification. Raises E2ESafetyError with safe messages."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    import redis.asyncio as aioredis

    # Structural first (safe errors).
    validate_e2e_db_url(db_url)
    validate_redis_url(redis_url)

    # DB live: SELECT current_database() must match parsed.
    try:
        parsed = validate_e2e_db_url(db_url)
        expected = parsed.database or ""
    except E2ESafetyError:
        raise
    except Exception as exc:
        raise E2ESafetyError(
            "DATABASE SAFETY ABORT: PostgreSQL connection URL is not an E2E target."
        ) from exc

    try:
        engine = create_async_engine(db_url, echo=False)
    except Exception as exc:
        raise E2ESafetyError(
            "DATABASE SAFETY ABORT: PostgreSQL connection target is not an E2E target."
        ) from exc
    try:
        try:
            async with engine.connect() as conn:
                res = await conn.execute(text("SELECT current_database()"))
                actual = res.scalar()
        except Exception as exc:
            raise E2ESafetyError(
                "DATABASE SAFETY ABORT: PostgreSQL connection target is not reachable as E2E target."
            ) from exc
        if actual != expected:
            raise E2ESafetyError(
                "DATABASE SAFETY ABORT: PostgreSQL connection target does not match configured database."
            )
        # Prefix re-check on actual (safe generic).
        from e2e.harness import E2E_DB_PATTERN

        if not E2E_DB_PATTERN.match(str(actual)):
            raise E2ESafetyError(
                "DATABASE SAFETY ABORT: PostgreSQL database name is not an E2E target."
            )
    finally:
        try:
            await engine.dispose()
        except Exception:
            pass

    # Redis live: ping + empty check (non-destructive).
    try:
        info = validate_redis_url(redis_url)
    except E2ESafetyError:
        raise
    try:
        rc = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await rc.ping()
            size = await rc.dbsize()
        finally:
            try:
                await rc.aclose()
            except Exception:
                pass
    except E2ESafetyError:
        raise
    except Exception as exc:
        raise E2ESafetyError(
            "REDIS SAFETY ABORT: Redis E2E target is not reachable."
        ) from exc
    if size != 0:
        raise E2ESafetyError("REDIS SAFETY ABORT: Redis E2E database is not empty.")

    return safe_db_info(db_url), safe_redis_info(redis_url)


def main() -> int:
    import asyncio

    db_url = _resolve_db_url()
    redis_url = _resolve_redis_url()
    if not db_url:
        print("DATABASE SAFETY ABORT: Missing E2E database URL.", file=sys.stderr)
        return 1
    if not redis_url:
        print("REDIS SAFETY ABORT: Missing E2E Redis URL.", file=sys.stderr)
        return 1
    try:
        db_info, redis_info = asyncio.run(_live_checks(db_url, redis_url))
    except E2ESafetyError as exc:
        # Safe reason only (E2ESafetyError messages are credential-safe by construction).
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        # Never echo raw URLs on unexpected failure.
        print("E2E SAFETY ABORT: Preflight failed for E2E target.", file=sys.stderr)
        return 1

    # Success: safe metadata only.
    print(
        f"E2E DB target: host={db_info.get('host')} port={db_info.get('port')} "
        f"database={db_info.get('database')}"
    )
    print(
        f"E2E Redis target: host={redis_info.get('host')} port={redis_info.get('port')} "
        f"db={redis_info.get('db')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
