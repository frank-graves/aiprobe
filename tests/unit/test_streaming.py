"""Offline tests for StreamingDetector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aiprobe.core.http import HttpClient, HttpResponse
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.streaming import StreamingDetector
from aiprobe.models.findings import DetectorStatus
from aiprobe.models.profile import EndpointInfo, StreamFormat

FIXTURES = Path(__file__).parent.parent / "fixtures" / "streams"


class MockStreamClient(HttpClient):
    def __init__(self, content_type: str, body_bytes: bytes) -> None:
        self.content_type = content_type
        self.body_bytes = body_bytes

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        raise NotImplementedError

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        raise NotImplementedError

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            headers={"content-type": self.content_type},
            url=url,
            content=b"",
        )

    async def stream(self, method: str, url: str, **kwargs: Any) -> Any:
        yield self.body_bytes

    async def __aenter__(self) -> MockStreamClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


def make_context(client: HttpClient) -> dict[str, Any]:
    return ProbeContext(
        client=client,
        endpoints={
            "chat": EndpointInfo(
                path="/api/chat", method="POST", requires_auth=False, validated=True
            )
        },
    ).model_dump()


@pytest.mark.asyncio
async def test_stream_sse_header() -> None:
    body = (FIXTURES / "sse_openai.txt").read_bytes()
    client = MockStreamClient("text/event-stream", body)
    detector = StreamingDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["format"] == StreamFormat.SSE.value
    assert finding.data["has_done_marker"] is True


@pytest.mark.asyncio
async def test_stream_jsonl_header() -> None:
    body = (FIXTURES / "jsonl.txt").read_bytes()
    client = MockStreamClient("application/x-ndjson", body)
    detector = StreamingDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.data["format"] == StreamFormat.JSONL.value


@pytest.mark.asyncio
async def test_stream_sse_fallback() -> None:
    body = (FIXTURES / "sse_openai.txt").read_bytes()
    # Ambiguous content type
    client = MockStreamClient("application/octet-stream", body)
    detector = StreamingDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.data["format"] == StreamFormat.SSE.value


@pytest.mark.asyncio
async def test_stream_single_json() -> None:
    body = (FIXTURES / "single_json.txt").read_bytes()
    client = MockStreamClient("application/json", body)
    detector = StreamingDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.data["format"] == StreamFormat.NONE.value
