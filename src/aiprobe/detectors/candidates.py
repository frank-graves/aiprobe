"""Declarative candidate generation for endpoint discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass

from aiprobe.providers.base import ProviderSpec


@dataclass(frozen=True)
class EndpointCandidate:
    """A potential API endpoint to probe."""

    name: str
    path: str
    method: str
    source: str


CANONICAL_NAMES: list[str] = [
    "chat",
    "completions",
    "models",
    "stream",
    "upload",
    "auth",
    "session",
    "usage",
]

PATH_PATTERNS: list[str] = [
    "/api/v1/{name}",
    "/api/v2/{name}",
    "/v1/{name}",
    "/api/{name}",
    "/api/v2/chat/completions",
    "/v1/chat/completions",
    "/api/chat/completions",
]

_STATIC_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".svg",
    ".woff",
    ".woff2",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".map",
}

_PATH_REGEX = re.compile(r'["\'](/[a-zA-Z0-9_\-/.]+)(?:\?[^"\'\s]*)?["\']')


def generate_candidates(provider_spec: ProviderSpec | None = None) -> list[EndpointCandidate]:
    """Generate a deduplicated list of endpoint candidates."""
    candidates: list[EndpointCandidate] = []

    if provider_spec:
        for name, path in provider_spec.candidate_endpoints.items():
            method = "POST" if name in ("chat", "completions", "stream") else "GET"
            candidates.append(
                EndpointCandidate(name=name, path=path, method=method, source="provider")
            )

    for pattern in PATH_PATTERNS:
        if "{name}" in pattern:
            for name in CANONICAL_NAMES:
                path = pattern.format(name=name)
                method = "POST" if name in ("chat", "completions", "stream") else "GET"
                candidates.append(
                    EndpointCandidate(name=name, path=path, method=method, source="pattern")
                )
        else:
            name = pattern.strip("/").split("/")[-1]
            method = "POST" if "chat" in name else "GET"
            candidates.append(
                EndpointCandidate(name=name, path=pattern, method=method, source="pattern")
            )

    unique: dict[tuple[str, str], EndpointCandidate] = {}
    for c in candidates:
        key = (c.method, c.path)
        if key not in unique or (unique[key].source == "pattern" and c.source == "provider"):
            unique[key] = c

    return list(unique.values())


def extract_paths_from_html(html: str) -> set[str]:
    """Extract potential API paths from an HTML/JS bundle string."""
    paths: set[str] = set()
    for match in _PATH_REGEX.finditer(html):
        path = match.group(1).split("?")[0]

        if "." in path:
            ext = "." + path.split(".")[-1].lower()
            if ext in _STATIC_EXTENSIONS:
                continue

        if path.startswith(("/api", "/v1", "/v2")):
            paths.add(path)

    return paths
