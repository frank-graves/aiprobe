"""The frozen output contract of a probe run (schema v1)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

CURRENT_SCHEMA_VERSION: int = 1


class AntibotType(StrEnum):
    NONE = "none"
    CF_TLS = "cf-tls"
    CF_JS = "cf-js"
    TURNSTILE = "turnstile"
    DATADOME = "datadome"
    UNKNOWN = "unknown"


class BypassStrategy(StrEnum):
    NONE = "none"
    CURL_CFFI = "curl_cffi"
    BROWSER = "browser"


class AuthScheme(StrEnum):
    NONE = "none"
    COOKIE = "cookie"
    BEARER = "bearer"
    HEADER = "header"
    UNKNOWN = "unknown"


class StreamFormat(StrEnum):
    NONE = "none"
    SSE = "sse"
    JSONL = "jsonl"
    CHUNKED = "chunked"
    UNKNOWN = "unknown"


class SchemaCompat(StrEnum):
    OPENAI = "openai"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


_FROZEN = ConfigDict(extra="forbid", frozen=True)


class AntibotInfo(BaseModel):
    model_config = _FROZEN
    type: AntibotType
    bypass: BypassStrategy
    impersonate: str | None = None
    notes: str | None = None


class TransportInfo(BaseModel):
    model_config = _FROZEN
    http2: bool
    tls_fingerprint: str | None = None
    notes: str | None = None


class AuthInfo(BaseModel):
    model_config = _FROZEN
    scheme: AuthScheme
    cookies: list[str]
    refresh: BypassStrategy


class EndpointInfo(BaseModel):
    model_config = _FROZEN
    path: str
    method: str
    requires_auth: bool
    validated: bool


class Profile(BaseModel):
    model_config = _FROZEN
    schema_version: int = CURRENT_SCHEMA_VERSION
    target: str
    detected_at: datetime
    antibot: AntibotInfo
    transport: TransportInfo
    auth: AuthInfo
    endpoints: dict[str, EndpointInfo]
    stream_format: StreamFormat
    tool_calling: bool
    schema_compat: SchemaCompat
    notes: str | None = None

    @field_validator("detected_at")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("detected_at must be timezone-aware (UTC)")
        return v.astimezone(UTC)

    @classmethod
    def from_yaml(cls, path: Path | str) -> Self:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def to_yaml(self, path: Path | str) -> None:
        payload = self.model_dump(mode="json")
        Path(path).write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
