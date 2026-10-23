"""Retry logic with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class RetryPolicy(BaseModel):
    """Configuration for retry behavior."""

    model_config = ConfigDict(frozen=True)

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    jitter: float = 0.25
    retry_on_status: set[int] = Field(default_factory=lambda: {429, 500, 502, 503, 504})


def is_transient(exc_or_status: Exception | int) -> bool:
    """Determine if an exception or status code is transient (retryable)."""
    if isinstance(exc_or_status, int):
        return exc_or_status in (429, 500, 502, 503, 504)
    return isinstance(exc_or_status, (ConnectionError, TimeoutError))


def compute_delay(attempt: int, policy: RetryPolicy, rng: random.Random | None = None) -> float:
    """Compute the delay for a given retry attempt with exponential backoff and jitter."""
    if rng is None:
        rng = random.Random()

    delay = min(policy.base_delay * (2 ** (attempt - 1)), policy.max_delay)

    if policy.jitter > 0:
        jitter_range = delay * policy.jitter
        delay += rng.uniform(-jitter_range, jitter_range)

    return float(max(0.0, delay))  # <-- Forzamos float()


def honor_retry_after(headers: dict[str, str], policy: RetryPolicy) -> float | None:
    """Parse Retry-After header and return the delay in seconds if present."""
    val = headers.get("retry-after") or headers.get("Retry-After")
    if not val:
        return None

    try:
        return float(str(val))  # <-- Forzamos float(str)
    except ValueError:
        pass

    try:
        dt = parsedate_to_datetime(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        diff = (dt - now).total_seconds()
        return float(max(0.0, diff))  # <-- Forzamos float()
    except ValueError:
        return None


class Sleeper(Protocol):
    """Protocol for injectable sleeping."""

    async def sleep(self, seconds: float) -> None:
        ...


class AsyncSleeper:
    """Real sleeper that uses asyncio."""

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class MockSleeper:
    """Mock sleeper for tests."""

    def __init__(self) -> None:
        self.total_slept: float = 0.0
        self.calls: int = 0

    async def sleep(self, seconds: float) -> None:
        self.total_slept += seconds
        self.calls += 1
