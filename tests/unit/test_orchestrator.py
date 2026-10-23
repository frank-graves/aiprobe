"""Offline tests for the Orchestrator."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC
from typing import Any

import pytest

from aiprobe.core.http import HttpResponse
from aiprobe.core.orchestrator import Orchestrator, OrchestratorConfig
from aiprobe.core.pipeline import PipelineStep
from aiprobe.core.session import Session, SessionManager
from aiprobe.detectors.base import DETECTORS, Detector, register
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding


class MockStore:
    async def save(self, session: Session) -> None:
        pass
    async def load(self, target: str) -> Session | None:
        from datetime import datetime
        return Session(
            target=target, cookies={}, user_agent="test", created_at=datetime.now(UTC)
        )
    async def delete(self, target: str) -> None:
        pass


class MockClient:
    async def __aenter__(self) -> MockClient:
        return self
    async def __aexit__(self, *args: Any) -> None:
        pass
    async def request(self, *args: Any, **kwargs: Any) -> Any:
        return HttpResponse(status_code=200, headers={}, url="https://example.com", content=b"")
    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return await self.request(*args, **kwargs)
    async def post(self, *args: Any, **kwargs: Any) -> Any:
        return await self.request(*args, **kwargs)
    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        yield b""


# Define mock detectors
@register
class MockTransport(Detector):
    name = "transport"
    category = "network"
    cost = DetectorCost.CHEAP
    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        return self._finding(DetectorStatus.DETECTED, 1.0, data={"http2": True})

@register
class MockAntibot(Detector):
    name = "antibot"
    category = "security"
    cost = DetectorCost.CHEAP
    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        return self._finding(DetectorStatus.FAILED, 0.0, error="Mock failure")

@register
class MockAuth(Detector):
    name = "auth"
    category = "security"
    cost = DetectorCost.EXPENSIVE
    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        return self._finding(DetectorStatus.DETECTED, 1.0)


@pytest.fixture(autouse=True)
def ensure_mocks_are_registered() -> Generator[None, None, None]:
    """Guarantee that these specific mocks overwrite the real detectors,
    regardless of import order by pytest."""
    original = dict(DETECTORS)
    DETECTORS["transport"] = MockTransport
    DETECTORS["antibot"] = MockAntibot
    DETECTORS["auth"] = MockAuth
    yield
    DETECTORS.clear()
    DETECTORS.update(original)


@pytest.fixture
def sm() -> SessionManager:
    return SessionManager(MockStore(), lambda s: MockClient())  # type: ignore


@pytest.mark.asyncio
async def test_pipeline_order_and_skips(sm: SessionManager) -> None:
    steps = (
        PipelineStep(detector="transport", requires=()),
        PipelineStep(detector="antibot", requires=()),
        PipelineStep(detector="auth", requires=("antibot",)),
    )
    config = OrchestratorConfig()
    orch = Orchestrator(steps, sm, config)

    findings = await orch.run("https://example.com")

    assert findings["transport"].status == DetectorStatus.DETECTED
    assert findings["antibot"].status == DetectorStatus.FAILED
    assert findings["auth"].status == DetectorStatus.SKIPPED
    assert "Failed dependencies" in findings["auth"].error


@pytest.mark.asyncio
async def test_skip_expensive(sm: SessionManager) -> None:
    steps = (PipelineStep(detector="auth", requires=()),)
    config = OrchestratorConfig(skip_expensive=True)
    orch = Orchestrator(steps, sm, config)

    findings = await orch.run("https://example.com")
    assert findings["auth"].status == DetectorStatus.SKIPPED
    assert "skip-expensive" in findings["auth"].error


@pytest.mark.asyncio
async def test_assemble_profile(sm: SessionManager) -> None:
    orch = Orchestrator((), sm, OrchestratorConfig())
    findings = {
        "transport": Finding(
            detector="transport", category="network", status=DetectorStatus.DETECTED,
            cost=DetectorCost.CHEAP, confidence=1.0, data={"http2": True}
        )
    }
    profile = await orch.assemble_profile("https://example.com", findings)
    assert profile.transport.http2 is True
