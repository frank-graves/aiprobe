"""Offline tests for retry logic."""

from __future__ import annotations

import pytest

from aiprobe.core.http import HttpResponse
from aiprobe.core.retry import (
    MockSleeper,
    RetryPolicy,
    compute_delay,
    honor_retry_after,
    is_transient,
)
from aiprobe.core.retrying_client import RetryingHttpClient


def test_is_transient() -> None:
    assert is_transient(429) is True
    assert is_transient(503) is True
    assert is_transient(ConnectionError()) is True
    assert is_transient(404) is False
    assert is_transient(400) is False
    assert is_transient(ValueError()) is False


def test_compute_delay() -> None:
    policy = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=0.0)
    assert compute_delay(1, policy) == 1.0
    assert compute_delay(2, policy) == 2.0
    assert compute_delay(3, policy) == 4.0
    assert compute_delay(4, policy) == 5.0  # Capped at max_delay


def test_honor_retry_after() -> None:
    policy = RetryPolicy()
    assert honor_retry_after({"retry-after": "5"}, policy) == 5.0
    assert honor_retry_after({"retry-after": "invalid"}, policy) is None


@pytest.mark.asyncio
async def test_retrying_client_success_after_failures() -> None:
    class FlakyClient:
        def __init__(self) -> None:
            self.calls = 0

        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            self.calls += 1
            if self.calls < 3:
                return HttpResponse(status_code=429, headers={}, url=url, content=b"")
            return HttpResponse(status_code=200, headers={}, url=url, content=b"OK")

        async def __aenter__(self) -> FlakyClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

    sleeper = MockSleeper()
    policy = RetryPolicy(max_attempts=3, base_delay=1.0, jitter=0.0)
    client = RetryingHttpClient(FlakyClient(), policy, sleeper)  # type: ignore

    resp = await client.get("http://test")
    assert resp.status_code == 200
    assert sleeper.calls == 2
    assert sleeper.total_slept == 3.0  # 1.0 + 2.0
