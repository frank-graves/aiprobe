"""`aiprobe validate <profile>` command."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer

from aiprobe.core.http import CurlCffiClient
from aiprobe.core.orchestrator import Orchestrator, OrchestratorConfig
from aiprobe.core.pipeline import resolve_steps
from aiprobe.core.session import FileSessionStore, SessionManager
from aiprobe.models.profile import Profile


def validate_cmd(
    profile_path: Path | None = typer.Argument(None, help="Path to the profile YAML."),
    all_profiles: bool = typer.Option(False, "--all", help="Validate all profiles in ./profiles"),
    as_json: bool = typer.Option(False, "--json", help="Output drift as JSON."),
) -> None:
    """Validate a stored profile against the live target (checks for drift)."""
    if not profile_path and not all_profiles:
        typer.secho("Error: Provide a profile path or use --all.", fg="red", err=True)
        sys.exit(3)

    paths = []
    if all_profiles:
        p = Path("profiles")
        if not p.exists():
            typer.secho("Error: profiles/ directory not found.", fg="red", err=True)
            sys.exit(3)
        paths = list(p.glob("*.yaml"))
    elif profile_path:
        paths = [profile_path]

    asyncio.run(_validate(paths, as_json))


async def _validate(paths: list[Path], as_json: bool) -> None:
    any_drift = False
    all_reports = []

    for path in paths:
        if not path.exists():
            typer.secho(f"Error: {path} not found.", fg="red", err=True)
            sys.exit(3)

        try:
            old_profile = Profile.from_yaml(path)
        except Exception as exc:
            typer.secho(f"Invalid profile format in {path}: {exc}", fg="red", err=True)
            sys.exit(3)

        if not as_json:
            typer.secho(f"Validating {old_profile.target} ({path.name})...", fg="cyan")

        steps = resolve_steps(only=["transport", "antibot", "endpoints"])
        store = FileSessionStore()
        sm = SessionManager(store, lambda s: CurlCffiClient(cookies=getattr(s, "cookies", {})))
        orchestrator = Orchestrator(steps, sm, OrchestratorConfig())

        findings = await orchestrator.run(old_profile.target)
        new_profile = await orchestrator.assemble_profile(old_profile.target, findings)

        drift = []
        if old_profile.transport.http2 != new_profile.transport.http2:
            drift.append(
                {
                    "field": "transport.http2",
                    "old": old_profile.transport.http2,
                    "new": new_profile.transport.http2,
                }
            )
        if old_profile.antibot.type != new_profile.antibot.type:
            drift.append(
                {
                    "field": "antibot.type",
                    "old": old_profile.antibot.type.value,
                    "new": new_profile.antibot.type.value,
                }
            )

        for name in set(old_profile.endpoints.keys()) | set(new_profile.endpoints.keys()):
            old_ep = old_profile.endpoints.get(name)
            new_ep = new_profile.endpoints.get(name)

            if old_ep and not new_ep:
                drift.append({"endpoint": name, "action": "removed"})
            elif not old_ep and new_ep:
                drift.append(
                    {
                        "endpoint": name,
                        "action": "added",
                        "method": new_ep.method,
                        "path": new_ep.path,
                    }
                )
            elif (
                old_ep and new_ep and (old_ep.path != new_ep.path or old_ep.method != new_ep.method)
            ):
                drift.append(
                    {
                        "endpoint": name,
                        "action": "changed",
                        "old": f"{old_ep.method} {old_ep.path}",
                        "new": f"{new_ep.method} {new_ep.path}",
                    }
                )

        if drift:
            any_drift = True
            if not as_json:
                for d in drift:
                    typer.secho(f"  DRIFT: {d}", fg="yellow")
        elif not as_json:
            typer.secho("  No drift detected.", fg="green")

        all_reports.append({"target": old_profile.target, "drift": drift})

    if as_json:
        typer.echo(json.dumps({"results": all_reports}, indent=2))

    if any_drift:
        sys.exit(2)
    sys.exit(0)
