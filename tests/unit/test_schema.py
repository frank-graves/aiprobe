"""Offline tests for SchemaDetector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aiprobe.core.http import HttpClient, HttpResponse
from aiprobe.detectors.context import ProbeContext
from aiprobe.detectors.schema import SchemaDetector
from aiprobe.models.findings import DetectorStatus
from aiprobe.models.profile import EndpointInfo, SchemaCompat

FIXTURES = Path(__file__).parent.parent / "fixtures" / "schemas"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text())


class MockSchemaClient(HttpClient):
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

    async def __aenter__(self) -> MockSchemaClient:
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
async def test_schema_openai() -> None:
    resp_data = load_fixture("openai_response")
    ok_resp = HttpResponse(
        status_code=200,
        headers={},
        url="https://example.com",
        content=json.dumps(resp_data).encode(),
    )

    client = MockSchemaClient([ok_resp])
    detector = SchemaDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    assert finding.data["schema_compat"] == SchemaCompat.OPENAI.value
    assert finding.data["rounds_used"] == 0


@pytest.mark.asyncio
async def test_schema_auto_adjust_422() -> None:
    err_data = load_fixture("validation_error_422")
    err_resp = HttpResponse(
        status_code=422,
        headers={},
        url="https://example.com",
        content=json.dumps(err_data).encode(),
    )

    ok_data = load_fixture("openai_response")
    ok_resp = HttpResponse(
        status_code=200, headers={}, url="https://example.com", content=json.dumps(ok_data).encode()
    )

    # First call fails with 422, second succeeds
    client = MockSchemaClient([err_resp, ok_resp])
    detector = SchemaDetector()

    finding = await detector.run("https://example.com", make_context(client))
    assert finding.status == DetectorStatus.DETECTED
    # It should have adjusted payload to include "model"
    assert finding.data["rounds_used"] == 1
    assert "model" in finding.data["working_payload"]


@pytest.mark.asyncio
async def test_schema_missing_endpoint() -> None:
    client = MockSchemaClient([])
    detector = SchemaDetector()
    finding = await detector.run("https://example.com", ProbeContext(client=client).model_dump())
    assert finding.status == DetectorStatus.SKIPPED
