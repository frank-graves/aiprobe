"""Live network tests for browser drivers. Skipped if extra not installed."""

from __future__ import annotations

import importlib.util

import pytest

from aiprobe.core.browser import PatchrightDriver

HAS_PATCHRIGHT = importlib.util.find_spec("patchright") is not None


@pytest.mark.network
@pytest.mark.skipif(not HAS_PATCHRIGHT, reason="patchright not installed")
@pytest.mark.asyncio
async def test_patchright_live() -> None:
    async with PatchrightDriver() as driver:
        result = await driver.fetch("https://httpbin.org/user-agent")
        assert result.user_agent
        assert "Chrome" in result.user_agent or "Headless" in result.user_agent
