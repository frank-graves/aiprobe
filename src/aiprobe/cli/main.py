"""CLI entry point using Typer."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

import typer

from aiprobe import __version__
from aiprobe.cli.commands.detect import detect_cmd
from aiprobe.cli.commands.probe import probe_cmd
from aiprobe.cli.commands.validate import validate_cmd
from aiprobe.cli.state import app_state  # <-- Importar desde state.py

app = typer.Typer(
    name="aiprobe",
    help="FOSS CLI to probe and profile the internal APIs of AI web apps.",
    no_args_is_help=True,
)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    session_store: Path | None = typer.Option(None, "--session-store"),
    concurrency: int = typer.Option(5, "--concurrency"),
    skip_browser: bool = typer.Option(False, "--skip-browser"),
    skip_expensive: bool = typer.Option(False, "--skip-expensive"),
    no_encrypt: bool = typer.Option(False, "--no-encrypt"),
    log_format: str = typer.Option("text", "--log-format"),
    stats: bool = typer.Option(False, "--stats"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    retry_attempts: int = typer.Option(3, "--retry-attempts"),
    timeout: float = typer.Option(30.0, "--timeout"),
) -> None:
    """Global configuration for aiprobe."""
    from aiprobe.utils.log import setup_logging

    setup_logging("DEBUG" if verbose else "INFO")

    app_state.update(
        {
            "session_store": session_store or Path(".aiprobe/sessions"),
            "concurrency": concurrency,
            "skip_browser": skip_browser,
            "skip_expensive": skip_expensive,
            "no_encrypt": no_encrypt,
            "log_format": log_format,
            "stats": stats,
            "dry_run": dry_run,
            "retry_attempts": retry_attempts,
            "timeout": timeout,
        }
    )


def _handle_sigint(signum: int, frame: object) -> None:
    typer.secho("\nInterrupted by user. Exiting gracefully...", fg="yellow")
    sys.exit(130)


@app.command()
def version() -> None:
    """Print the aiprobe version."""
    typer.echo(f"aiprobe {__version__}")


signal.signal(signal.SIGINT, _handle_sigint)

app.command(name="probe")(probe_cmd)
app.command(name="detect")(detect_cmd)
app.command(name="validate")(validate_cmd)
