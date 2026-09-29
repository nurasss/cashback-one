from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient

from app.core.config import settings
from app.core.errors import AppError
from app.services.rate_limiter import (
    RATE_LIMIT_LUA_SCRIPT,
    InMemoryRateLimiter,
    RedisRateLimiter,
    _test_limiter,
)


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_device_limit() -> None:
    """InMemoryRateLimiter enforces limit within window."""
    limiter = InMemoryRateLimiter()
    key = "dev:device-test-1"
    limit = 3
    window = 10

    assert await limiter.is_rate_limited(key, limit, window) is False
    assert await limiter.is_rate_limited(key, limit, window) is False
    assert await limiter.is_rate_limited(key, limit, window) is False
    # 4th request must be rate limited
    assert await limiter.is_rate_limited(key, limit, window) is True


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_independent_keys() -> None:
    """Different keys do not interfere with each other."""
    limiter = InMemoryRateLimiter()
    assert await limiter.is_rate_limited("dev:device-A", 1, 60) is False
    assert await limiter.is_rate_limited("dev:device-B", 1, 60) is False

    # Second request to device-A is limited, while device-B's limit was already reached
    assert await limiter.is_rate_limited("dev:device-A", 1, 60) is True


@pytest.mark.asyncio
async def test_challenge_rate_limiting_via_api(client: AsyncClient) -> None:
    """API endpoint rejects requests exceeding device or IP rate limit with 429."""
    _test_limiter.reset()
    device_id = "device-rate-limit-test"

    # Limit is settings.auth_challenge_device_limit (e.g. 5)
    for _ in range(settings.auth_challenge_device_limit):
        res = await client.post("/auth/challenge", json={"device_id": device_id})
        assert res.status_code == 200

    # Next attempt must return 429
    blocked_res = await client.post("/auth/challenge", json={"device_id": device_id})
    assert blocked_res.status_code == 429
    assert blocked_res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    _test_limiter.reset()


@pytest.mark.asyncio
async def test_redis_rate_limiter_lua_atomic() -> None:
    """RedisRateLimiter uses atomic Lua script and enforces limit semantics."""
    mock_redis = MagicMock()
    mock_redis.eval = AsyncMock()
    limiter = RedisRateLimiter(mock_redis)

    # 1. First request returns count=1 -> not limited
    mock_redis.eval.return_value = 1
    is_limited = await limiter.is_rate_limited("test-key", limit=5, window_seconds=60)
    assert is_limited is False
    mock_redis.eval.assert_awaited_once_with(
        RATE_LIMIT_LUA_SCRIPT,
        1,
        "rate_limit:test-key",
        "60",
    )

    # 2. Reaching exact limit returns count=5 -> not limited
    mock_redis.eval.return_value = 5
    assert await limiter.is_rate_limited("test-key", limit=5, window_seconds=60) is False

    # 3. Exceeding limit returns count=6 -> limited
    mock_redis.eval.return_value = 6
    assert await limiter.is_rate_limited("test-key", limit=5, window_seconds=60) is True


@pytest.mark.asyncio
async def test_redis_rate_limiter_failure_raises_503() -> None:
    """If Redis is unavailable, rate limiter fails closed with 503 AppError."""
    mock_redis = MagicMock()
    mock_redis.eval = AsyncMock(side_effect=aioredis.ConnectionError("Redis connection refused"))
    limiter = RedisRateLimiter(mock_redis)

    with pytest.raises(AppError) as exc_info:
        await limiter.is_rate_limited("fail-key", limit=5, window_seconds=60)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "AUTH_RATE_LIMIT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_challenge_rate_limiter_unavailable_returns_503_via_api(
    client: AsyncClient,
) -> None:
    """When rate limiter raises AUTH_RATE_LIMIT_UNAVAILABLE, API returns controlled 503."""
    from app.main import app
    from app.services.rate_limiter import get_rate_limiter

    class FailingLimiter:
        async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
            raise AppError(
                code="AUTH_RATE_LIMIT_UNAVAILABLE",
                message="Rate limiting service temporarily unavailable",
                status_code=503,
            )

    app.dependency_overrides[get_rate_limiter] = lambda: FailingLimiter()
    try:
        res = await client.post("/auth/challenge", json={"device_id": "dev-503"})
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "AUTH_RATE_LIMIT_UNAVAILABLE"
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


