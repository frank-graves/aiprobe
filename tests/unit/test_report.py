"""Offline tests for report rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import yaml

from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from aiprobe.models.profile import (
    AntibotInfo,
    AntibotType,
    AuthInfo,
    AuthScheme,
    BypassStrategy,
    Profile,
    SchemaCompat,
    StreamFormat,
    TransportInfo,
)
from aiprobe.report.json_out import render_json
from aiprobe.report.markdown_out import render_markdown
from aiprobe.report.yaml_out import render_yaml


def make_profile() -> Profile:
    return Profile(
        target="https://example.com",
        detected_at=datetime.now(UTC),
        antibot=AntibotInfo(type=AntibotType.NONE, bypass=BypassStrategy.NONE),
        transport=TransportInfo(http2=False),
        auth=AuthInfo(scheme=AuthScheme.NONE, cookies=[], refresh=BypassStrategy.NONE),
        endpoints={},
        stream_format=StreamFormat.NONE,
        tool_calling=False,
        schema_compat=SchemaCompat.UNKNOWN,
    )


def test_yaml_roundtrip() -> None:
    profile = make_profile()
    y = render_yaml(profile)
    data = yaml.safe_load(y)
    assert data["target"] == "https://example.com"


def test_json_roundtrip() -> None:
    profile = make_profile()
    j = render_json(profile)
    data = json.loads(j)
    assert data["target"] == "https://example.com"


def test_markdown_with_warnings() -> None:
    profile = make_profile()
    findings = {
        "transport": Finding(
            detector="transport",
            category="network",
            status=DetectorStatus.FAILED,
            cost=DetectorCost.CHEAP,
            confidence=0.0,
            error="Network timeout",
        )
    }
    md = render_markdown(profile, findings)
    assert "## Warnings" in md
    assert "**transport**: failed" in md
    assert "Network timeout" in md
