import time
from typing import Protocol

import redis.asyncio as aioredis
from fastapi import Request

from app.core.config import settings
from app.core.errors import AppError


class RateLimiter(Protocol):
    """Protocol for challenge rate limiting."""

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if rate limit is exceeded, False otherwise.

        Increments the usage count within the specified window.
        """
        ...


class InMemoryRateLimiter:
    """Deterministic in-memory rate limiter for explicit unit-test injection only.

    Production and E2E runtimes must use RedisRateLimiter. This class is never
    auto-selected by application runtime; unit tests inject it via
    FastAPI dependency_overrides.
    """

    def __init__(self) -> None:
        self._records: dict[str, list[float]] = {}

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        history = self._records.get(key, [])
        # Evict timestamps outside the sliding window
        valid_history = [t for t in history if now - t < window_seconds]
        if len(valid_history) >= limit:
            self._records[key] = valid_history
            return True

        valid_history.append(now)
        self._records[key] = valid_history
        return False

    def reset(self) -> None:
        self._records.clear()


RATE_LIMIT_LUA_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return current
"""


class RedisRateLimiter:
    """Multi-process safe Redis rate limiter using atomic Lua fixed-window counter."""

    def __init__(self, client: aioredis.Redis) -> None:
        self.client = client

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        redis_key = f"rate_limit:{key}"
        try:
            current_count = await self.client.eval(
                RATE_LIMIT_LUA_SCRIPT,
                1,
                redis_key,
                str(window_seconds),
            )
            return int(current_count) > limit
        except (aioredis.RedisError, OSError) as exc:
            raise AppError(
                code="AUTH_RATE_LIMIT_UNAVAILABLE",
                message="Rate limiting service temporarily unavailable",
                status_code=503,
            ) from exc


# Global singleton test limiter to share deterministic state across dependency injections
_test_limiter = InMemoryRateLimiter()

# Shared Redis client instance for production/dev
_shared_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Resolve or instantiate shared Redis client."""
    global _shared_redis_client
    if _shared_redis_client is None:
        _shared_redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
        )
    return _shared_redis_client


async def close_redis_client() -> None:
    """Gracefully close shared Redis client connections."""
    global _shared_redis_client
    if _shared_redis_client is not None:
        await _shared_redis_client.aclose()
        _shared_redis_client = None


def get_rate_limiter(request: Request) -> RateLimiter:
    """FastAPI dependency to resolve the active rate limiter.

    Always Redis-backed in application runtime (including E2E development mode).
    InMemoryRateLimiter is used only when explicitly injected by unit tests via
    dependency_overrides. No environment flag selects the memory limiter.
    """
    if hasattr(request.app.state, "redis") and request.app.state.redis is not None:
        return RedisRateLimiter(request.app.state.redis)

    return RedisRateLimiter(get_redis_client())


