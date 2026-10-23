"""Live network tests for the orchestrator."""

from __future__ import annotations

import pytest

from aiprobe.core.http import CurlCffiClient
from aiprobe.core.orchestrator import Orchestrator, OrchestratorConfig
from aiprobe.core.pipeline import resolve_steps
from aiprobe.core.session import FileSessionStore, SessionManager
from aiprobe.models.findings import DetectorStatus
from aiprobe.providers.qwen import QwenProvider


@pytest.mark.network
@pytest.mark.asyncio
async def test_probe_qwen_live() -> None:
    """Live test against Qwen. Accepts network failures gracefully."""
    store = FileSessionStore(".aiprobe/test_sessions")
    sm = SessionManager(store, lambda s: CurlCffiClient(cookies=s.cookies))

    steps = resolve_steps(only=["transport", "antibot"])
    orch = Orchestrator(steps, sm, OrchestratorConfig())

    findings = await orch.run("https://chat.qwen.ai", QwenProvider.get_spec())

    assert "transport" in findings
    assert "antibot" in findings

    # If the runner's IP is blocked by Qwen, it will fail. We accept this in CI.
    if findings["antibot"].status == DetectorStatus.FAILED:
        pytest.skip(f"Network blocked or failed: {findings['antibot'].error}")

    # Qwen might drop antibot, so we accept both DETECTED and OK
    assert findings["antibot"].status in (DetectorStatus.DETECTED, DetectorStatus.OK)
