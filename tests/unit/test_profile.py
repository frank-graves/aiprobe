"""Offline contract tests for the frozen Profile v1 schema."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import (
    AntibotInfo,
    AntibotType,
    AuthInfo,
    AuthScheme,
    BypassStrategy,
    EndpointInfo,
    Profile,
    SchemaCompat,
    StreamFormat,
    TransportInfo,
)


def _example_profile() -> Profile:
    return Profile(
        target="https://chat.qwen.ai",
        detected_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        antibot=AntibotInfo(
            type=AntibotType.NONE,
            bypass=BypassStrategy.NONE,
        ),
        transport=TransportInfo(http2=True),
        auth=AuthInfo(
            scheme=AuthScheme.COOKIE,
            cookies=["token"],
            refresh=BypassStrategy.NONE,
        ),
        endpoints={
            "chat": EndpointInfo(
                path="/api/v1/chat",
                method="POST",
                requires_auth=True,
                validated=True,
            ),
        },
        stream_format=StreamFormat.SSE,
        tool_calling=True,
        schema_compat=SchemaCompat.OPENAI,
        notes="Reference example",
    )


def test_yaml_roundtrip(tmp_path: Path) -> None:
    original = _example_profile()
    path = tmp_path / "profile.yaml"

    original.to_yaml(path)
    assert path.exists()
    # The serialized payload is plain YAML, not Python repr.
    text = path.read_text(encoding="utf-8")
    assert "target: https://chat.qwen.ai" in text

    loaded = Profile.from_yaml(path)
    assert loaded == original
    assert loaded.schema_version == 1
    assert loaded.detected_at.tzinfo is not None
    assert loaded.detected_at.utcoffset() == UTC.utcoffset(None)


def test_extra_field_rejected(tmp_path: Path) -> None:
    yaml_payload = """\
schema_version: 1
target: "https://example.com"
detected_at: "2026-01-01T00:00:00+00:00"
antibot:
  type: none
  bypass: none
transport:
  http2: true
auth:
  scheme: none
  cookies: []
  refresh: none
endpoints: {}
stream_format: none
tool_calling: false
schema_compat: unknown
this_field_does_not_exist: "boom"
"""
    path = tmp_path / "bad.yaml"
    path.write_text(yaml_payload, encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        Profile.from_yaml(path)
    assert "this_field_does_not_exist" in str(excinfo.value)


def test_confidence_out_of_range() -> None:
    common = dict(
        detector="x",
        category="y",
        status=DetectorStatus.OK,
        cost=DetectorCost.CHEAP,
    )
    with pytest.raises(ValidationError):
        Finding(confidence=1.5, **common)
    with pytest.raises(ValidationError):
        Finding(confidence=-0.01, **common)
