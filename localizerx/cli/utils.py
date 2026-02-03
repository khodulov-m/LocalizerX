"""Shared utilities for CLI commands."""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

# Shared console instance
console = Console()


def create_progress() -> Progress:
    """Create a configured Progress instance for CLI operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )
