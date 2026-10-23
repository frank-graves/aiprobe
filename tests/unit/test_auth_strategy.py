"""Offline tests for AuthDetector strategy selection."""

from __future__ import annotations

import pytest

from aiprobe.core.http import HttpResponse
from aiprobe.core.session import Session, SessionStore
from aiprobe.detectors.auth import AuthDetector, AuthStrategy
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import AntibotType, AuthScheme
from tests.helpers.fake_browser import FakeBrowserDriver
from tests.helpers.fake_client import FakeHttpClient


class MemoryStore(SessionStore):
    def __init__(self) -> None:
        self.data: dict[str, Session] = {}

    async def save(self, session: Session) -> None:
        self.data[session.target] = session

    async def load(self, target: str) -> Session | None:
        return self.data.get(target)

    async def delete(self, target: str) -> None:
        self.data.pop(target, None)


def make_antibot_finding(atype: AntibotType) -> Finding:
    return Finding(
        detector="antibot",
        category="security",
        status=DetectorStatus.DETECTED,
        cost=DetectorCost.CHEAP,
        confidence=1.0,
        data={"type": atype.value},
    )


@pytest.mark.asyncio
async def test_http_only_for_none() -> None:
    browser = FakeBrowserDriver()
    store = MemoryStore()
    context = ProbeContext(
        client=FakeHttpClient({}),
        findings={"antibot": make_antibot_finding(AntibotType.NONE)},
    ).model_dump()
    context["browser_driver"] = browser
    context["store"] = store

    detector = AuthDetector()
    finding = await detector.run("https://example.com", context)
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["strategy"] == AuthStrategy.HTTP_ONLY.value
    assert not browser.used


@pytest.mark.asyncio
async def test_http_only_for_cf_tls() -> None:
    browser = FakeBrowserDriver()
    context = ProbeContext(
        client=FakeHttpClient({}),
        findings={"antibot": make_antibot_finding(AntibotType.CF_TLS)},
    ).model_dump()
    context["browser_driver"] = browser

    detector = AuthDetector()
    finding = await detector.run("https://example.com", context)
    assert finding.data["strategy"] == AuthStrategy.HTTP_ONLY.value
    assert not browser.used


@pytest.mark.asyncio
async def test_browser_cookie_for_cf_js() -> None:
    browser = FakeBrowserDriver()
    context = ProbeContext(
        client=FakeHttpClient({}),
        findings={"antibot": make_antibot_finding(AntibotType.CF_JS)},
    ).model_dump()
    context["browser_driver"] = browser

    detector = AuthDetector()
    finding = await detector.run("https://example.com", context)
    assert finding.data["strategy"] == AuthStrategy.BROWSER_COOKIE.value
    assert browser.used


@pytest.mark.asyncio
async def test_browser_failure() -> None:
    browser = FakeBrowserDriver(raise_on_fetch=True)
    context = ProbeContext(
        client=FakeHttpClient({}),
        findings={"antibot": make_antibot_finding(AntibotType.CF_JS)},
    ).model_dump()
    context["browser_driver"] = browser

    detector = AuthDetector()
    finding = await detector.run("https://example.com", context)
    assert finding.status == DetectorStatus.FAILED
    assert "Browser failed" in finding.error


@pytest.mark.asyncio
async def test_scheme_bearer() -> None:
    from tests.helpers.fake_client import FakeHttpClient

    client = FakeHttpClient(
        {
            "GET:https://example.com/:None:None": HttpResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
                url="https://example.com",
                content=b"",
            )
        }
    )
    context = ProbeContext(
        client=client,
        findings={"antibot": make_antibot_finding(AntibotType.NONE)},
    ).model_dump()

    detector = AuthDetector()
    finding = await detector.run("https://example.com", context)
    assert finding.data["scheme"] == AuthScheme.BEARER.value
