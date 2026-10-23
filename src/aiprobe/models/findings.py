"""Detector-level findings."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DetectorStatus(StrEnum):
    OK = "ok"
    DETECTED = "detected"
    FAILED = "failed"
    SKIPPED = "skipped"


class DetectorCost(StrEnum):
    CHEAP = "cheap"
    EXPENSIVE = "expensive"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    detector: str
    category: str
    status: DetectorStatus
    cost: DetectorCost
    confidence: float = Field(ge=0, le=1)
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
