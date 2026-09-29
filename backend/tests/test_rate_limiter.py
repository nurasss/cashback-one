from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.rate_limiter import (
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
async def test_redis_rate_limiter_unit_pipeline() -> None:
    """RedisRateLimiter atomic pipeline behaves correctly."""
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()

    # Async context manager for pipeline
    mock_redis.pipeline.return_value.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_redis.expire = AsyncMock()

    # Case 1: First request (count=1, ttl=-1) -> not limited, expire set
    mock_pipeline.execute = AsyncMock(return_value=[1, -1])
    limiter = RedisRateLimiter(mock_redis)
    is_limited = await limiter.is_rate_limited("test-key", limit=5, window_seconds=60)
    assert is_limited is False
    mock_redis.expire.assert_awaited_once_with("rate_limit:test-key", 60)

    # Case 2: Exceeded limit (count=6, ttl=50) -> limited
    mock_redis.expire.reset_mock()
    mock_pipeline.execute = AsyncMock(return_value=[6, 50])
    is_limited_2 = await limiter.is_rate_limited("test-key", limit=5, window_seconds=60)
    assert is_limited_2 is True
    mock_redis.expire.assert_not_awaited()
