"""Authentication scheme detection."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from aiprobe.core.browser import BrowserDriver
from aiprobe.core.session import Session, SessionStore
from aiprobe.detectors.base import Detector, register
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import AntibotType, AuthScheme, BypassStrategy
from aiprobe.utils.log import get_logger

logger = get_logger(__name__)


class AuthStrategy(StrEnum):
    HTTP_ONLY = "http_only"
    BROWSER_COOKIE = "browser_cookie"
    BROWSER_LOGIN = "browser_login"


@register
class AuthDetector(Detector):
    name = "auth"
    category = "security"
    cost = DetectorCost.EXPENSIVE

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        try:
            ctx = ProbeContext.model_validate(context)
        except Exception as exc:
            return self._finding(DetectorStatus.FAILED, 0.0, error=f"Invalid context: {exc}")

        url = target if target.startswith("http") else f"https://{target}"
        if not url.endswith(ctx.probe_paths[0]):
            url = url.rstrip("/") + ctx.probe_paths[0]

        # 1. Determine strategy based on antibot finding
        antibot_finding = ctx.findings.get("antibot")
        antibot_type = AntibotType.UNKNOWN

        if antibot_finding and antibot_finding.data.get("type"):
            with contextlib.suppress(ValueError):
                antibot_type = AntibotType(antibot_finding.data["type"])

        strategy = self._select_strategy(antibot_type)

        browser_driver: BrowserDriver | None = context.get("browser_driver")
        store: SessionStore | None = context.get("store")

        used_browser = False

        try:
            cookies: dict[str, str] = {}
            user_agent = "aiprobe/0.1"

            # 2. Execute strategy
            if strategy in (AuthStrategy.BROWSER_COOKIE, AuthStrategy.BROWSER_LOGIN):
                if not browser_driver:
                    return self._finding(
                        DetectorStatus.FAILED,
                        0.0,
                        error="Browser strategy required but no driver provided.",
                    )

                used_browser = True
                async with browser_driver as driver:
                    result = await driver.fetch(url)
                    cookies = result.cookies
                    user_agent = result.user_agent

            # 3. Probe auth scheme (HTTP or with browser cookies)
            scheme, refresh = await self._probe_scheme(ctx.client, url, cookies)

            # 4. Build and persist session
            session = Session(
                target=target,
                cookies=cookies,
                user_agent=user_agent,
                impersonate=ctx.impersonate,
                created_at=datetime.now(UTC),
            )
            if store:
                await store.save(session)

            return self._finding(
                DetectorStatus.DETECTED,
                confidence=0.8,
                data={
                    "scheme": scheme.value,
                    "cookies": list(cookies.keys()),
                    "refresh": refresh.value,
                    "strategy": strategy.value,
                    "used_browser": used_browser,
                },
            )

        except Exception as exc:
            logger.error("Auth detection failed: %s", exc)
            return self._finding(DetectorStatus.FAILED, 0.0, error=str(exc))

    def _select_strategy(self, antibot: AntibotType) -> AuthStrategy:
        if antibot in (AntibotType.NONE, AntibotType.CF_TLS):
            return AuthStrategy.HTTP_ONLY
        if antibot in (
            AntibotType.CF_JS,
            AntibotType.TURNSTILE,
            AntibotType.DATADOME,
            AntibotType.UNKNOWN,
        ):
            return AuthStrategy.BROWSER_COOKIE
        return AuthStrategy.BROWSER_COOKIE

    async def _probe_scheme(
        self, client: Any, url: str, cookies: dict[str, str]
    ) -> tuple[AuthScheme, BypassStrategy]:
        try:
            resp = await client.get(url, cookies=cookies, allow_redirects=False)

            if resp.status_code in (401, 403):
                auth_header = resp.headers.get("www-authenticate", "").lower()
                if "bearer" in auth_header:
                    return AuthScheme.BEARER, BypassStrategy.NONE
                return AuthScheme.HEADER, BypassStrategy.NONE

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "").lower()
                if "login" in location or "auth" in location:
                    return AuthScheme.COOKIE, BypassStrategy.BROWSER

            if 200 <= resp.status_code < 300:
                return AuthScheme.NONE, BypassStrategy.NONE

            return AuthScheme.UNKNOWN, BypassStrategy.NONE
        except Exception:
            return AuthScheme.UNKNOWN, BypassStrategy.NONE

    async def refresh(self, target: str) -> Session:
        """Hook for SessionManager to refresh auth via browser."""
        from aiprobe.core.browser import get_browser_driver

        driver = get_browser_driver()
        async with driver as d:
            result = await d.fetch(target)
            return Session(
                target=target,
                cookies=result.cookies,
                user_agent=result.user_agent,
                created_at=datetime.now(UTC),
            )


def make_refresh_hook(
    detector: AuthDetector,
) -> Callable[[str], Awaitable[Session]]:
    """Factory returning a callable compatible with SessionManager.set_refresh_hook."""
    return detector.refresh
