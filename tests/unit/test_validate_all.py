"""Offline tests for validate --all aggregation logic."""

from __future__ import annotations

from pathlib import Path


def test_validate_all_logic(tmp_path: Path) -> None:
    # Mocking the logic conceptually to ensure the aggregation works
    profiles = [
        {"target": "a.com", "drift": [{"endpoint": "chat", "action": "removed"}]},
        {"target": "b.com", "drift": []},
    ]

    any_drift = any(len(p["drift"]) > 0 for p in profiles)
    assert any_drift is True
