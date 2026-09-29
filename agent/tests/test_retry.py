"""Tests for exponential backoff and retry policy."""

import pytest

from poscenter_loyalty_agent.retry import RetryState, calculate_backoff


def test_calculate_backoff_bounds() -> None:
    # Attempt 0: around 1.0 ± 20%
    b0 = calculate_backoff(0, initial_seconds=1.0, max_seconds=60.0)
    assert 0.8 <= b0 <= 1.2

    # Attempt 3: 1.0 * 8 = 8.0 ± 20%
    b3 = calculate_backoff(3, initial_seconds=1.0, max_seconds=60.0)
    assert 6.4 <= b3 <= 9.6

    # High attempt capped by max_seconds
    b10 = calculate_backoff(10, initial_seconds=1.0, max_seconds=60.0)
    assert b10 <= 60.0 * 1.2


@pytest.mark.asyncio
async def test_retry_state_delays_and_reset() -> None:
    slept_durations: list[float] = []

    async def fake_sleep(d: float) -> None:
        slept_durations.append(d)

    retry = RetryState(
        initial_seconds=2.0,
        max_seconds=10.0,
        sleep_fn=fake_sleep,
    )

    # First sleep
    await retry.sleep()
    assert len(slept_durations) == 1
    assert retry.attempts == 1

    # Explicit retry-after honors the passed duration
    d = retry.next_delay(retry_after=5.0)
    assert d == 5.0

    # Reset
    retry.reset()
    assert retry.attempts == 0
