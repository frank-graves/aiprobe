"""Fake BrowserDriver for offline testing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Self

from aiprobe.core.browser import BrowserResult


class FakeBrowserDriver:
    def __init__(self, result: BrowserResult | None = None, raise_on_fetch: bool = False) -> None:
        self.result = result or BrowserResult(
            cookies={"cf_clearance": "fake_clearance"},
            user_agent="Mozilla/5.0 (FakeBrowser)",
            final_url="https://example.com",
            html="<html>Fake</html>",
        )
        self.raise_on_fetch = raise_on_fetch
        self.used = False

    async def fetch(
        self,
        url: str,
        *,
        wait_until: str = "network_idle",
        actions: Callable[[Any], Awaitable[None]] | None = None,
        timeout: float = 30.0,
    ) -> BrowserResult:
        self.used = True
        if self.raise_on_fetch:
            raise RuntimeError("Browser failed intentionally")
        return self.result

    async def close(self) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass
