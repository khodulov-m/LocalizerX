"""CLI for LocalizerX."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from localizerx import __version__
from localizerx.config import (
    DEFAULT_MODEL,
    GEMINI_MODELS,
    Config,
    create_default_config,
    get_cache_dir,
    load_config,
)
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import Translation
from localizerx.translator.base import TranslationRequest
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.utils.locale import (
    get_language_name,
    parse_language_list,
    validate_language_code,
)

app = typer.Typer(
    name="localizerx",
    help="Translate Xcode String Catalogs (.xcstrings) using Gemini API",
    invoke_without_command=True,
)
console = Console()


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
            "--to", "-t",
            help="Target languages (comma-separated, e.g., 'fr,es,de')",
        ),
    ] = None,
    src: Annotated[
        str,
        typer.Option(
            "--src", "-s",
            help="Source language",
        ),
    ] = "en",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n",
            help="Show what would be translated without making changes",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview", "-p",
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
            "--config", "-c",
            help="Path to configuration file",
        ),
    ] = None,
    batch_size: Annotated[
        Optional[int],
        typer.Option(
            "--batch-size",
            help="Number of strings per API call",
            min=1,
            max=50,
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model", "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
) -> None:
    """LocalizerX - Translate Xcode String Catalogs using Gemini API.

    Quick usage: localizerx --to ru,fr,de
    """
    # If no subcommand and --to is provided, run translate
    if ctx.invoked_subcommand is None and to is not None:
        _run_translate(
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
def translate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to .xcstrings file or directory (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to", "-t",
            help="Target languages (comma-separated, e.g., 'fr,es,de')",
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option(
            "--src", "-s",
            help="Source language",
        ),
    ] = "en",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n",
            help="Show what would be translated without making changes",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview", "-p",
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
            "--backup", "-b",
            help="Create backup before writing changes",
        ),
    ] = True,
    config_path: Annotated[
        Optional[Path],
        typer.Option(
            "--config", "-c",
            help="Path to configuration file",
        ),
    ] = None,
    batch_size: Annotated[
        Optional[int],
        typer.Option(
            "--batch-size",
            help="Number of strings per API call",
            min=1,
            max=50,
        ),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model", "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
) -> None:
    """Translate an .xcstrings file to target languages."""
    if not to:
        console.print("[red]Error:[/red] --to option is required (e.g., --to ru,fr,de)")
        raise typer.Exit(1)

    _run_translate(
        path=path,
        to=to,
        src=src,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=backup,
        config_path=config_path,
        batch_size=batch_size,
        model=model,
    )


def _run_translate(
    path: Path | None,
    to: str,
    src: str,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    config_path: Path | None,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Core translation logic."""
    # Load configuration
    config = load_config(config_path)

    # Parse target languages
    target_langs = parse_language_list(to)
    if not target_langs:
        console.print("[red]Error:[/red] No valid target languages specified")
        raise typer.Exit(1)

    # Validate languages
    invalid_langs = [lang for lang in target_langs if not validate_language_code(lang)]
    if invalid_langs:
        codes = ", ".join(invalid_langs)
        console.print(f"[yellow]Warning:[/yellow] Unrecognized language codes: {codes}")

    # Validate model
    if model and model not in GEMINI_MODELS:
        console.print(
            f"[yellow]Warning:[/yellow] Unknown model '{model}'. "
            "Use 'localizerx models' to see available models."
        )

    # Auto-detect xcstrings files if path not provided
    if path is None:
        search_path = Path.cwd()
        files = _find_xcstrings_files(search_path)
        if not files:
            console.print("[red]Error:[/red] No .xcstrings files found in current directory")
            raise typer.Exit(1)

        # If multiple files found, prompt user to select
        if len(files) > 1:
            files = _prompt_file_selection(files)
            if not files:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)
    else:
        # Validate path exists
        if not path.exists():
            console.print(f"[red]Error:[/red] Path does not exist: {path}")
            raise typer.Exit(1)
        files = _find_xcstrings_files(path)
        if not files:
            console.print(f"[red]Error:[/red] No .xcstrings files found at {path}")
            raise typer.Exit(1)

    console.print(f"Found {len(files)} .xcstrings file(s)")
    console.print(f"Source: {get_language_name(src)} ({src})")
    target_display = ", ".join(f"{get_language_name(lang)} ({lang})" for lang in target_langs)
    console.print(f"Targets: {target_display}")
    console.print()

    # Process each file
    for file_path in files:
        _process_file(
            file_path=file_path,
            source_lang=src,
            target_langs=target_langs,
            config=config,
            dry_run=dry_run,
            preview=preview,
            overwrite=overwrite,
            backup=backup,
            batch_size=batch_size,
            model=model,
        )


def _find_xcstrings_files(path: Path) -> list[Path]:
    """Find all .xcstrings files in path."""
    if path.is_file():
        if path.suffix == ".xcstrings":
            return [path]
        return []

    return sorted(path.rglob("*.xcstrings"))


def _prompt_file_selection(files: list[Path]) -> list[Path]:
    """Prompt user to select which files to translate."""
    console.print(f"Found {len(files)} .xcstrings file(s):\n")

    for i, f in enumerate(files, 1):
        # Show relative path from cwd for readability
        try:
            rel_path = f.relative_to(Path.cwd())
        except ValueError:
            rel_path = f
        console.print(f"  [cyan]{i}[/cyan]. {rel_path}")

    console.print("\n  [cyan]a[/cyan]. All files")
    console.print()

    choice = typer.prompt("Select file(s) to translate (number, comma-separated, or 'a' for all)")
    choice = choice.strip().lower()

    if choice == "a":
        return files

    # Parse selection
    selected = []
    try:
        for part in choice.split(","):
            part = part.strip()
            if "-" in part:
                # Range like "1-3"
                start, end = map(int, part.split("-"))
                for i in range(start, end + 1):
                    if 1 <= i <= len(files):
                        selected.append(files[i - 1])
            else:
                idx = int(part)
                if 1 <= idx <= len(files):
                    selected.append(files[idx - 1])
    except ValueError:
        console.print("[red]Error:[/red] Invalid selection")
        return []

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for f in selected:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    return unique


def _process_file(
    file_path: Path,
    source_lang: str,
    target_langs: list[str],
    config: Config,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Process a single xcstrings file."""
    console.print(f"[bold]Processing:[/bold] {file_path}")

    # Read file
    catalog = read_xcstrings(file_path)
    console.print(f"  Found {len(catalog.strings)} string(s)")

    # Collect entries to translate per language
    translation_tasks: dict[str, list[tuple[str, str, str | None]]] = {}

    for target_lang in target_langs:
        entries_to_translate = []
        for key, entry in catalog.strings.items():
            if not entry.needs_translation:
                continue

            # Skip if translation exists and not overwriting
            if target_lang in entry.translations and not overwrite:
                continue

            entries_to_translate.append((key, entry.source_text, entry.comment))

        if entries_to_translate:
            translation_tasks[target_lang] = entries_to_translate

    if not translation_tasks:
        console.print("  [green]All strings already translated[/green]")
        return

    # Show summary
    for lang, entries in translation_tasks.items():
        console.print(f"  {get_language_name(lang)}: {len(entries)} string(s) to translate")

    if dry_run:
        console.print("  [yellow]Dry run - no changes made[/yellow]")
        _show_dry_run_table(translation_tasks)
        return

    # Perform translation
    asyncio.run(
        _translate_file(
            catalog=catalog,
            file_path=file_path,
            source_lang=source_lang,
            translation_tasks=translation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            batch_size=batch_size,
            model=model,
        )
    )


def _show_dry_run_table(tasks: dict[str, list[tuple[str, str, str | None]]]) -> None:
    """Show table of strings that would be translated."""
    table = Table(title="Strings to Translate")
    table.add_column("Key", style="cyan")
    table.add_column("Source Text", style="white")
    table.add_column("Languages", style="green")

    # Collect all unique entries
    entries: dict[str, tuple[str, set[str]]] = {}
    for lang, items in tasks.items():
        for key, text, _ in items:
            if key not in entries:
                entries[key] = (text, set())
            entries[key][1].add(lang)

    for key, (text, langs) in list(entries.items())[:20]:
        display_text = text[:50] + "..." if len(text) > 50 else text
        table.add_row(key[:40], display_text, ", ".join(sorted(langs)))

    if len(entries) > 20:
        table.add_row("...", f"({len(entries) - 20} more)", "")

    console.print(table)


async def _translate_file(
    catalog,
    file_path: Path,
    source_lang: str,
    translation_tasks: dict[str, list[tuple[str, str, str | None]]],
    config: Config,
    preview: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Perform translations and update catalog."""
    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.translator.batch_size
    actual_model = model or config.translator.model

    async with GeminiTranslator(
        model=actual_model,
        batch_size=actual_batch_size,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        all_translations: dict[str, dict[str, str]] = {}  # key -> {lang: translation}

        for target_lang, entries in translation_tasks.items():
            console.print(f"  Translating to {get_language_name(target_lang)}...")

            requests = [
                TranslationRequest(key=key, text=text, comment=comment)
                for key, text, comment in entries
            ]

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"    {target_lang}", total=len(requests))

                results = await translator.translate_batch(
                    requests, source_lang, target_lang
                )

                for result in results:
                    if result.success and result.translated:
                        if result.key not in all_translations:
                            all_translations[result.key] = {}
                        all_translations[result.key][target_lang] = result.translated
                    progress.advance(task)

        # Show preview if requested
        if preview:
            _show_preview_table(all_translations, catalog)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog
        for key, translations in all_translations.items():
            if key in catalog.strings:
                for lang, value in translations.items():
                    catalog.strings[key].translations[lang] = Translation(value=value)

        # Write file
        write_xcstrings(catalog, file_path, backup=backup)
        console.print(f"  [green]Saved {file_path}[/green]")


def _show_preview_table(translations: dict[str, dict[str, str]], catalog) -> None:
    """Show preview of translations."""
    table = Table(title="Translation Preview")
    table.add_column("Key", style="cyan")
    table.add_column("Source", style="white")
    table.add_column("Language", style="yellow")
    table.add_column("Translation", style="green")

    count = 0
    for key, lang_translations in translations.items():
        source = catalog.strings[key].source_text if key in catalog.strings else ""
        source_display = source[:30] + "..." if len(source) > 30 else source

        for lang, trans in lang_translations.items():
            trans_display = trans[:40] + "..." if len(trans) > 40 else trans
            table.add_row(key[:25], source_display, lang, trans_display)
            count += 1
            if count >= 30:
                break
        if count >= 30:
            break

    if len(translations) > 30:
        table.add_row("...", "", "", f"({sum(len(t) for t in translations.values()) - 30} more)")

    console.print(table)


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


@app.command()
def info(
    path: Annotated[
        Path,
        typer.Argument(help="Path to .xcstrings file", exists=True),
    ],
) -> None:
    """Show information about an .xcstrings file."""
    if path.suffix != ".xcstrings":
        console.print("[red]Error:[/red] Not an .xcstrings file")
        raise typer.Exit(1)

    catalog = read_xcstrings(path)

    console.print(f"[bold]File:[/bold] {path}")
    console.print(f"[bold]Source Language:[/bold] {catalog.source_language}")
    console.print(f"[bold]Total Strings:[/bold] {len(catalog.strings)}")

    # Count translations per language
    lang_counts: dict[str, int] = {}
    for entry in catalog.strings.values():
        for lang in entry.translations:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    if lang_counts:
        console.print("\n[bold]Translations:[/bold]")
        table = Table()
        table.add_column("Language", style="cyan")
        table.add_column("Translated", style="green")
        table.add_column("Coverage", style="yellow")

        total = len(catalog.strings)
        for lang, count in sorted(lang_counts.items()):
            pct = (count / total * 100) if total > 0 else 0
            table.add_row(
                f"{get_language_name(lang)} ({lang})",
                str(count),
                f"{pct:.1f}%",
            )

        console.print(table)
    else:
        console.print("\n[yellow]No translations found[/yellow]")


if __name__ == "__main__":
    app()
