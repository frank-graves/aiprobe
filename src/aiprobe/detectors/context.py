"""Context object passed to all detectors during a probe run."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aiprobe.core.http import HttpClient
from aiprobe.core.session import Session
from aiprobe.models.findings import Finding
from aiprobe.models.profile import EndpointInfo
from aiprobe.providers.base import ProviderSpec


class ProbeContext(BaseModel):
    """Typed container for the `context` dict accepted by `Detector.run()`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: HttpClient
    session: Session | None = None
    probe_paths: list[str] = Field(default_factory=lambda: ["/"])
    impersonate: str = "chrome"
    findings: dict[str, Finding] = Field(default_factory=dict)
    provider_spec: ProviderSpec | None = None

    # Endpoints phase specific config
    parse_bundles: bool = True
    max_bundle_paths: int = 50

    # Phase 5 additions
    endpoints: dict[str, EndpointInfo] = Field(default_factory=dict)
    chat_payload: dict[str, Any] | None = None
