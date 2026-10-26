# 🔍 aiprobe

[![CI](https://github.com/frank-graves/aiprobe/actions/workflows/ci.yaml/badge.svg)](https://github.com/frank-graves/aiprobe/actions/workflows/ci.yaml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**aiprobe** is a FOSS (Free and Open Source Software) CLI tool built to probe and profile the internal APIs of AI web applications (like `chat.qwen.ai` or `chat.deepseek.com`).

It produces a versioned YAML `profile` that describes exactly how a web app talks to its backend—covering transport, anti-bot protections, authentication, discovered endpoints, JSON schemas, and streaming formats. This contract is designed to be consumed by downstream multi-provider gateways.

## ✨ Features

- **🕵️ Anti-Bot Detection**: Classifies Cloudflare (TLS/JS/Turnstile), DataDome, Akamai, and others. It uses differential TLS fingerprinting to know exactly which bypass strategy to use.
- **🛡️ Graceful Auth**: Only opens a headless browser (via Patchright/Camoufox) if the anti-bot wall strictly requires it. Otherwise, it stays fast and uses HTTP.
- **🛣️ Endpoint Discovery**: Probes candidate paths concurrently. It's smart enough to detect SPA false-positives (where a 200 OK returns HTML instead of JSON).
- **📐 Schema Inference**: Infers the JSON schema of requests/responses and classifies compatibility with OpenAI formats.
- **🌊 Streaming Detection**: Identifies SSE, JSONL, and raw chunked formats.
- **⚙️ Resilient by Design**: Built-in retry policies (exponential backoff), circuit breakers, and structured error handling.
- **🔒 Security First**: AES-256-GCM session encryption at rest and secret redaction in logs.
- **💻 Beautiful CLI**: Built with Typer, with outputs in YAML, JSON, and human-readable Markdown.

## 🚀 Installation

Ensure you have Python 3.12+ installed.

```bash
# Clone the repository
git clone https://github.com/frank-graves/aiprobe
cd aiprobe

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# (Optional) Install browser dependencies for JS challenge bypass
pip install -e ".[browser]"
```

## 📖 Usage

### Probe a target
Run the full detection pipeline and save a profile.

```bash
# Print the YAML profile to the console
aiprobe probe chat.qwen.ai

# Save outputs organized by domain (creates outputs/chat_qwen_ai/)
aiprobe probe chat.qwen.ai --out-dir outputs

# Generate a human-readable Markdown report
aiprobe probe chat.deepseek.com --format md -o report.md
```

### Detect specific features
Run only the detectors you care about, without generating a full profile.

```bash
aiprobe detect chat.qwen.ai --only antibot,transport
```

### Validate against drift
Check if a target has changed its API since you last saved its profile. Perfect for CI/CD.

```bash
# Check a single profile
aiprobe validate profiles/qwen.yaml

# Check all profiles in a directory
aiprobe validate --all --json
```

## 🏗️ Architecture

`aiprobe` follows a strictly layered architecture:
- **`core/`**: The engine. HTTP transport (`curl_cffi`), session management, retry logic, and the declarative pipeline.
- **`detectors/`**: Isolated modules that answer a single question (e.g., "Is there an anti-bot?"). They depend on a structural `HttpClient` Protocol, not concrete libraries.
- **`models/`**: Pydantic v2 contracts. The output `Profile` is strictly versioned and immutable.
- **`providers/`**: Declarative definitions for known targets (Qwen, DeepSeek, etc.).

## 🛠️ Development

We use `ruff` for linting/formatting, `mypy` for strict type checking, and `pytest` for testing.

```bash
# Run the linter
ruff check .

# Run the type checker
mypy src

# Run the offline test suite (83 tests)
pytest -m "not network"
```

## 📄 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
