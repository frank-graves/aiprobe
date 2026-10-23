"""Fake HTTP client for offline detector testing."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from aiprobe.core.http import HttpResponse


class FakeHttpClient:
    """Implements HttpClient. Routes requests based on method, URL, and kwargs."""

    def __init__(self, routes: dict[str, HttpResponse | Exception]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def _make_key(self, method: str, url: str, kwargs: dict[str, Any]) -> str:
        imp = kwargs.get("impersonate", "None")
        hv = kwargs.get("http_version", "None")
        return f"{method}:{url}:{imp}:{hv}"

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        key = self._make_key(method, url, kwargs)
        self.calls.append(key)
        route = self.routes.get(key)
        if isinstance(route, Exception):
            raise route
        if route:
            return route
        return HttpResponse(status_code=404, headers={}, url=url, content=b"Not Found")

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("POST", url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs: Any) -> AsyncIterator[bytes]:
        resp = await self.request(method, url, **kwargs)
        yield resp.content

    async def __aenter__(self) -> FakeHttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass
