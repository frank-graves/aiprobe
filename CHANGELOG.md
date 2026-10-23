# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-23

### Added
- Initial release of `aiprobe`.
- Core HTTP transport with `curl_cffi` impersonation.
- Anti-bot detection (Cloudflare, DataDome, Akamai, etc.).
- Auth strategy selection (HTTP vs Browser).
- Endpoint discovery with concurrency control.
- JSON Schema inference and stream format classification.
- Declarative pipeline orchestrator.
- CLI with `probe`, `detect`, and `validate` commands.
- Retry policies, circuit breakers, and secret redaction.
