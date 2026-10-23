"""Offline tests for EndpointsDetector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiprobe.core.http import HttpResponse
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.endpoints import EndpointsDetector, EndpointStatus
from aiprobe.models.findings import DetectorStatus
from tests.helpers.fake_client import FakeHttpClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "endpoints"


def load_fixture(name: str) -> HttpResponse:
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    return HttpResponse(
        status_code=data["status_code"],
        headers=data["headers"],
        url=data["url"],
        content=data["body"].encode(),
    )


def make_context(client: FakeHttpClient) -> dict[str, object]:
    return ProbeContext(
        client=client,
        parse_bundles=False,  # Disabled by default for isolated testing
    ).model_dump()


@pytest.mark.asyncio
async def test_classify_public() -> None:
    resp = load_fixture("ok_200")

    class MockClient(FakeHttpClient):
        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            return resp

    detector = EndpointsDetector()
    finding = await detector.run("https://example.com", make_context(MockClient({})))

    assert finding.status == DetectorStatus.DETECTED
    assert len(finding.data["endpoints"]) > 0
    assert all(
        e["status"] == EndpointStatus.EXISTS_PUBLIC.value
        for e in finding.data["endpoints"].values()
    )


@pytest.mark.asyncio
async def test_classify_protected() -> None:
    resp = load_fixture("protected_401")

    class MockClient(FakeHttpClient):
        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            return resp

    detector = EndpointsDetector()
    finding = await detector.run("https://example.com", make_context(MockClient({})))

    assert any(
        e["status"] == EndpointStatus.EXISTS_PROTECTED.value
        for e in finding.data["endpoints"].values()
    )
    assert any(e["requires_auth"] for e in finding.data["endpoints"].values())


@pytest.mark.asyncio
async def test_classify_bad_payload() -> None:
    resp = load_fixture("bad_payload_422")

    class MockClient(FakeHttpClient):
        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            return resp

    detector = EndpointsDetector()
    finding = await detector.run("https://example.com", make_context(MockClient({})))

    assert any(
        e["status"] == EndpointStatus.EXISTS_BAD_PAYLOAD.value
        for e in finding.data["endpoints"].values()
    )


@pytest.mark.asyncio
async def test_method_mismatch_retry() -> None:
    resp_405 = load_fixture("method_405_with_allow")
    resp_200 = load_fixture("ok_200")

    class MockClient(FakeHttpClient):
        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            if method == "POST":
                return resp_405
            return resp_200

    detector = EndpointsDetector()
    finding = await detector.run("https://example.com", make_context(MockClient({})))

    # Retried with GET and succeeded
    assert any(
        e["method"] == "GET" and e["status"] == EndpointStatus.EXISTS_PUBLIC.value
        for e in finding.data["endpoints"].values()
    )


@pytest.mark.asyncio
async def test_not_found_excluded() -> None:
    resp = load_fixture("notfound_404")

    class MockClient(FakeHttpClient):
        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            return resp

    detector = EndpointsDetector()
    finding = await detector.run("https://example.com", make_context(MockClient({})))

    assert len(finding.data["endpoints"]) == 0
    assert len(finding.data["not_found"]) > 0


@pytest.mark.asyncio
async def test_network_error_isolation() -> None:
    resp_ok = load_fixture("ok_200")

    class MockClient(FakeHttpClient):
        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            if url.endswith("/usage"):
                raise Exception("Network unreachable")
            return resp_ok

    detector = EndpointsDetector()
    finding = await detector.run("https://example.com", make_context(MockClient({})))

    # Other endpoints should succeed
    assert finding.status == DetectorStatus.DETECTED
    assert any(
        e["status"] == EndpointStatus.EXISTS_PUBLIC.value
        for e in finding.data["endpoints"].values()
    )
    # Every 'usage' candidate failed, so that endpoint is reported as ERROR.
    # (Results are aggregated by name; a name with any success would mask the error.)
    assert any(
        e["status"] == EndpointStatus.ERROR.value for e in finding.data["endpoints"].values()
    )


@pytest.mark.asyncio
async def test_bundle_parsing() -> None:
    resp_html = HttpResponse(
        status_code=200,
        headers={},
        url="https://example.com",
        content=(FIXTURES / "html_with_bundle_paths.html").read_bytes(),
    )
    resp_404 = load_fixture("notfound_404")

    class MockClient(FakeHttpClient):
        async def get(self, url: str, **kwargs: object) -> HttpResponse:
            return resp_html

        async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
            if url.endswith("/api/v1/chat") or url.endswith("/v1/models"):
                return load_fixture("ok_200")
            return resp_404

    detector = EndpointsDetector()
    context = ProbeContext(
        client=MockClient({}),
        parse_bundles=True,
    ).model_dump()

    finding = await detector.run("https://example.com", context)

    assert "/api/v1/chat" in finding.data["bundle_discovered"]
    assert "/v1/models" in finding.data["bundle_discovered"]
