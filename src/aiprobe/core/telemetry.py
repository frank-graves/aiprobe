"""Observability primitives for tracking pipeline execution."""

from __future__ import annotations

import time
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class StepEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    detector: str
    status: str
    duration_ms: float
    error: str | None = None


class RunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: str
    started_at: float
    duration_ms: float
    steps: list[StepEvent]
    totals: dict[str, int]


class StepObserver(Protocol):
    def on_step_start(self, detector: str) -> None: ...
    def on_step_end(self, event: StepEvent) -> None: ...


class CollectingObserver:
    """Accumulates events into a RunReport."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._steps: list[StepEvent] = []
        self._current_start: float = 0.0

    def on_step_start(self, detector: str) -> None:
        self._current_start = time.time()

    def on_step_end(self, event: StepEvent) -> None:
        self._steps.append(event)

    def build_report(self, target: str) -> RunReport:
        end_time = time.time()
        totals: dict[str, int] = {}
        for s in self._steps:
            totals[s.status] = totals.get(s.status, 0) + 1

        return RunReport(
            target=target,
            started_at=self._start_time,
            duration_ms=(end_time - self._start_time) * 1000,
            steps=self._steps,
            totals=totals,
        )


def render_run_report(report: RunReport) -> str:
    """Render a RunReport as a readable text table."""
    lines = [
        f"--- Run Report: {report.target} ---",
        f"Total time: {report.duration_ms / 1000:.2f}s",
        "",
        "| Detector | Status | Time (ms) | Error |",
        "|---|---|---|---|",
    ]
    for step in report.steps:
        err = step.error or ""
        lines.append(f"| {step.detector} | {step.status} | {step.duration_ms:.1f} | {err} |")
    lines.append("")
    return "\n".join(lines)
