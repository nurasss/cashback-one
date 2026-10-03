"""FIX-B resource safety tests: non-destructive, owned resources only, credential-safe.

Rules:
- Only DROP/FLUSH/DELETE resources THIS TEST created/proved ownership for.
- No fixed DB names, no fixed Redis DBs (except pure parsing strings, never connected).
- No cross-DB access: canonical REDIS_URL only.
- Unique UUID-based owned keys/DBs; cleanup deletes only owned.
- Failure messages never contain raw URLs/passwords/queries.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import uuid
from pathlib import Path

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from e2e.harness import (
    E2EConfig,
    E2EHarness,
    E2ESafetyError,
    safe_db_info,
    safe_redis_info,
    validate_e2e_db_url,
    validate_redis_url,
)


# ---------------------------------------------------------------------------
# Helpers: CI-compatible derivation (no hardcoded user/host)
# ---------------------------------------------------------------------------

def _canonical_pg_url() -> str:
    url = (
        os.environ.get("POSTGRES_E2E_URL", "").strip()
        or os.environ.get("POSTGRES_TEST_URL", "").strip()
        or ""
    )
    if not url:
        pytest.skip("POSTGRES_E2E_URL not configured")
    return url


def _canonical_redis_url() -> str:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        pytest.skip("REDIS_URL not configured")
    return url


def _pg_url_for_db(dbname: str) -> str:
    """Build URL for given DB using canonical user/host/port/password (never logged)."""
    base = _canonical_pg_url()
    try:
        u = make_url(base)
        # Preserve driver/user/password/host/port, replace database only.
        new_u = u.set(database=dbname)
        return str(new_u)
    except Exception as exc:
        pytest.fail(f"cannot derive PG URL: {type(exc).__name__}")


def _pg_maintenance_url() -> str:
    return _pg_url_for_db("postgres")


def _unique_e2e_db() -> str:
    return f"cashback_e2e_safety_{uuid.uuid4().hex[:10].lower()}"


def _unique_non_e2e_db() -> str:
    # Must NOT match ^cashback_e2e_ to prove refusal.
    return f"review_safety_{uuid.uuid4().hex[:10].lower()}"


def _unique_key(prefix: str = "e2e_safety") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def _pg_exec(url: str, sql: str, params: dict | None = None, autocommit: bool = False):
    if autocommit:
        eng = create_async_engine(url, echo=False, isolation_level="AUTOCOMMIT")
    else:
        eng = create_async_engine(url, echo=False)
    try:
        if autocommit:
            async with eng.connect() as conn:
                await conn.execute(text(sql), params or {})
        else:
            async with eng.begin() as conn:
                await conn.execute(text(sql), params or {})
    finally:
        await eng.dispose()


async def _pg_scalar(url: str, sql: str, params: dict | None = None):
    eng = create_async_engine(url, echo=False)
    try:
        async with eng.connect() as conn:
            res = await conn.execute(text(sql), params or {})
            return res.scalar()
    finally:
        await eng.dispose()


# ---------------------------------------------------------------------------
# Pure validation (no connections, safe IDs)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "dbname",
    ["latest", "contest", "production", "task_latest", "contest_db"],
    ids=["unsafe-latest", "unsafe-contest", "unsafe-production", "unsafe-task-latest", "unsafe-contest-db"],
)
def test_db_rejects_unsafe_names(dbname: str):
    url = f"postgresql+asyncpg://u:p@127.0.0.1:5432/{dbname}"
    with pytest.raises(E2ESafetyError, match="DATABASE SAFETY ABORT"):
        validate_e2e_db_url(url)


def test_db_rejects_query_override():
    # Safe ID, no raw URL in ID.
    url = "postgresql+asyncpg://u:p@127.0.0.1:5432/cashback_e2e_abc123?database=production"
    with pytest.raises(E2ESafetyError, match="query parameters"):
        validate_e2e_db_url(url)
    url2 = "postgresql+asyncpg://u:p@127.0.0.1:5432/cashback_e2e_abc123?host=evil&port=5433"
    with pytest.raises(E2ESafetyError, match="query parameters"):
        validate_e2e_db_url(url2)


def test_db_allows_canonical():
    validate_e2e_db_url("postgresql+asyncpg://u:p@127.0.0.1:5432/cashback_e2e_abc123")
    validate_e2e_db_url("postgresql+asyncpg://u:p@localhost:5432/cashback_e2e_ci")
    info = safe_db_info("postgresql+asyncpg://u:p@127.0.0.1:5432/cashback_e2e_x1")
    assert info["host"] == "127.0.0.1"
    assert info["database"] == "cashback_e2e_x1"


def test_db_rejects_remote_host():
    with pytest.raises(E2ESafetyError, match="SAFETY ABORT"):
        validate_e2e_db_url("postgresql+asyncpg://u:p@prod.example.com:5432/cashback_e2e_x1")


def test_redis_rejects_db0():
    # Pure validation, never connects to DB0.
    with pytest.raises(E2ESafetyError, match="DB 0"):
        validate_redis_url("redis://127.0.0.1:6379/0")


def test_redis_rejects_missing_and_query():
    with pytest.raises(E2ESafetyError, match="Missing Redis DB"):
        validate_redis_url("redis://127.0.0.1:6379")
    with pytest.raises(E2ESafetyError, match="query parameters"):
        validate_redis_url("redis://127.0.0.1:6379/14?foo=bar")


def test_redis_allows_canonical_and_safe_display(monkeypatch):
    info = safe_redis_info("redis://127.0.0.1:6379/14")
    assert info == {"host": "127.0.0.1", "port": 6379, "db": 14}
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/14")
    monkeypatch.delenv("REDIS_E2E_URL", raising=False)
    cfg = E2EConfig()
    assert cfg.redis_url == "redis://127.0.0.1:6379/14"


def test_redis_conflicting_sources_rejected(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/14")
    monkeypatch.setenv("REDIS_E2E_URL", "redis://127.0.0.1:6379/14")
    # Same is allowed; different must abort without echoing URLs.
    monkeypatch.setenv("REDIS_E2E_URL", "redis://127.0.0.1:6379/13")
    with pytest.raises(E2ESafetyError, match="Conflicting"):
        E2EConfig()


def test_safe_display_never_contains_password():
    db_info = safe_db_info("postgresql+asyncpg://bob:pw123@127.0.0.1:5432/cashback_e2e_t1")
    assert "pw123" not in str(db_info)
    assert "bob" not in str(db_info)
    rd = safe_redis_info("redis://127.0.0.1:6379/14")
    assert set(rd.keys()) == {"host", "port", "db"}


def test_db_failure_hides_marker_password():
    marker = f"marker-db-pw-{uuid.uuid4().hex[:8]}"
    url = f"postgresql+asyncpg://u:{marker}@127.0.0.1:5432/cashback_e2e_x1?database=production"
    try:
        validate_e2e_db_url(url)
        pytest.fail("expected refusal")
    except E2ESafetyError as exc:
        assert marker not in str(exc)


def test_redis_failure_hides_marker_secret():
    marker = f"marker-redis-{uuid.uuid4().hex[:8]}"
    url = f"redis://127.0.0.1:6379/14?password={marker}"
    try:
        validate_redis_url(url)
        pytest.fail("expected refusal")
    except E2ESafetyError as exc:
        assert marker not in str(exc)


# ---------------------------------------------------------------------------
# PostgreSQL ownership: only test-created DB may be dropped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pg_owned_lifecycle_create_and_drop():
    """Create unique owned E2E DB, verify ownership, drop only owned."""
    dbname = _unique_e2e_db()
    maint = _pg_maintenance_url()
    created_by_this_test = False
    try:
        try:
            await _pg_exec(maint, f'CREATE DATABASE "{dbname}"', autocommit=True)
        except Exception as exc:
            msg = str(exc).lower()
            if "permission denied" in msg or "must be" in msg:
                pytest.fail(f"PG role lacks CREATEDB for safety test: {type(exc).__name__}")
            if "already exists" in msg:
                # Collision: do NOT adopt. Generate another (fail to surface).
                pytest.fail("owned DB name collision; refusing to adopt existing DB")
            raise
        created_by_this_test = True
        # Prove we own it: write sentinel via owned URL.
        owned_url = _pg_url_for_db(dbname)
        await _pg_exec(owned_url, "CREATE TABLE IF NOT EXISTS sentinel(id INT PRIMARY KEY, v TEXT)")
        await _pg_exec(owned_url, "DELETE FROM sentinel WHERE id=1")
        await _pg_exec(owned_url, "INSERT INTO sentinel(id,v) VALUES (1,'ownme')")
        v = await _pg_scalar(owned_url, "SELECT v FROM sentinel WHERE id=1")
        assert v == "ownme"
    finally:
        if created_by_this_test:
            try:
                # Terminate backends then drop owned only.
                await _pg_exec(maint, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:d AND pid<>pg_backend_pid()", {"d": dbname}, autocommit=True)
            except Exception:
                pass
            await _pg_exec(maint, f'DROP DATABASE IF EXISTS "{dbname}"', autocommit=True)
        else:
            # Never drop preexisting.
            pass


@pytest.mark.asyncio
async def test_pg_existing_db_never_adopted():
    """Simulate collision: existing DB must NOT be marked owned, never dropped."""
    dbname = _unique_e2e_db()
    maint = _pg_maintenance_url()
    # First create as owned.
    try:
        await _pg_exec(maint, f'CREATE DATABASE "{dbname}"', autocommit=True)
    except Exception as exc:
        pytest.skip(f"cannot create collision DB: {type(exc).__name__}")
    try:
        # Simulate second attempt with same name (collision).
        created_by_test = False
        try:
            await _pg_exec(maint, f'CREATE DATABASE "{dbname}"', autocommit=True)
            created_by_test = True  # Should not happen.
        except Exception as exc2:
            assert "already exists" in str(exc2).lower()
            created_by_test = False
        assert created_by_test is False
        # Helper must NOT drop: verify DB still exists.
        v = await _pg_scalar(maint, "SELECT 1 FROM pg_database WHERE datname=:d", {"d": dbname})
        assert v == 1
    finally:
        # Only original owner drops.
        try:
            await _pg_exec(maint, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:d AND pid<>pg_backend_pid()", {"d": dbname}, autocommit=True)
        except Exception:
            pass
        await _pg_exec(maint, f'DROP DATABASE IF EXISTS "{dbname}"', autocommit=True)


@pytest.mark.asyncio
async def test_non_e2e_refusal_preserves_owned_sentinel():
    """Own non-E2E DB + sentinel; validation refuses; sentinel survives; drop owned."""
    dbname = _unique_non_e2e_db()
    maint = _pg_maintenance_url()
    try:
        await _pg_exec(maint, f'CREATE DATABASE "{dbname}"', autocommit=True)
    except Exception as exc:
        pytest.skip(f"cannot create non-E2E DB: {type(exc).__name__}")
    owned_url = _pg_url_for_db(dbname)
    try:
        await _pg_exec(owned_url, "CREATE TABLE IF NOT EXISTS sentinel(id INT PRIMARY KEY, v TEXT)")
        await _pg_exec(owned_url, "DELETE FROM sentinel WHERE id=1")
        await _pg_exec(owned_url, "INSERT INTO sentinel(id,v) VALUES (1,'keepme')")
        # Invoke ONLY validation (never harness setup that could truncate).
        with pytest.raises(E2ESafetyError, match="SAFETY ABORT"):
            validate_e2e_db_url(owned_url)
        # Sentinel still exists via direct reconnect.
        v = await _pg_scalar(owned_url, "SELECT v FROM sentinel WHERE id=1")
        assert v == "keepme"
    finally:
        try:
            await _pg_exec(maint, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:d AND pid<>pg_backend_pid()", {"d": dbname}, autocommit=True)
        except Exception:
            pass
        await _pg_exec(maint, f'DROP DATABASE IF EXISTS "{dbname}"', autocommit=True)


@pytest.mark.asyncio
async def test_runner_refuses_unsafe_db_before_pytest():
    """Full canonical runner refuses owned unsafe DB; pytest never starts; sentinel survives."""
    import sys
    dbname = _unique_non_e2e_db()
    maint = _pg_maintenance_url()
    try:
        await _pg_exec(maint, f'CREATE DATABASE "{dbname}"', autocommit=True)
    except Exception as exc:
        pytest.skip(f"cannot create unsafe DB: {type(exc).__name__}")
    owned_url = _pg_url_for_db(dbname)
    try:
        await _pg_exec(owned_url, "CREATE TABLE IF NOT EXISTS sentinel(id INT PRIMARY KEY, v TEXT)")
        await _pg_exec(owned_url, "DELETE FROM sentinel WHERE id=1")
        await _pg_exec(owned_url, "INSERT INTO sentinel(id,v) VALUES (1,'keepme')")

        # 1) Preflight (same code runner uses) refuses.
        env = dict(os.environ)
        env["POSTGRES_E2E_URL"] = owned_url
        repo = Path(__file__).resolve().parent.parent
        py = sys.executable
        pre = subprocess.run(
            [py, "-m", "e2e.preflight"],
            cwd=str(repo),
            env={**env, "PYTHONPATH": f"{repo}:{repo / 'backend'}:{repo / 'agent' / 'src'}:{env.get('PYTHONPATH','')}"},
            capture_output=True,
            text=True,
        )
        assert pre.returncode != 0
        combined_pre = (pre.stdout or "") + (pre.stderr or "")
        assert "test session starts" not in combined_pre.lower()
        assert owned_url not in combined_pre

        # 2) Full canonical runner also refuses before pytest.
        runner = repo / "scripts" / "run_pre_one_e2e.sh"
        full = subprocess.run(
            ["bash", str(runner)],
            cwd=str(repo),
            env={**env, "PYTHONPATH": f"{repo}:{repo / 'backend'}:{repo / 'agent' / 'src'}:{env.get('PYTHONPATH','')}"},
            capture_output=True,
            text=True,
        )
        assert full.returncode != 0
        combined_full = (full.stdout or "") + (full.stderr or "")
        assert "test session starts" not in combined_full.lower()
        assert owned_url not in combined_full
        assert "preflight" in combined_full.lower()
        # Sentinel + DB survive full runner refusal.
        v = await _pg_scalar(owned_url, "SELECT v FROM sentinel WHERE id=1")
        assert v == "keepme"
        exists = await _pg_scalar(maint, "SELECT 1 FROM pg_database WHERE datname=:d", {"d": dbname})
        assert exists == 1
    finally:
        try:
            await _pg_exec(maint, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:d AND pid<>pg_backend_pid()", {"d": dbname}, autocommit=True)
        except Exception:
            pass
        await _pg_exec(maint, f'DROP DATABASE IF EXISTS "{dbname}"', autocommit=True)


# ---------------------------------------------------------------------------
# Redis ownership: canonical DB only, owned keys only, never FLUSHDB in tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_busy_namespace_refuses_and_preserves_owned_key():
    """Owned key in canonical DB causes refusal; key survives; only owned key deleted."""
    redis_url = _canonical_redis_url()
    # Validate canonical first (must be allowed DB, not DB0).
    info = validate_redis_url(redis_url)
    assert info["db"] != 0
    r = aioredis.from_url(redis_url, decode_responses=True)
    owned = _unique_key()
    try:
        try:
            await r.ping()
        except Exception:
            pytest.skip("redis not available")
        # Ensure starting empty for determinism? If not empty due to parallel harness,
        # skip to avoid interfering (tests run sequentially in our suite, should be empty
        # when this test runs standalone; when run with full suite, harness per-test
        # isolates via FLUSHDB on teardown, so empty here).
        # We create owned key to simulate busy.
        await r.set(owned, "1")
        # Call validator/preflight logic: DBSIZE !=0 must refuse. Use harness method
        # without creating harness (which would create temp dir)? Use preflight live check
        # via direct DBSIZE to avoid harness side-effects.
        size = await r.dbsize()
        assert size >= 1
        # Simulate preflight refusal: non-empty must be refused.
        # Use harness verification on a lightweight instance? Instead assert via
        # direct preflight function to avoid temp dirs.
        from e2e.preflight import _live_checks
        import os as _os
        # _live_checks would fail on DBSIZE; call with canonical URLs (DB non-empty).
        # It must raise safe error without touching keys.
        with pytest.raises(E2ESafetyError, match="not empty"):
            await _live_checks(_canonical_pg_url(), redis_url)
        # Owned key still exists (no FLUSHDB).
        assert await r.get(owned) == "1"
    finally:
        try:
            await r.delete(owned)
        except Exception:
            pass
        try:
            await r.aclose()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_runner_refuses_busy_redis_before_pytest():
    """Full runner refuses busy canonical DB; owned sentinel survives; only owned deleted."""
    import sys
    redis_url = _canonical_redis_url()
    r = aioredis.from_url(redis_url, decode_responses=True)
    owned = _unique_key("e2e_busy")
    try:
        try:
            await r.ping()
        except Exception:
            pytest.skip("redis not available")
        await r.set(owned, "1")
        env = dict(os.environ)
        repo = Path(__file__).resolve().parent.parent
        py = sys.executable
        pre = subprocess.run(
            [py, "-m", "e2e.preflight"],
            cwd=str(repo),
            env={**env, "PYTHONPATH": f"{repo}:{repo / 'backend'}:{repo / 'agent' / 'src'}:{env.get('PYTHONPATH','')}"},
            capture_output=True,
            text=True,
        )
        assert pre.returncode != 0
        assert "not empty" in ((pre.stdout or "") + (pre.stderr or "")).lower()
        assert await r.get(owned) == "1"
        # Full runner also refuses before pytest.
        runner = repo / "scripts" / "run_pre_one_e2e.sh"
        full = subprocess.run(
            ["bash", str(runner)],
            cwd=str(repo),
            env={**env, "PYTHONPATH": f"{repo}:{repo / 'backend'}:{repo / 'agent' / 'src'}:{env.get('PYTHONPATH','')}"},
            capture_output=True,
            text=True,
        )
        assert full.returncode != 0
        combined_full = (full.stdout or "") + (full.stderr or "")
        assert "test session starts" not in combined_full.lower()
        assert "preflight" in combined_full.lower()
        assert await r.get(owned) == "1"
    finally:
        try:
            await r.delete(owned)
        except Exception:
            pass
        try:
            await r.aclose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Cleanup lifecycle: CI-compatible (no hardcoded user), unreachable Redis port
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_failure_triggers_cleanup_and_idempotent():
    """Use canonical PG, unreachable Redis port; cleanup removes temp, no orphan."""
    pg_url = _canonical_pg_url()
    # Derive DB index from canonical Redis to keep shape, but bad port.
    canon_redis = _canonical_redis_url()
    try:
        db_idx = validate_redis_url(canon_redis)["db"]
    except Exception:
        db_idx = 14
    # Find unused localhost port and close it to guarantee refusal (no touch of real server).
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    bad_port = s.getsockname()[1]
    s.close()
    bad_redis = f"redis://127.0.0.1:{bad_port}/{db_idx}"

    old_pg = os.environ.get("POSTGRES_E2E_URL")
    old_redis = os.environ.get("REDIS_URL")
    os.environ["POSTGRES_E2E_URL"] = pg_url
    os.environ["REDIS_URL"] = bad_redis
    # Ensure conflicting var absent.
    old_e2e = os.environ.pop("REDIS_E2E_URL", None)
    h = None
    try:
        h = E2EHarness()
        tmp = Path(h.temp_dir)
        assert tmp.exists()
        with pytest.raises(Exception):
            await h.setup()
        await h.cleanup()
        assert not tmp.exists()
        assert h._engine is None
        assert h._backend_proc is None
        await h.cleanup()
        await h.cleanup()
    finally:
        if h is not None:
            try:
                await h.cleanup()
            except Exception:
                pass
        if old_pg is None:
            os.environ.pop("POSTGRES_E2E_URL", None)
        else:
            os.environ["POSTGRES_E2E_URL"] = old_pg
        if old_redis is None:
            os.environ.pop("REDIS_URL", None)
        else:
            os.environ["REDIS_URL"] = old_redis
        if old_e2e is not None:
            os.environ["REDIS_E2E_URL"] = old_e2e


@pytest.mark.asyncio
async def test_cleanup_idempotent_without_setup():
    pg_url = _canonical_pg_url()
    redis_url = _canonical_redis_url()
    old_pg = os.environ.get("POSTGRES_E2E_URL")
    old_redis = os.environ.get("REDIS_URL")
    os.environ["POSTGRES_E2E_URL"] = pg_url
    os.environ["REDIS_URL"] = redis_url
    old_e2e = os.environ.pop("REDIS_E2E_URL", None)
    try:
        h = E2EHarness()
        tmp = Path(h.temp_dir)
        await h.cleanup()
        assert not tmp.exists()
        await h.cleanup()
    finally:
        if old_pg is None:
            os.environ.pop("POSTGRES_E2E_URL", None)
        else:
            os.environ["POSTGRES_E2E_URL"] = old_pg
        if old_redis is None:
            os.environ.pop("REDIS_URL", None)
        else:
            os.environ["REDIS_URL"] = old_redis
        if old_e2e is not None:
            os.environ["REDIS_E2E_URL"] = old_e2e


# ---------------------------------------------------------------------------
# Failure privacy probes (no marker in output)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preflight_failure_hides_db_marker_password():
    import sys
    marker = f"marker-db-{uuid.uuid4().hex[:8]}"
    # Unsafe DB + marker password must refuse before pytest, marker absent.
    unsafe_url = f"postgresql+asyncpg://u:{marker}@127.0.0.1:5432/review_unsafe_{uuid.uuid4().hex[:6]}"
    env = dict(os.environ)
    env["POSTGRES_E2E_URL"] = unsafe_url
    proc = subprocess.run(
        [sys.executable, "-m", "e2e.preflight"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={**env, "PYTHONPATH": f"{Path(__file__).resolve().parent.parent}:{Path(__file__).resolve().parent.parent / 'backend'}:{Path(__file__).resolve().parent.parent / 'agent' / 'src'}:{env.get('PYTHONPATH','')}"},
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert marker not in combined
    assert unsafe_url not in combined
    assert "test session starts" not in combined.lower()


@pytest.mark.asyncio
async def test_preflight_failure_hides_redis_marker_secret():
    import sys
    marker = f"marker-redis-{uuid.uuid4().hex[:8]}"
    env = dict(os.environ)
    # Keep canonical PG (valid) so failure is Redis-side.
    env["REDIS_URL"] = f"redis://127.0.0.1:6379/14?password={marker}"
    proc = subprocess.run(
        [sys.executable, "-m", "e2e.preflight"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={**env, "PYTHONPATH": f"{Path(__file__).resolve().parent.parent}:{Path(__file__).resolve().parent.parent / 'backend'}:{Path(__file__).resolve().parent.parent / 'agent' / 'src'}:{env.get('PYTHONPATH','')}"},
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert marker not in combined
