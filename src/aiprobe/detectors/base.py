"""Abstract Detector interface and registration mechanism."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding


class Detector(ABC):
    """Base class every detector must subclass."""

    name: str
    category: str
    cost: DetectorCost

    @abstractmethod
    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        """Probe ``target`` and return a Finding."""

    def _finding(
        self,
        status: DetectorStatus,
        confidence: float,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Finding:
        """Construct a Finding tagged with this detector's identity."""
        return Finding(
            detector=self.name,
            category=self.category,
            status=status,
            cost=self.cost,
            confidence=confidence,
            data=data if data is not None else {},
            error=error,
        )


DETECTORS: dict[str, type[Detector]] = {}


def register[D: type[Detector]](detector_cls: D) -> D:
    """Register a detector class under its ``name``. Usable as a decorator."""
    DETECTORS[detector_cls.name] = detector_cls
    return detector_cls
