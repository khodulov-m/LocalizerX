"""CLI for LocalizerX."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx import __version__
from localizerx.cli.utils import console
from localizerx.config import (
    DEFAULT_MODEL,
    GEMINI_MODELS,
    create_default_config,
)

# Create the main app first
app = typer.Typer(
    name="localizerx",
    help="Translate Xcode String Catalogs (.xcstrings) using Gemini API",
    invoke_without_command=True,
)

# Import command modules after app is created (circular import prevention)
from localizerx.cli import (  # noqa: E402
    android,
    chrome,
    i18n,
    metadata,
    screenshots,
    translate,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"LocalizerX version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            "-t",
            help=(
                "Target languages (comma-separated, e.g., 'fr,es,de')."
                " Omit to use defaults from config."
            ),
        ),
    ] = None,
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source language",
        ),
    ] = "en",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be translated without making changes",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            "-p",
            help="Show proposed translations before applying",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing translations",
        ),
    ] = False,
    no_backup: Annotated[
        bool,
        typer.Option(
            "--no-backup",
            help="Don't create backup before writing changes",
        ),
    ] = False,
    config_path: Annotated[
        Optional[Path],
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
        ),
    ] = None,
    batch_size: Annotated[
        Optional[int],
        typer.Option(
            "--batch-size",
            help="Number of strings per API call",
            min=1,
            max=100,
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
) -> None:
    """LocalizerX - Translate Xcode String Catalogs using Gemini API.

    Quick usage: localizerx --to ru,fr,de
    Or use default targets: localizerx translate
    """
    # If no subcommand and --to is provided, run translate
    if ctx.invoked_subcommand is None and to is not None:
        translate._run_translate(
            path=None,
            to=to,
            src=src,
            dry_run=dry_run,
            preview=preview,
            overwrite=overwrite,
            backup=not no_backup,
            config_path=config_path,
            batch_size=batch_size,
            model=model,
        )
    elif ctx.invoked_subcommand is None:
        # No subcommand and no --to, show help
        console.print(ctx.get_help())
        raise typer.Exit(0)


@app.command()
def init(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Path for config file"),
    ] = None,
) -> None:
    """Create a default configuration file."""
    config_path = create_default_config(path)
    console.print(f"[green]Created configuration file:[/green] {config_path}")


@app.command()
def models() -> None:
    """List available Gemini models."""
    table = Table(title="Available Gemini Models")
    table.add_column("Model", style="cyan")
    table.add_column("Default", style="green")

    for model in GEMINI_MODELS:
        is_default = "✓" if model == DEFAULT_MODEL else ""
        table.add_row(model, is_default)

    console.print(table)
    console.print("\nUse [cyan]--model[/cyan] option or set in config.toml")


@app.command()
def languages() -> None:
    """List supported language codes."""
    from localizerx.utils.locale import LANGUAGE_NAMES

    table = Table(title="Supported Languages")
    table.add_column("Code", style="cyan")
    table.add_column("Language", style="white")

    for code, name in sorted(LANGUAGE_NAMES.items()):
        table.add_row(code, name)

    console.print(table)


# Register commands from modules
app.command()(translate.translate)
app.command()(translate.info)
app.command()(metadata.metadata)
app.command("metadata-info")(metadata.metadata_info)
app.command("metadata-check")(metadata.metadata_check)
app.command()(chrome.chrome)
app.command("chrome-info")(chrome.chrome_info)
app.command("i18n")(i18n.i18n_translate)
app.command("i18n-info")(i18n.i18n_info)
app.command("android")(android.android_translate)
app.command("android-info")(android.android_info)
app.command("screenshots")(screenshots.screenshots_translate)
app.command("screenshots-info")(screenshots.screenshots_info)
app.command("screenshots-generate")(screenshots.screenshots_generate)
