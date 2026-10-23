"""Offline tests for AntibotDetector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiprobe.core.http import HttpResponse
from aiprobe.detectors.antibot import AntibotDetector
from aiprobe.detectors.context import ProbeContext
from aiprobe.models.findings import DetectorStatus
from aiprobe.models.profile import AntibotType, BypassStrategy
from tests.helpers.fake_client import FakeHttpClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "antibot"


def load_fixture(name: str) -> HttpResponse:
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    return HttpResponse(
        status_code=data["status_code"],
        headers=data["headers"],
        url=data["url"],
        content=data["body"].encode(),
    )


def make_context(client: FakeHttpClient) -> dict[str, object]:
    return ProbeContext(client=client, probe_paths=["/"]).model_dump()


@pytest.mark.asyncio
async def test_cloudflare_tls() -> None:
    resp = load_fixture("cloudflare_tls_403")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": HttpResponse(
                status_code=403, headers={}, url="https://example.com", content=b""
            ),
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.CF_TLS.value


@pytest.mark.asyncio
async def test_cloudflare_js() -> None:
    resp = load_fixture("cloudflare_js_challenge_503")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.CF_JS.value
    assert finding.data["bypass"] == BypassStrategy.BROWSER.value


@pytest.mark.asyncio
async def test_cloudflare_turnstile() -> None:
    resp = load_fixture("cloudflare_turnstile_403")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.TURNSTILE.value


@pytest.mark.asyncio
async def test_datadome() -> None:
    resp = load_fixture("datadome_403")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.DATADOME.value


@pytest.mark.asyncio
async def test_akamai() -> None:
    resp = load_fixture("akamai_403")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.UNKNOWN.value


@pytest.mark.asyncio
async def test_perimeterx() -> None:
    resp = load_fixture("perimeterx_403")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.UNKNOWN.value


@pytest.mark.asyncio
async def test_imperva() -> None:
    resp = load_fixture("imperva_403")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.UNKNOWN.value


@pytest.mark.asyncio
async def test_clean_site() -> None:
    resp = load_fixture("clean_200")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.OK
    assert finding.data["type"] == AntibotType.NONE.value
    assert finding.data["bypass"] == BypassStrategy.NONE.value


@pytest.mark.asyncio
async def test_unknown_block() -> None:
    resp = HttpResponse(
        status_code=403,
        headers={"server": "custom"},
        url="https://example.com",
        content=b"Blocked",
    )
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["type"] == AntibotType.UNKNOWN.value
    assert finding.data["bypass"] == BypassStrategy.BROWSER.value


@pytest.mark.asyncio
async def test_network_failure() -> None:
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": Exception("Connection refused"),
            "GET:https://example.com/:None:None": Exception("Connection refused"),
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.FAILED
    assert "Connection refused" in finding.error


@pytest.mark.asyncio
async def test_confidence_range() -> None:
    resp = load_fixture("cloudflare_js_challenge_503")
    client = FakeHttpClient(
        {
            "GET:https://example.com/:chrome:None": resp,
            "GET:https://example.com/:None:None": resp,
        }
    )
    detector = AntibotDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert 0.0 <= finding.confidence <= 1.0
