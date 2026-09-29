import time
from typing import Protocol

import redis.asyncio as aioredis

from app.core.config import settings


class RateLimiter(Protocol):
    """Protocol for challenge rate limiting."""

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if rate limit is exceeded, False otherwise.

        Increments the usage count within the specified window.
        """
        ...


class InMemoryRateLimiter:
    """Deterministic in-memory rate limiter for tests and development without Redis."""

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


class RedisRateLimiter:
    """Multi-process safe Redis rate limiter using atomic sliding/fixed window counters."""

    def __init__(self, client: aioredis.Redis) -> None:
        self.client = client

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        redis_key = f"rate_limit:{key}"
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.ttl(redis_key)
            results = await pipe.execute()

        current_count: int = results[0]
        ttl: int = results[1]

        # Set expiry on first access or if key had no TTL
        if ttl == -1 or current_count == 1:
            await self.client.expire(redis_key, window_seconds)

        return current_count > limit


# Global singleton test limiter to share deterministic state across dependency injections
_test_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency to resolve the active rate limiter."""
    if settings.app_env.lower() == "test":
        return _test_limiter

    client = aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
    return RedisRateLimiter(client)

