"""Shared utilities for CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from localizerx.utils.formality import FORMALITY_AUTO, normalize_formality

# Shared console instance
console = Console()

FORMALITY_HELP = (
    "Form of address in the target language: 'informal' (du/tu/ты), "
    "'formal' (Sie/vous/вы) or 'auto'. Overrides the config value."
)


def resolve_formality(cli_value: str | None, config_value: str | None = None) -> str:
    """Resolve the effective formality from the CLI flag and the config value."""
    try:
        if cli_value:
            return normalize_formality(cli_value)
        return normalize_formality(config_value)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def announce_formality(formality: str) -> None:
    """Print the chosen form of address unless it is left to the model."""
    if formality != FORMALITY_AUTO:
        console.print(f"[dim]Form of address: {formality}[/dim]")


def create_progress() -> Progress:
    """Create a configured Progress instance for CLI operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )
