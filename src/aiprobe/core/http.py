"""Decoupled HTTP transport layer backed by curl_cffi."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, Self, cast, runtime_checkable

from curl_cffi.requests import AsyncSession
from pydantic import BaseModel, ConfigDict, Field, field_validator

_HTTP_METHOD = Literal["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH", "QUERY"]


class HttpResponse(BaseModel):
    """Normalized HTTP response, independent of the underlying client."""

    model_config = ConfigDict(frozen=True)

    status_code: int
    headers: dict[str, str]
    url: str
    content: bytes

    @field_validator("headers")
    @classmethod
    def _lowercase_headers(cls, v: dict[str, str]) -> dict[str, str]:
        return {k.lower(): val for k, val in v.items()}

    def text(self) -> str:
        """Decode content as UTF-8, replacing invalid bytes."""
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:  # type: ignore[override]
        """Parse content as JSON. Raises ``json.JSONDecodeError`` on failure."""
        return json.loads(self.text())

    def ok(self) -> bool:
        """Return True if status is in the 2xx range."""
        return 200 <= self.status_code < 300


@runtime_checkable
class HttpClient(Protocol):
    """Abstract async HTTP client interface."""

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse: ...

    async def get(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def post(self, url: str, **kwargs: Any) -> HttpResponse: ...

    def stream(self, method: str, url: str, **kwargs: Any) -> AsyncIterator[bytes]: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None: ...


class HttpConfig(BaseModel):
    """Configuration for HTTP clients."""

    model_config = ConfigDict(frozen=True)

    impersonate: str = "chrome"
    timeout: float = 30.0
    headers: dict[str, str] = Field(default_factory=dict)
    follow_redirects: bool = True
    max_redirects: int = 10
    verify: bool = True


class CurlCffiClient:
    """HttpClient implementation backed by curl_cffi.AsyncSession."""

    def __init__(
        self,
        config: HttpConfig | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self.config = config or HttpConfig()
        self._cookies = cookies or {}
        self._session: Any = None

    async def __aenter__(self) -> Self:
        self._session = AsyncSession(
            impersonate=self.config.impersonate,
            timeout=self.config.timeout,
            verify=self.config.verify,
            max_redirects=self.config.max_redirects,
        )
        if self._cookies:
            self._session.cookies.update(self._cookies)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def _get_session(self) -> Any:
        if not self._session:
            raise RuntimeError("Client must be used within an async context manager.")
        return self._session

    def _merge_headers(self, req_headers: dict[str, str] | None) -> dict[str, str]:
        headers = self.config.headers.copy()
        if req_headers:
            headers.update(req_headers)
        return headers

    def _build_response(self, resp: Any) -> HttpResponse:
        return HttpResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            url=resp.url,
            content=resp.content,
        )

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        session = self._get_session()
        headers = self._merge_headers(kwargs.pop("headers", None))

        resp = await session.request(
            cast(_HTTP_METHOD, method),
            url,
            headers=headers,
            allow_redirects=self.config.follow_redirects,
            **kwargs,
        )
        return self._build_response(resp)

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return await self.request("POST", url, **kwargs)

    async def stream(self, method: str, url: str, **kwargs: Any) -> AsyncIterator[bytes]:
        session = self._get_session()
        headers = self._merge_headers(kwargs.pop("headers", None))

        resp = await session.request(
            cast(_HTTP_METHOD, method),
            url,
            headers=headers,
            allow_redirects=self.config.follow_redirects,
            stream=True,
            **kwargs,
        )
        try:
            async for chunk in resp.aiter_content():
                yield chunk
        finally:
            await resp.aclose()

    # ── cookie management ────────────────────────────────────────────────

    def get_cookies(self) -> dict[str, str]:
        """Return current session cookies."""
        session = self._get_session()
        return dict(session.cookies)

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """Replace all session cookies."""
        session = self._get_session()
        session.cookies.clear()
        session.cookies.update(cookies)

    def update_cookies(self, cookies: dict[str, str]) -> None:
        """Merge new cookies into the session."""
        session = self._get_session()
        session.cookies.update(cookies)
