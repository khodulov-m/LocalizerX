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
    get_cache_dir,
    load_config,
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
    delete,
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
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Create backup before writing changes",
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
            help="Gemini model to use (see 'localizerx list' for list)",
        ),
    ] = None,
    temperature: Annotated[
        Optional[float],
        typer.Option(
            "--temperature",
            "-T",
            help="Sampling temperature (0.0–2.0). Lower = more deterministic.",
            min=0.0,
            max=2.0,
        ),
    ] = None,
    custom_prompt: Annotated[
        Optional[str],
        typer.Option(
            "--custom-prompt",
            "--instructions",
            help="Custom instructions for translation (e.g., 'Do not translate proper names')",
        ),
    ] = None,
    no_app_context: Annotated[
        bool,
        typer.Option(
            "--no-app-context",
            help="Disable automatic app context extraction (name, subtitle, description) from metadata or project files.",
        ),
    ] = False,
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
            backup=backup,
            config_path=config_path,
            batch_size=batch_size,
            model=model,
            temperature=temperature,
            custom_prompt=custom_prompt,
            no_app_context=no_app_context,
            refresh=False,
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


@app.command("list")
def list_models() -> None:
    """List available Gemini models from the API."""
    import os

    import httpx

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error: GEMINI_API_KEY environment variable is not set.[/red]")
        raise typer.Exit(1)

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        models = [m["name"].replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]

        table = Table(title="Available Gemini Models")
        table.add_column("Model", style="cyan")

        for m in models:
            table.add_row(m)

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching models: {e}[/red]")
        raise typer.Exit(1)


@app.command("use")
def use_model(
    model: Annotated[str, typer.Argument(help="Gemini model to use")],
    thinking_level: Annotated[
        str,
        typer.Option(
            "--thinking-level",
            help="Thinking level (minimal, low, medium, high) or 0 to disable",
        ),
    ] = "0",
) -> None:
    """Set the specified model and thinking level in config.toml."""
    import re

    from localizerx.config import DEFAULT_CONFIG_PATH, create_default_config

    config_path = DEFAULT_CONFIG_PATH
    if not config_path.exists():
        console.print("[yellow]Config file not found, creating default...[/yellow]")
        create_default_config(config_path)

    content = config_path.read_text()

    # Update model in [translator]
    section_pattern = re.compile(r"^\[translator\]$", re.MULTILINE)
    match = section_pattern.search(content)
    if not match:
        content += f"\n[translator]\nmodel = \"{model}\"\nthinking_level = \"{thinking_level}\"\n"
    else:
        # Extract the translator section
        start = match.end()
        next_section = re.search(r"^\[.*?\]", content[start:], re.MULTILINE)
        end = start + next_section.start() if next_section else len(content)
        section_content = content[start:end]

        # Update model
        model_pattern = re.compile(r"^model\s*=\s*.*$", re.MULTILINE)
        if model_pattern.search(section_content):
            section_content = model_pattern.sub(f'model = "{model}"', section_content)
        else:
            section_content = f'model = "{model}"\n' + section_content

        # Update thinking_level
        thinking_pattern = re.compile(r"^thinking_level\s*=\s*.*$", re.MULTILINE)
        if thinking_pattern.search(section_content):
            section_content = thinking_pattern.sub(f'thinking_level = "{thinking_level}"', section_content)
        else:
            section_content += f'thinking_level = "{thinking_level}"\n'

        content = content[:start] + section_content + content[end:]

    config_path.write_text(content)
    console.print(f"[green]Successfully set model to [cyan]{model}[/cyan] with thinking_level [cyan]{thinking_level}[/cyan].[/green]")


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


@app.command("cache-clear")
def cache_clear(
    config_path: Annotated[
        Optional[Path],
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
        ),
    ] = None,
) -> None:
    """Clear the translation cache."""
    config = load_config(config_path)
    cache_dir = get_cache_dir(config)

    if cache_dir is None:
        console.print("[yellow]Caching is disabled — nothing to clear.[/yellow]")
        raise typer.Exit(0)

    db_path = cache_dir / "translations.db"
    if not db_path.exists():
        console.print("[yellow]Cache is already empty.[/yellow]")
        raise typer.Exit(0)

    size_kb = db_path.stat().st_size / 1024
    db_path.unlink()
    console.print(f"[green]Cache cleared.[/green] Removed {size_kb:.1f} KB from {db_path}")


# Register commands from modules
app.command()(translate.translate)
app.command()(translate.info)
app.command()(delete.delete)
app.command()(metadata.metadata)
app.command("metadata-info")(metadata.metadata_info)
app.command("metadata-check")(metadata.metadata_check)
app.command("metadata-urls")(metadata.metadata_urls)
app.command()(chrome.chrome)
app.command("chrome-info")(chrome.chrome_info)
app.command("i18n")(i18n.i18n_translate)
app.command("i18n-info")(i18n.i18n_info)
app.command("android")(android.android_translate)
app.command("android-info")(android.android_info)
app.command("screenshots")(screenshots.screenshots_translate)
app.command("screenshots-info")(screenshots.screenshots_info)
app.command("screenshots-generate")(screenshots.screenshots_generate)
