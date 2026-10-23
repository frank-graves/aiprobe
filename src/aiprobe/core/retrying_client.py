"""HTTP client decorator that adds retry logic."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Self

from aiprobe.core.http import HttpClient, HttpResponse
from aiprobe.core.retry import (
    RetryPolicy,
    Sleeper,
    compute_delay,
    honor_retry_after,
    is_transient,
)
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


class RetryingHttpClient:
    """Wraps an HttpClient to automatically retry transient failures."""

    def __init__(
        self,
        inner: HttpClient,
        policy: RetryPolicy | None = None,
        sleeper: Sleeper | None = None,
    ) -> None:
        self.inner = inner
        self.policy = policy or RetryPolicy()
        from aiprobe.core.retry import AsyncSleeper

        self.sleeper = sleeper or AsyncSleeper()

    async def __aenter__(self) -> Self:
        await self.inner.__aenter__()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        await self.inner.__aexit__(exc_type, exc_val, exc_tb)

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        attempt = 1
        while True:
            try:
                resp = await self.inner.request(method, url, **kwargs)
                if not is_transient(resp.status_code):
                    return resp

                if attempt >= self.policy.max_attempts:
                    logger.warning(f"Max retries reached for {url}")
                    return resp

            except Exception as exc:
                if not is_transient(exc) or attempt >= self.policy.max_attempts:
                    raise

            retry_after = None
            if "resp" in locals() and resp:
                retry_after = honor_retry_after(resp.headers, self.policy)

            delay = retry_after if retry_after is not None else compute_delay(attempt, self.policy)
            logger.info(
                f"Retrying {method} {url} in {delay:.2f}s "
                f"(attempt {attempt}/{self.policy.max_attempts})"
            )

            await self.sleeper.sleep(delay)
            attempt += 1
            resp = None  # type: ignore

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("POST", url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs: Any) -> AsyncIterator[bytes]:
        attempt = 1
        while True:
            try:
                async for chunk in self.inner.stream(method, url, **kwargs):
                    yield chunk
                return
            except Exception as exc:
                if not is_transient(exc) or attempt >= self.policy.max_attempts:
                    raise
                delay = compute_delay(attempt, self.policy)
                logger.info(f"Retrying stream {method} {url} in {delay:.2f}s")
                await self.sleeper.sleep(delay)
                attempt += 1
