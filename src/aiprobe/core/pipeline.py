"""Declarative pipeline definition for aiprobe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PipelineStep:
    """A single step in the probe pipeline."""

    detector: str
    requires: tuple[str, ...]
    skip_if: Callable[[dict[str, Any]], bool] | None = None
    enabled_by_default: bool = True


PIPELINE: tuple[PipelineStep, ...] = (
    PipelineStep(detector="transport", requires=()),
    PipelineStep(detector="antibot", requires=()),
    PipelineStep(detector="auth", requires=("antibot",)),
    PipelineStep(detector="endpoints", requires=("antibot", "auth")),
    PipelineStep(detector="streaming", requires=("endpoints",)),
    PipelineStep(detector="tools", requires=("endpoints",)),
    PipelineStep(detector="schema", requires=("endpoints", "streaming")),
)


def resolve_steps(
    only: list[str] | None = None, skip: list[str] | None = None
) -> tuple[PipelineStep, ...]:
    """Filter and order the pipeline steps, ensuring dependencies are met."""
    only_set = set(only) if only else None
    skip_set = set(skip) if skip else set()

    resolved: dict[str, PipelineStep] = {}
    for step in PIPELINE:
        if not step.enabled_by_default:
            continue

        if only_set is not None and step.detector not in only_set:
            continue

        if step.detector in skip_set:
            continue

        resolved[step.detector] = step

    changed = True
    while changed:
        changed = False
        for _name, step in list(resolved.items()):
            for req in step.requires:
                if req not in resolved and req not in skip_set:
                    req_step = next((s for s in PIPELINE if s.detector == req), None)
                    if req_step:
                        resolved[req] = req_step
                        changed = True

    pipeline_order = [s.detector for s in PIPELINE]
    return tuple(sorted(resolved.values(), key=lambda s: pipeline_order.index(s.detector)))
