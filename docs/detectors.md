# How to Write a Detector

Detectors are the core of `aiprobe`. They are small, independent modules that ask a specific question about a target and return a `Finding`.

## The Contract

Every detector must subclass `Detector` and implement the `run` coroutine.

```python
from aiprobe.detectors.base import Detector, register
from aiprobe.models.findings import DetectorCost, DetectorStatus, Finding
from typing import Any


@register
class MyCustomDetector(Detector):
    name = "my-custom"
    category = "custom"
    cost = DetectorCost.CHEAP

    async def run(self, target: str, context: dict[str, Any]) -> Finding:
        # context contains a validated ProbeContext and the findings of previous steps
        return self._finding(
            status=DetectorStatus.OK, confidence=1.0, data={"my_result": "success"}
        )
```

## The Context

The `context` dictionary passed to `run` contains the following keys:

- `client`: An instance of `HttpClient` (from `aiprobe.core.http`).
- `session`: The current `Session` object (or `None`).
- `findings`: A dict of all previous `Finding` objects (keyed by detector name).
- `provider_spec`: A `ProviderSpec` object if the target matches a known provider.
- `endpoints`: A parsed dict of `EndpointInfo` (populated after the endpoints detector runs).

## Registration

Using the `@register` decorator automatically adds your detector to the global `DETECTORS` registry. To include it in the execution pipeline, add it to `PIPELINE` in `core/pipeline.py`.
