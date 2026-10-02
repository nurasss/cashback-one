from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.config import settings
from app.db.session import async_session_maker
from app.services.rate_limiter import get_redis_client

router = APIRouter(tags=["Health"])

EXPECTED_ALEMBIC_HEAD = "0009_admin_mutations"


async def check_database_readiness() -> tuple[bool, str]:
    try:
        async with async_session_maker() as session:
            # Check basic query connectivity
            res = await session.execute(text("SELECT 1"))
            if res.scalar() != 1:
                return False, "unavailable"

            # Check schema readiness
            try:
                ver_res = await session.execute(text("SELECT version_num FROM alembic_version"))
                version = ver_res.scalar()
                if version != EXPECTED_ALEMBIC_HEAD:
                    return False, "migration_pending"
            except Exception:  # noqa: BLE001 - probe must fail-closed on schema error
                # In test environment with direct model tables (e.g. SQLite test fixtures)
                if settings.app_env.lower() == "test":
                    try:
                        await session.execute(text("SELECT 1 FROM businesses LIMIT 1"))
                        return True, "ok"
                    except Exception:  # noqa: BLE001 - test fallback probe check
                        return False, "unmigrated"
                return False, "migration_pending"
            return True, "ok"
    except Exception:  # noqa: BLE001 - fail-closed on database connection/pool failure
        return False, "unavailable"


async def check_redis_readiness() -> tuple[bool, str]:
    if not settings.redis_url:
        return False, "unavailable"
    try:
        client = get_redis_client()
        await client.ping()
        return True, "ok"
    except Exception:  # noqa: BLE001 - fail-closed on cache/redis failure
        return False, "unavailable"


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Legacy backward-compatible health check."""
    return {"status": "ok"}


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Process liveness probe. Fast, independent of external dependencies."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(response: Response) -> dict[str, object]:
    """Application readiness probe. Validates database, schema, and cache connectivity."""
    db_ok, db_status = await check_database_readiness()
    redis_ok, redis_status = await check_redis_readiness()

    is_ready = db_ok and redis_ok
    if not is_ready:
        response.status_code = 503

    return {
        "status": "ready" if is_ready else "not_ready",
        "components": {
            "database": db_status,
            "redis": redis_status,
        },
    }
