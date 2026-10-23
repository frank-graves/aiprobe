"""Offline tests for ToolsDetector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aiprobe.core.http import HttpClient, HttpResponse
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.tools import ToolsDetector
from aiprobe.models.profile import EndpointInfo

FIXTURES = Path(__file__).parent.parent / "fixtures" / "schemas"


def make_context(client: HttpClient) -> dict[str, Any]:
    return ProbeContext(
        client=client,
        endpoints={
            "chat": EndpointInfo(
                path="/api/chat", method="POST", requires_auth=False, validated=True
            )
        },
    ).model_dump()


class MockToolsClient(HttpClient):
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.call_count = 0

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        raise NotImplementedError

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        raise NotImplementedError

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return resp

    async def stream(self, method: str, url: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def __aenter__(self) -> MockToolsClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_tools_supported() -> None:
    data = json.loads((FIXTURES / "tool_calls_response.json").read_text())
    ok_resp = HttpResponse(
        status_code=200, headers={}, url="https://example.com", content=json.dumps(data).encode()
    )

    client = MockToolsClient([ok_resp])
    detector = ToolsDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.data["supported"] is True
    assert finding.data["format"] == "openai"


@pytest.mark.asyncio
async def test_tools_rejected_all() -> None:
    err_resp = HttpResponse(
        status_code=400, headers={}, url="https://example.com", content=b"Unknown field: tools"
    )

    client = MockToolsClient([err_resp])
    detector = ToolsDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.data["supported"] is False
    # Should try 3 variants
    assert len(finding.data["variants_tried"]) == 3


@pytest.mark.asyncio
async def test_tools_accepted_ignored() -> None:
    # 200 response without tool_calls
    data = {"id": "123", "choices": [{"message": {"role": "assistant", "content": "Hello"}}]}
    ok_resp = HttpResponse(
        status_code=200, headers={}, url="https://example.com", content=json.dumps(data).encode()
    )

    client = MockToolsClient([ok_resp])
    detector = ToolsDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.data["supported"] is False
