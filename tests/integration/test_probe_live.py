"""Live integration test for the orchestrator."""

from __future__ import annotations

import pytest

from aiprobe.core.http import CurlCffiClient
from aiprobe.core.orchestrator import Orchestrator, OrchestratorConfig
from aiprobe.core.pipeline import resolve_steps
from aiprobe.core.session import FileSessionStore, SessionManager
from aiprobe.providers.qwen import QwenProvider


@pytest.mark.network
@pytest.mark.asyncio
async def test_probe_qwen_live() -> None:
    store = FileSessionStore(".aiprobe/test_sessions")
    sm = SessionManager(store, lambda s: CurlCffiClient(cookies=s.cookies))

    steps = resolve_steps(only=["transport", "antibot"])
    orch = Orchestrator(steps, sm, OrchestratorConfig())

    findings = await orch.run("https://chat.qwen.ai", QwenProvider.get_spec())

    assert "transport" in findings
    assert "antibot" in findings
    assert findings["antibot"].status == "detected"
