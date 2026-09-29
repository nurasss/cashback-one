"""Retry logic with exponential backoff, jitter, and Retry-After support."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


def calculate_backoff(
    attempt: int,
    initial_seconds: float = 1.0,
    max_seconds: float = 60.0,
    jitter_ratio: float = 0.2,
) -> float:
    """Calculate exponential backoff duration with random jitter.

    formula: min(max_seconds, initial_seconds * (2 ** attempt)) ± jitter
    """
    attempt = max(0, attempt)
    base = initial_seconds * (2 ** attempt)
    capped = min(base, max_seconds)
    if jitter_ratio > 0:
        jitter_range = capped * jitter_ratio
        # Random variation between -jitter_range and +jitter_range
        capped += random.uniform(-jitter_range, jitter_range)
    # Strictly bound final delay so that jitter can never exceed max_seconds
    return float(min(max_seconds, max(0.01, capped)))


class RetryState:
    """Tracks retry attempts and calculates subsequent delays."""

    def __init__(
        self,
        initial_seconds: float = 1.0,
        max_seconds: float = 60.0,
        jitter_ratio: float = 0.2,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.initial_seconds = initial_seconds
        self.max_seconds = max_seconds
        self.jitter_ratio = jitter_ratio
        self.attempts = 0
        self.sleep_fn = sleep_fn or asyncio.sleep

    def next_delay(self, retry_after: float | None = None) -> float:
        """Get the next delay in seconds, honoring retry_after if explicitly provided."""
        if retry_after is not None and retry_after > 0:
            # Retry-After is strictly capped at max_seconds
            delay = min(retry_after, self.max_seconds)
        else:
            delay = calculate_backoff(
                attempt=self.attempts,
                initial_seconds=self.initial_seconds,
                max_seconds=self.max_seconds,
                jitter_ratio=self.jitter_ratio,
            )
        self.attempts += 1
        return delay

    async def sleep(self, delay: float | None = None) -> None:
        """Sleep for calculated next_delay or specified delay."""
        duration = delay if delay is not None else self.next_delay()
        logger.debug("Backing off for %.2f seconds (attempt %d)", duration, self.attempts)
        await self.sleep_fn(duration)

    def reset(self) -> None:
        """Reset attempt counter after successful operation."""
        self.attempts = 0
