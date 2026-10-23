# Contributing to aiprobe

We welcome contributions! Please adhere to the following guidelines.

## Adding a Detector

1. Create a new file in `src/aiprobe/detectors/`.
2. Subclass `Detector` and implement `async def run(...) -> Finding`.
3. Decorate the class with `@register`.
4. Add the detector to `PIPELINE` in `src/aiprobe/core/pipeline.py`.
5. Write offline unit tests using `FakeHttpClient`.

## Adding a Provider

1. Create a file in `src/aiprobe/providers/`.
2. Subclass `Provider` and implement `get_spec()`.
3. Decorate the class with `@register_provider`.

## Code Quality

- `ruff check .`
- `mypy --strict`
- `pytest` (must pass 100% offline).
