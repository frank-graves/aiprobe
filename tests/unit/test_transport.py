"""Offline tests for TransportDetector."""

from __future__ import annotations

import pytest

from aiprobe.core.http import HttpResponse
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.transport import TransportDetector
from aiprobe.models.findings import DetectorStatus
from tests.helpers.fake_client import FakeHttpClient


def make_context(client: FakeHttpClient) -> dict[str, object]:
    return ProbeContext(client=client, probe_paths=["/"]).model_dump()


@pytest.mark.asyncio
async def test_http2_required() -> None:
    ok_resp = HttpResponse(
        status_code=200, headers={}, url="https://example.com", content=b"OK"
    )
    fail_resp = HttpResponse(
        status_code=403, headers={}, url="https://example.com", content=b"Blocked"
    )

    client = FakeHttpClient({
        "GET:https://example.com/:None:1": fail_resp,
        "GET:https://example.com/:None:None": ok_resp,
        "GET:https://example.com/:chrome:None": ok_resp,
    })
    detector = TransportDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["http2"] is True


@pytest.mark.asyncio
async def test_tls_fingerprint_required() -> None:
    ok_resp = HttpResponse(
        status_code=200, headers={}, url="https://example.com", content=b"OK"
    )
    fail_resp = HttpResponse(
        status_code=403, headers={}, url="https://example.com", content=b"Blocked"
    )

    client = FakeHttpClient({
        "GET:https://example.com/:chrome:None": ok_resp,
        "GET:https://example.com/:None:None": fail_resp,
        "GET:https://example.com/:None:1": ok_resp,
    })
    detector = TransportDetector()
    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["tls_fingerprint"] == "chrome"
