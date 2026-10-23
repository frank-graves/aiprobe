"""`aiprobe probe <target>` command."""

from __future__ import annotations

import asyncio
import re
import sys
from enum import StrEnum
from pathlib import Path

import typer

from aiprobe.cli.state import app_state
from aiprobe.core.browser import get_browser_driver
from aiprobe.core.encrypted_store import EncryptedSessionStore
from aiprobe.core.http import CurlCffiClient
from aiprobe.core.orchestrator import Orchestrator, OrchestratorConfig
from aiprobe.core.pipeline import resolve_steps
from aiprobe.core.session import FileSessionStore, SessionManager, SessionStore
from aiprobe.providers.base import PROVIDERS
from aiprobe.report.json_out import render_json
from aiprobe.report.markdown_out import render_markdown
from aiprobe.report.yaml_out import render_yaml
from aiprobe.utils.crypto import generate_key, load_key


class OutputFormat(StrEnum):
    yaml = "yaml"
    json = "json"
    md = "md"


def probe_cmd(
    target: str = typer.Argument(..., help="Target domain or URL"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Save to a specific file."),
    out_dir: Path | None = typer.Option(
        None, "--out-dir", help="Directory to auto-save all formats."
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.yaml, "--format", help="Output format if printing to stdout."
    ),
) -> None:
    """Run the full pipeline and output a profile."""
    asyncio.run(_probe(target, output, out_dir, format))


async def _probe(target: str, output: Path | None, out_dir: Path | None, fmt: OutputFormat) -> None:
    base_target = target if target.startswith("http") else f"https://{target}"

    # Extraer el dominio limpio para usarlo como nombre de carpeta
    domain = base_target.replace("https://", "").replace("http://", "").split("/")[0]
    safe_domain = re.sub(r"[^a-zA-Z0-9_\-]", "_", domain)

    store_path = app_state.get("session_store")
    if not isinstance(store_path, Path):
        store_path = Path(".aiprobe/sessions")

    raw_store: SessionStore = FileSessionStore(store_path)
    store: SessionStore = raw_store
    if not app_state.get("no_encrypt"):
        key_path = store_path.parent / "key.bin"
        if not key_path.exists():
            store_path.mkdir(parents=True, exist_ok=True)
            generate_key(key_path)
        key = load_key(key_path)
        store = EncryptedSessionStore(raw_store, key)

    def client_factory(session: object) -> CurlCffiClient:
        return CurlCffiClient(cookies=getattr(session, "cookies", {}))

    sm = SessionManager(store, client_factory)

    browser_driver = None
    if not app_state.get("skip_browser"):
        try:
            browser_driver = get_browser_driver()
        except RuntimeError:
            typer.secho("Warning: patchright not installed.", fg="yellow")

    config = OrchestratorConfig(
        skip_expensive=bool(app_state.get("skip_expensive")),
        skip_browser=bool(app_state.get("skip_browser")),
        browser_driver=browser_driver,
    )

    steps = resolve_steps()
    orchestrator = Orchestrator(steps, sm, config)

    spec = None
    for p_cls in PROVIDERS.values():
        if domain in p_cls.get_spec().domains:
            spec = p_cls.get_spec()
            break

    typer.secho(f"Starting probe for {base_target}...", fg="cyan")

    try:
        findings = await orchestrator.run(base_target, spec)
        profile = await orchestrator.assemble_profile(base_target, findings)
    except Exception as exc:
        typer.secho(f"Fatal error during probe: {exc}", fg="red", err=True)
        sys.exit(1)

    # --- Lógica de guardado estructurado ---
    if out_dir:
        target_dir = out_dir / safe_domain
        target_dir.mkdir(parents=True, exist_ok=True)

        (target_dir / "profile.yaml").write_text(render_yaml(profile), encoding="utf-8")
        (target_dir / "profile.json").write_text(render_json(profile), encoding="utf-8")
        (target_dir / "report.md").write_text(render_markdown(profile, findings), encoding="utf-8")

        typer.secho(f"All outputs saved to {target_dir}/", fg="green")
        typer.secho("  - profile.yaml", fg="green")
        typer.secho("  - profile.json", fg="green")
        typer.secho("  - report.md", fg="green")
        return

    # --- Lógica de guardado manual (legacy) ---
    if fmt == OutputFormat.yaml:
        out_str = render_yaml(profile)
    elif fmt == OutputFormat.json:
        out_str = render_json(profile)
    else:
        out_str = render_markdown(profile, findings)

    if output:
        output.write_text(out_str, encoding="utf-8")
        typer.secho(f"Profile written to {output}", fg="green")
    else:
        typer.echo(out_str)
