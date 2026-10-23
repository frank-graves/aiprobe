"""`aiprobe detect <target>` command."""

from __future__ import annotations

import asyncio

import typer

from aiprobe.core.http import CurlCffiClient
from aiprobe.core.orchestrator import Orchestrator, OrchestratorConfig
from aiprobe.core.pipeline import resolve_steps
from aiprobe.core.session import FileSessionStore, SessionManager


def detect_cmd(
    target: str = typer.Argument(..., help="Target URL"),
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category."),
    only: str | None = typer.Option(None, "--only", help="Comma-separated list of detectors."),
) -> None:
    """Run a subset of detectors without generating a profile."""
    asyncio.run(_detect(target, category, only))


async def _detect(target: str, category: str | None, only: str | None) -> None:
    base_target = target if target.startswith("http") else f"https://{target}"

    # Setup minimal pipeline
    only_list = [x.strip() for x in only.split(",")] if only else None
    steps = resolve_steps(only=only_list)

    store = FileSessionStore()
    sm = SessionManager(store, lambda s: CurlCffiClient(cookies=getattr(s, "cookies", {})))
    config = OrchestratorConfig()
    orchestrator = Orchestrator(steps, sm, config)

    typer.secho(f"Detecting on {base_target}...", fg="cyan")
    findings = await orchestrator.run(base_target)

    typer.echo("\n--- Detection Results ---")
    for name, f in findings.items():
        if category and f.category != category:
            continue

        color = "green" if f.status == "detected" else "yellow" if f.status == "skipped" else "red"
        typer.secho(f"[{f.status.upper()}] {name} (conf: {f.confidence:.2f})", fg=color)
        if f.error:
            typer.secho(f"  Error: {f.error}", fg="red")
        else:
            typer.echo(f"  Data: {f.data}")
