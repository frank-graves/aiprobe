# Architecture

`aiprobe` is built around the concept of **progressive disclosure**. It starts with the cheapest, most reliable checks and only escalates to heavier mechanisms (like a full browser) when absolutely necessary.

## Layers

```text
┌────────────────────────────────────────────────────────────┐
│ CLI (typer)                                                │
│  - probe, detect, validate                                 │
│  - Error handling, signal traps, exit codes                │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│ Orchestrator (pipeline.py)                                 │
│  - Declarative execution order                             │
│  - Dependency resolution                                   │
│  - Context injection                                       │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│ Detectors (antibot, auth, endpoints, schema, etc.)         │
│  - Pure, isolated logic per concern                        │
│  - Depend on HttpClient Protocol, never curl_cffi directly │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│ Core Transport (http.py, session.py, retry.py)             │
│  - CurlCffiClient (with browser fingerprint impersonation) │
│  - Retry decorator, circuit breakers, session persistence  │
└────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **Protocol over Inheritance**: `HttpClient` is a `typing.Protocol`. This allows tests to inject fake clients seamlessly, and lets us swap `curl_cffi` for `httpx` or `primp` in the future by just writing a new adapter.
2. **Declarative Pipeline**: The order of execution is defined in `PIPELINE` (a tuple of `PipelineStep`). This makes it trivial to see dependencies, skip steps via CLI flags (`--skip-expensive`), or reorder them if needed.
3. **Browser as Last Resort**: Opening a browser (Patchright/Camoufox) is extremely expensive. The `AuthDetector` only requests a browser if the `AntibotDetector` explicitly found a JS challenge (`CF_JS`, `TURNSTILE`, `DATADOME`).
4. **Graceful Degradation**: If a detector fails (e.g., due to network issues), the orchestrator catches the exception, records a `FAILED` finding, and skips dependents. It does not crash the entire probe.

## Threat Model vs. Anti-Bot

- **TLS Fingerprinting**: Mitigated by `curl_cffi`'s `impersonate="chrome"`.
- **JS Challenges (Cloudflare IUAM)**: Mitigated by `Patchright` (stealth mode), waiting for `network_idle`, and capturing the `cf_clearance` cookie.
- **IP Reputation**: Cannot be mitigated purely in software; requires rotating proxies (planned for a future phase).
