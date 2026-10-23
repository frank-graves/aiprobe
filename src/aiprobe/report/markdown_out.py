"""Markdown report renderer."""

from __future__ import annotations

from aiprobe.models.findings import DetectorStatus, Finding
from aiprobe.models.profile import Profile


def render_markdown(profile: Profile, findings: dict[str, Finding]) -> str:
    """Render a Profile and findings as a human-readable Markdown string."""
    lines = [
        f"# aiprobe report: {profile.target}",
        "",
        f"**Schema Version:** {profile.schema_version} | "
        f"**Detected At:** {profile.detected_at.isoformat()}",
        "",
        "## Anti-bot & Transport",
        "",
        "| Feature | Value |",
        "|---|---|",
        f"| Anti-bot type | `{profile.antibot.type.value}` |",
        f"| Bypass strategy | `{profile.antibot.bypass.value}` |",
        f"| TLS Fingerprint | `{profile.transport.tls_fingerprint or 'none'}` |",
        f"| HTTP/2 | `{profile.transport.http2}` |",
        "",
        "## Authentication",
        "",
        "| Feature | Value |",
        "|---|---|",
        f"| Scheme | `{profile.auth.scheme.value}` |",
        f"| Cookies | {', '.join(profile.auth.cookies) or 'none'} |",
        f"| Refresh | `{profile.auth.refresh.value}` |",
        "",
        "## Format & Capabilities",
        "",
        "| Feature | Value |",
        "|---|---|",
        f"| Stream format | `{profile.stream_format.value}` |",
        f"| Tool calling | `{profile.tool_calling}` |",
        f"| Schema compat | `{profile.schema_compat.value}` |",
        "",
        "## Discovered Endpoints",
        "",
    ]

    if profile.endpoints:
        lines.extend(
            [
                "| Name | Method | Path | Auth Required | Validated |",
                "|---|---|---|---|---|",
            ]
        )
        for name, ep in profile.endpoints.items():
            lines.append(
                f"| {name} | `{ep.method}` | `{ep.path}` | {ep.requires_auth} | {ep.validated} |"
            )
    else:
        lines.append("*No endpoints discovered.*")

    lines.extend(["", "## Warnings", ""])
    has_warnings = False
    for name, f in findings.items():
        if f.status in (DetectorStatus.FAILED, DetectorStatus.SKIPPED):
            lines.append(f"- **{name}**: {f.status.value} - `{f.error or 'No error provided'}`")
            has_warnings = True

    if not has_warnings:
        lines.append("*All detectors ran successfully.*")

    lines.append("")
    return "\n".join(lines)
