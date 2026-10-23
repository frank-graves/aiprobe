"""Offline tests for secret redaction."""

from __future__ import annotations

from aiprobe.utils.redact import redact_mapping, redact_value


def test_redact_value() -> None:
    assert redact_value("cf_clearance", "1234567890abcdef") == "1234...cdef"
    assert redact_value("token", "short") == "*****"
    assert redact_value("user-agent", "Mozilla/5.0") == "Mozilla/5.0"


def test_redact_mapping() -> None:
    d = {
        "cf_clearance": "1234567890abcdef",
        "content-type": "application/json",
    }
    redacted = redact_mapping(d)
    assert redacted["cf_clearance"] == "1234...cdef"
    assert redacted["content-type"] == "application/json"
