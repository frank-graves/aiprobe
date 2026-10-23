"""Optional browser integration for bypassing JS challenges."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict


class BrowserResult(BaseModel):
    """Output of a browser fetch."""

    model_config = ConfigDict(frozen=True)

    cookies: dict[str, str]
    user_agent: str
    final_url: str
    html: str


PageAction = Callable[[Any], Awaitable[None]]


class BrowserDriver(Protocol):
    """Abstract browser interface, decoupled from any specific library."""

    async def fetch(
        self,
        url: str,
        *,
        wait_until: str = "network_idle",
        actions: PageAction | None = None,
        timeout: float = 30.0,
    ) -> BrowserResult: ...

    async def close(self) -> None: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None: ...


class PatchrightDriver:
    """Stealth browser driver backed by patchright."""

    def __init__(self, headless: bool = True) -> None:
        try:
            from patchright.async_api import async_playwright  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "patchright is not installed. Install the browser extra: "
                "`pip install aiprobe[browser]`"
            ) from exc

        self._playwright = async_playwright
        self.headless = headless
        self._pw_cm: Any = None
        self._browser: Any = None
        self._context: Any = None

    async def __aenter__(self) -> Self:
        self._pw_cm = self._playwright()
        self._pw = await self._pw_cm.__aenter__()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw_cm:
            await self._pw_cm.__aexit__(None, None, None)

    async def fetch(
        self,
        url: str,
        *,
        wait_until: str = "network_idle",
        actions: PageAction | None = None,
        timeout: float = 30.0,
    ) -> BrowserResult:
        if not self._context:
            raise RuntimeError("Driver used outside async context manager.")

        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout * 1000)

            if actions:
                await actions(page)

            cookies_list = await self._context.cookies()
            cookies = {c["name"]: c["value"] for c in cookies_list}
            ua = await page.evaluate("navigator.userAgent")
            html = await page.content()
            final_url = page.url

            return BrowserResult(
                cookies=cookies,
                user_agent=str(ua),
                final_url=final_url,
                html=html,
            )
        finally:
            await page.close()


class CamoufoxDriver:
    """Stealth browser driver backed by camoufox."""

    def __init__(self, headless: bool = True) -> None:
        try:
            from camoufox.async_api import AsyncCamoufox  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "camoufox is not installed. Install the browser extra: "
                "`pip install aiprobe[browser]`"
            ) from exc

        self._camoufox_cls = AsyncCamoufox
        self.headless = headless
        self._browser: Any = None

    async def __aenter__(self) -> Self:
        self._browser = await self._camoufox_cls(headless=self.headless).__aenter__()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.__aexit__(None, None, None)

    async def fetch(
        self,
        url: str,
        *,
        wait_until: str = "network_idle",
        actions: PageAction | None = None,
        timeout: float = 30.0,
    ) -> BrowserResult:
        if not self._browser:
            raise RuntimeError("Driver used outside async context manager.")

        page = await self._browser.new_page()
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout * 1000)

            if actions:
                await actions(page)

            cookies_list = await self._browser.cookies()
            cookies = {c["name"]: c["value"] for c in cookies_list}
            ua = await page.evaluate("navigator.userAgent")
            html = await page.content()
            final_url = page.url

            return BrowserResult(
                cookies=cookies,
                user_agent=str(ua),
                final_url=final_url,
                html=html,
            )
        finally:
            await page.close()


def get_browser_driver(name: str = "patchright") -> BrowserDriver:
    """Factory function to get a browser driver by name."""
    if name == "patchright":
        return PatchrightDriver()
    elif name == "camoufox":
        return CamoufoxDriver()
    else:
        raise ValueError(f"Unknown browser driver: {name}")
