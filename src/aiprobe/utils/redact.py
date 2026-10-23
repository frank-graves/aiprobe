"""Sensitive data redaction for logs and output."""

from __future__ import annotations

SENSITIVE_NAMES = {
    "cf_clearance",
    "session",
    "token",
    "authorization",
    "cookie",
    "set-cookie",
    "__cf_bm",
    "api_key",
    "secret",
    "password",
}


def redact_value(name: str, value: str) -> str:
    """Redact a single value based on its key name."""
    if name.lower() not in SENSITIVE_NAMES:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def redact_mapping(d: dict[str, str]) -> dict[str, str]:
    """Redact values in a dictionary based on sensitive keys."""
    return {k: redact_value(k, v) for k, v in d.items()}
