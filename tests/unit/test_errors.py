"""Offline tests for error mapping."""

from __future__ import annotations

from aiprobe.errors import (
    AuthError,
    ConfigError,
    DriftDetectedError,
    NetworkError,
    exit_code_for,
)


def test_exit_codes() -> None:
    assert exit_code_for(ConfigError("")) == 3
    assert exit_code_for(NetworkError("")) == 1
    assert exit_code_for(DriftDetectedError("")) == 2
    assert exit_code_for(AuthError("")) == 1
    assert exit_code_for(ValueError("")) == 1  # Unknown exception
