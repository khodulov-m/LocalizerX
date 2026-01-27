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
    chrome_to_standard_locale,
    get_chrome_locale_name,
    get_fastlane_locale_name,
    get_language_name,
    parse_chrome_locale_list,
    parse_fastlane_locale_list,
    parse_language_list,
    validate_chrome_locale,
    validate_fastlane_locale,
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
            "--to",
            "-t",
            help="Target languages (comma-separated, e.g., 'fr,es,de'). Omit to use defaults from config.",
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
        Optional[str],
        typer.Option(
            "--to",
            "-t",
            help="Target languages (comma-separated, e.g., 'fr,es,de'). Omit to use defaults from config.",
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
    ] = True,
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
    """Translate an .xcstrings file to target languages.

    If --to is omitted, uses default_targets from config.
    """
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
    to: str | None,
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

    # Parse target languages (use config defaults if not specified)
    if to:
        target_langs = parse_language_list(to)
    else:
        target_langs = config.default_targets.copy()
        if target_langs:
            console.print(
                f"[dim]Using default targets from config ({len(target_langs)} languages)[/dim]"
            )

    if not target_langs:
        console.print("[red]Error:[/red] No target languages specified")
        console.print("Use --to option or set default_targets in config.toml")
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

                results = await translator.translate_batch(requests, source_lang, target_lang)

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


@app.command()
def metadata(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to fastlane metadata directory (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Target locales (comma-separated, e.g., 'de-DE,fr-FR,es-ES')",
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source locale",
        ),
    ] = "en-US",
    fields: Annotated[
        Optional[str],
        typer.Option(
            "--fields",
            "-f",
            help="Fields to translate (comma-separated: name,subtitle,keywords,etc.)",
        ),
    ] = None,
    on_limit: Annotated[
        str,
        typer.Option(
            "--on-limit",
            help="Action when translation exceeds character limit: warn, truncate, or error",
        ),
    ] = "warn",
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
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
) -> None:
    """Translate fastlane App Store metadata to target locales."""
    if not to:
        console.print("[red]Error:[/red] --to option is required (e.g., --to de-DE,fr-FR)")
        raise typer.Exit(1)

    # Validate on_limit option
    from localizerx.utils.limits import LimitAction

    try:
        limit_action = LimitAction(on_limit)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid --on-limit value: {on_limit}")
        console.print("Valid options: warn, truncate, error")
        raise typer.Exit(1)

    _run_metadata_translate(
        path=path,
        to=to,
        src=src,
        fields=fields,
        limit_action=limit_action,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=not no_backup,
        model=model,
    )


@app.command("metadata-info")
def metadata_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to fastlane metadata directory (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about fastlane metadata files."""
    from localizerx.io.metadata import detect_metadata_path, read_metadata
    from localizerx.parser.metadata_model import FIELD_LIMITS, MetadataFieldType

    # Find metadata path
    if path is None:
        path = detect_metadata_path()
        if path is None:
            console.print("[red]Error:[/red] No metadata directory found")
            console.print("Run from a directory with fastlane/metadata or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    # Read metadata
    try:
        catalog = read_metadata(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Metadata Directory:[/bold] {path}")
    console.print(f"[bold]Source Locale:[/bold] {catalog.source_locale}")
    console.print(f"[bold]Total Locales:[/bold] {catalog.locale_count}")
    console.print()

    # Show locale table
    table = Table(title="Locale Status")
    table.add_column("Locale", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Fields", style="green")
    table.add_column("Issues", style="yellow")

    for locale, locale_meta in sorted(catalog.locales.items()):
        locale_name = get_fastlane_locale_name(locale)
        field_count = locale_meta.field_count
        over_limit = locale_meta.get_over_limit_fields()

        issues = []
        if over_limit:
            issues.append(f"{len(over_limit)} over limit")

        issues_str = ", ".join(issues) if issues else "-"
        is_source = " (source)" if locale == catalog.source_locale else ""

        table.add_row(
            f"{locale}{is_source}",
            locale_name,
            str(field_count),
            issues_str,
        )

    console.print(table)
    console.print()

    # Show field details for source locale
    source = catalog.get_source_metadata()
    if source:
        console.print(f"[bold]Source Fields ({catalog.source_locale}):[/bold]")
        field_table = Table()
        field_table.add_column("Field", style="cyan")
        field_table.add_column("Chars", style="white")
        field_table.add_column("Limit", style="yellow")
        field_table.add_column("Status", style="green")

        for field_type in MetadataFieldType:
            field = source.get_field(field_type)
            if field:
                char_count = field.char_count
                limit = field.limit
                if field.is_over_limit:
                    status = f"[red]OVER by {field.chars_over}[/red]"
                else:
                    status = "OK"
                field_table.add_row(
                    field_type.value,
                    str(char_count),
                    str(limit),
                    status,
                )
            else:
                field_table.add_row(
                    field_type.value,
                    "-",
                    str(FIELD_LIMITS[field_type]),
                    "[dim]missing[/dim]",
                )

        console.print(field_table)


def _run_metadata_translate(
    path: Path | None,
    to: str,
    src: str,
    fields: str | None,
    limit_action,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Core metadata translation logic."""
    from localizerx.io.metadata import detect_metadata_path, read_metadata
    from localizerx.parser.metadata_model import MetadataFieldType

    # Load configuration
    config = load_config()

    # Parse target locales
    target_locales = parse_fastlane_locale_list(to)
    if not target_locales:
        console.print("[red]Error:[/red] No valid target locales specified")
        raise typer.Exit(1)

    # Validate locales
    invalid_locales = [loc for loc in target_locales if not validate_fastlane_locale(loc)]
    if invalid_locales:
        codes = ", ".join(invalid_locales)
        console.print(f"[yellow]Warning:[/yellow] Unrecognized locale codes: {codes}")

    # Parse fields filter
    field_types: list[MetadataFieldType] | None = None
    if fields:
        field_types = []
        for field_name in fields.split(","):
            field_name = field_name.strip().lower()
            try:
                field_types.append(MetadataFieldType(field_name))
            except ValueError:
                console.print(f"[yellow]Warning:[/yellow] Unknown field: {field_name}")
        if not field_types:
            console.print("[red]Error:[/red] No valid fields specified")
            raise typer.Exit(1)

    # Find metadata path
    if path is None:
        path = detect_metadata_path()
        if path is None:
            console.print("[red]Error:[/red] No metadata directory found")
            console.print("Run from a directory with fastlane/metadata or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    # Read metadata
    try:
        catalog = read_metadata(path, source_locale=src)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Check source locale exists
    source = catalog.get_source_metadata()
    if not source:
        console.print(f"[red]Error:[/red] Source locale '{src}' not found in metadata")
        console.print(f"Available locales: {', '.join(catalog.locales.keys())}")
        raise typer.Exit(1)

    console.print(f"[bold]Metadata Directory:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_fastlane_locale_name(src)} ({src})")
    target_display = ", ".join(f"{get_fastlane_locale_name(loc)} ({loc})" for loc in target_locales)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Determine fields to translate for each locale
    translation_tasks: dict[str, list[MetadataFieldType]] = {}

    for target_locale in target_locales:
        # Get fields needing translation
        needs = catalog.get_fields_needing_translation(target_locale, field_types)

        # If overwrite, translate all specified fields that exist in source
        if overwrite:
            if field_types:
                needs = [ft for ft in field_types if source.has_field(ft)]
            else:
                needs = [ft for ft in MetadataFieldType if source.has_field(ft)]

        if needs:
            translation_tasks[target_locale] = needs

    if not translation_tasks:
        console.print("[green]All fields already translated[/green]")
        return

    # Show summary
    for locale, locale_fields in translation_tasks.items():
        field_names = ", ".join(f.value for f in locale_fields)
        console.print(f"  {get_fastlane_locale_name(locale)}: {field_names}")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        _show_metadata_dry_run(catalog, translation_tasks)
        return

    # Perform translation
    asyncio.run(
        _translate_metadata(
            catalog=catalog,
            path=path,
            source_locale=src,
            translation_tasks=translation_tasks,
            config=config,
            limit_action=limit_action,
            preview=preview,
            backup=backup,
            model=model,
        )
    )


def _show_metadata_dry_run(
    catalog,
    tasks: dict[str, list],
) -> None:
    """Show table of fields that would be translated."""
    from localizerx.parser.metadata_model import FIELD_LIMITS

    source = catalog.get_source_metadata()
    if not source:
        return

    table = Table(title="Fields to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Field", style="white")
    table.add_column("Source Length", style="yellow")
    table.add_column("Limit", style="green")

    for locale, fields in tasks.items():
        for field_type in fields:
            field = source.get_field(field_type)
            if field:
                table.add_row(
                    locale,
                    field_type.value,
                    str(field.char_count),
                    str(FIELD_LIMITS[field_type]),
                )

    console.print(table)


async def _translate_metadata(
    catalog,
    path: Path,
    source_locale: str,
    translation_tasks: dict[str, list],
    config,
    limit_action,
    preview: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Perform metadata translations and update files."""
    from localizerx.io.metadata import write_metadata
    from localizerx.parser.metadata_model import MetadataFieldType
    from localizerx.translator.metadata_prompts import (
        build_keywords_prompt,
        build_metadata_prompt,
    )
    from localizerx.utils.limits import LimitAction, truncate_to_limit, validate_limit

    cache_dir = get_cache_dir(config)
    actual_model = model or config.translator.model

    source = catalog.get_source_metadata()
    if not source:
        return

    async with GeminiTranslator(
        model=actual_model,
        batch_size=1,  # Metadata fields are translated one at a time
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        all_translations: dict[str, dict[MetadataFieldType, str]] = {}
        limit_warnings: list[str] = []

        for target_locale, field_types in translation_tasks.items():
            console.print(f"  Translating to {get_fastlane_locale_name(target_locale)}...")

            all_translations[target_locale] = {}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"    {target_locale}", total=len(field_types))

                for field_type in field_types:
                    field = source.get_field(field_type)
                    if not field:
                        progress.advance(task)
                        continue

                    # Build specialized prompt
                    if field_type == MetadataFieldType.KEYWORDS:
                        prompt = build_keywords_prompt(field.content, source_locale, target_locale)
                    else:
                        prompt = build_metadata_prompt(
                            field.content, field_type, source_locale, target_locale
                        )

                    # Translate using raw API call via the translator's internal method
                    try:
                        translated = await translator._call_api(prompt)
                        translated = translated.strip()
                    except Exception as e:
                        console.print(f"    [red]Error translating {field_type.value}: {e}[/red]")
                        progress.advance(task)
                        continue

                    # Validate against limit
                    validation = validate_limit(translated, field_type)

                    if not validation.is_valid:
                        warning = (
                            f"[{target_locale}] {field_type.value}: "
                            f"{validation.char_count}/{validation.limit} chars "
                            f"(over by {validation.chars_over})"
                        )
                        limit_warnings.append(warning)

                        if limit_action == LimitAction.ERROR:
                            console.print(f"    [red]Error: {warning}[/red]")
                            raise typer.Exit(1)
                        elif limit_action == LimitAction.TRUNCATE:
                            translated = truncate_to_limit(translated, field_type)
                            console.print(f"    [yellow]Truncated: {field_type.value}[/yellow]")
                        else:  # warn
                            console.print(f"    [yellow]Warning: {warning}[/yellow]")

                    all_translations[target_locale][field_type] = translated
                    progress.advance(task)

        # Show preview if requested
        if preview:
            _show_metadata_preview(source, all_translations)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog and write files
        for target_locale, translations in all_translations.items():
            locale_meta = catalog.get_or_create_locale(target_locale)
            for field_type, value in translations.items():
                locale_meta.set_field(field_type, value)

        # Write only the translated locales
        write_metadata(
            catalog,
            path,
            backup=backup,
            locales=list(all_translations.keys()),
        )

        console.print(f"\n[green]Saved translations to {path}[/green]")

        # Show limit warnings summary
        if limit_warnings:
            console.print(f"\n[yellow]Character limit warnings ({len(limit_warnings)}):[/yellow]")
            for warning in limit_warnings[:10]:
                console.print(f"  {warning}")
            if len(limit_warnings) > 10:
                console.print(f"  ... and {len(limit_warnings) - 10} more")


def _show_metadata_preview(source, all_translations: dict) -> None:
    """Show preview of metadata translations."""
    table = Table(title="Translation Preview")
    table.add_column("Locale", style="cyan")
    table.add_column("Field", style="white")
    table.add_column("Translation", style="green")
    table.add_column("Chars", style="yellow")

    count = 0
    for locale, translations in all_translations.items():
        for field_type, value in translations.items():
            preview_value = value[:60] + "..." if len(value) > 60 else value
            preview_value = preview_value.replace("\n", " ")
            table.add_row(locale, field_type.value, preview_value, str(len(value)))
            count += 1
            if count >= 20:
                break
        if count >= 20:
            break

    total = sum(len(t) for t in all_translations.values())
    if total > 20:
        table.add_row("...", "", f"({total - 20} more)", "")

    console.print(table)


@app.command()
def chrome(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to _locales/ directory (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Target locales (comma-separated, e.g., 'fr,de,pt-BR'). "
            "Hyphens auto-converted to underscores.",
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source locale",
        ),
    ] = "en",
    keys: Annotated[
        Optional[str],
        typer.Option(
            "--keys",
            "-k",
            help="Filter specific message keys (comma-separated)",
        ),
    ] = None,
    on_limit: Annotated[
        str,
        typer.Option(
            "--on-limit",
            help="Action when CWS field exceeds character limit: warn, truncate, or error",
        ),
    ] = "warn",
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
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
) -> None:
    """Translate Chrome Extension _locales/ messages to target locales."""
    if not to:
        console.print("[red]Error:[/red] --to option is required (e.g., --to fr,de,pt-BR)")
        raise typer.Exit(1)

    from localizerx.utils.limits import LimitAction

    try:
        limit_action = LimitAction(on_limit)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid --on-limit value: {on_limit}")
        console.print("Valid options: warn, truncate, error")
        raise typer.Exit(1)

    _run_chrome_translate(
        path=path,
        to=to,
        src=src,
        keys=keys,
        limit_action=limit_action,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=not no_backup,
        model=model,
    )


@app.command("chrome-info")
def chrome_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to _locales/ directory (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about Chrome Extension locale files."""
    from localizerx.io.extension import detect_extension_path, read_extension
    from localizerx.parser.extension_model import EXTENSION_FIELD_LIMITS, KNOWN_CWS_KEYS

    # Find _locales path
    if path is None:
        path = detect_extension_path()
        if path is None:
            console.print("[red]Error:[/red] No _locales/ directory found")
            console.print("Run from a directory with _locales/ or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_extension(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Locales Directory:[/bold] {path}")
    console.print(f"[bold]Source Locale:[/bold] {catalog.source_locale}")
    console.print(f"[bold]Total Locales:[/bold] {catalog.locale_count}")
    console.print()

    # Show locale table
    table = Table(title="Locale Status")
    table.add_column("Locale", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Messages", style="green")
    table.add_column("Issues", style="yellow")

    for locale_code, locale_data in sorted(catalog.locales.items()):
        locale_name = get_chrome_locale_name(locale_code)
        msg_count = locale_data.field_count
        over_limit = locale_data.get_over_limit_fields()

        issues = []
        if over_limit:
            issues.append(f"{len(over_limit)} over limit")

        issues_str = ", ".join(issues) if issues else "-"
        is_source = " (source)" if locale_code == catalog.source_locale else ""

        table.add_row(
            f"{locale_code}{is_source}",
            locale_name,
            str(msg_count),
            issues_str,
        )

    console.print(table)
    console.print()

    # Show CWS field details for source locale
    source = catalog.get_source_locale()
    if source:
        has_cws_fields = any(key in source.messages for key in KNOWN_CWS_KEYS)
        if has_cws_fields:
            console.print(f"[bold]CWS Fields ({catalog.source_locale}):[/bold]")
            field_table = Table()
            field_table.add_column("Field", style="cyan")
            field_table.add_column("Chars", style="white")
            field_table.add_column("Limit", style="yellow")
            field_table.add_column("Status", style="green")

            from localizerx.parser.extension_model import ExtensionFieldType

            for ft in ExtensionFieldType:
                msg = source.get_message(ft.value)
                limit = EXTENSION_FIELD_LIMITS[ft]
                if msg:
                    char_count = msg.char_count
                    if msg.is_over_limit:
                        over = msg.char_count - limit
                        status = f"[red]OVER by {over}[/red]"
                    else:
                        status = "OK"
                    field_table.add_row(ft.value, str(char_count), str(limit), status)
                else:
                    field_table.add_row(ft.value, "-", str(limit), "[dim]missing[/dim]")

            console.print(field_table)


def _run_chrome_translate(
    path: Path | None,
    to: str,
    src: str,
    keys: str | None,
    limit_action,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Core Chrome Extension translation logic."""
    from localizerx.io.extension import detect_extension_path, read_extension
    from localizerx.parser.extension_model import KNOWN_CWS_KEYS

    config = load_config()

    # Parse target locales (hyphen -> underscore)
    target_locales = parse_chrome_locale_list(to)
    if not target_locales:
        console.print("[red]Error:[/red] No valid target locales specified")
        raise typer.Exit(1)

    # Validate locales
    invalid_locales = [loc for loc in target_locales if not validate_chrome_locale(loc)]
    if invalid_locales:
        codes = ", ".join(invalid_locales)
        console.print(f"[yellow]Warning:[/yellow] Unrecognized locale codes: {codes}")

    # Parse keys filter
    keys_filter: list[str] | None = None
    if keys:
        keys_filter = [k.strip() for k in keys.split(",") if k.strip()]

    # Find _locales path
    if path is None:
        path = detect_extension_path()
        if path is None:
            console.print("[red]Error:[/red] No _locales/ directory found")
            console.print("Run from a directory with _locales/ or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    # Read catalog
    try:
        catalog = read_extension(path, source_locale=src)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    source = catalog.get_source_locale()
    if not source:
        console.print(f"[red]Error:[/red] Source locale '{src}' not found in _locales/")
        console.print(f"Available locales: {', '.join(catalog.locales.keys())}")
        raise typer.Exit(1)

    console.print(f"[bold]Locales Directory:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_chrome_locale_name(src)} ({src})")
    target_display = ", ".join(f"{get_chrome_locale_name(loc)} ({loc})" for loc in target_locales)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Determine messages to translate per locale
    translation_tasks: dict[str, list] = {}  # locale -> list of ExtensionMessage

    for target_locale in target_locales:
        if overwrite:
            # Translate all specified keys (or all source keys)
            candidates = keys_filter or list(source.messages.keys())
            needs = [
                source.get_message(k)
                for k in candidates
                if source.get_message(k) and source.get_message(k).message.strip()
            ]
        else:
            needs = catalog.get_messages_needing_translation(target_locale, keys_filter)

        if needs:
            translation_tasks[target_locale] = needs

    if not translation_tasks:
        console.print("[green]All messages already translated[/green]")
        return

    # Show summary
    for locale, msgs in translation_tasks.items():
        cws_count = sum(1 for m in msgs if m.key in KNOWN_CWS_KEYS)
        regular_count = len(msgs) - cws_count
        parts = []
        if cws_count:
            parts.append(f"{cws_count} CWS field(s)")
        if regular_count:
            parts.append(f"{regular_count} message(s)")
        console.print(f"  {get_chrome_locale_name(locale)}: {', '.join(parts)}")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        _show_chrome_dry_run(translation_tasks)
        return

    # Perform translation
    asyncio.run(
        _translate_chrome(
            catalog=catalog,
            path=path,
            source_locale=src,
            translation_tasks=translation_tasks,
            config=config,
            limit_action=limit_action,
            preview=preview,
            backup=backup,
            model=model,
        )
    )


def _show_chrome_dry_run(tasks: dict[str, list]) -> None:
    """Show table of messages that would be translated."""
    from localizerx.parser.extension_model import KNOWN_CWS_KEYS

    table = Table(title="Messages to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Length", style="green")

    for locale, msgs in tasks.items():
        for msg in msgs[:20]:
            msg_type = "CWS" if msg.key in KNOWN_CWS_KEYS else "msg"
            table.add_row(locale, msg.key[:40], msg_type, str(msg.char_count))

        if len(msgs) > 20:
            table.add_row(locale, f"... ({len(msgs) - 20} more)", "", "")

    console.print(table)


async def _translate_chrome(
    catalog,
    path: Path,
    source_locale: str,
    translation_tasks: dict[str, list],
    config,
    limit_action,
    preview: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Perform Chrome Extension translations and update files."""
    from localizerx.io.extension import write_extension
    from localizerx.parser.extension_model import KNOWN_CWS_KEYS, ExtensionFieldType
    from localizerx.translator.extension_prompts import (
        build_extension_field_prompt,
    )
    from localizerx.utils.limits import LimitAction, truncate_to_limit, validate_limit

    cache_dir = get_cache_dir(config)
    actual_model = model or config.translator.model

    async with GeminiTranslator(
        model=actual_model,
        batch_size=config.translator.batch_size,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        all_translations: dict[str, dict[str, str]] = {}  # locale -> {key: translated}
        limit_warnings: list[str] = []

        for target_locale, messages in translation_tasks.items():
            console.print(f"  Translating to {get_chrome_locale_name(target_locale)}...")
            all_translations[target_locale] = {}

            # Separate CWS fields from regular messages
            cws_messages = [m for m in messages if m.key in KNOWN_CWS_KEYS]
            regular_messages = [m for m in messages if m.key not in KNOWN_CWS_KEYS]

            # Use standard locale codes for Gemini API
            src_std = chrome_to_standard_locale(source_locale)
            tgt_std = chrome_to_standard_locale(target_locale)

            total = len(messages)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"    {target_locale}", total=total)

                # 1. Translate CWS fields one-by-one with specialized prompts
                for msg in cws_messages:
                    field_type = ExtensionFieldType(msg.key)
                    prompt = build_extension_field_prompt(
                        text=msg.message,
                        key=msg.key,
                        description=msg.description,
                        field_type=field_type,
                        src_lang=source_locale,
                        tgt_lang=target_locale,
                    )

                    try:
                        translated = await translator._call_api(prompt)
                        translated = translated.strip()
                    except Exception as e:
                        console.print(f"    [red]Error translating {msg.key}: {e}[/red]")
                        progress.advance(task)
                        continue

                    # Validate against limit
                    validation = validate_limit(translated, field_type)

                    if not validation.is_valid:
                        warning = (
                            f"[{target_locale}] {msg.key}: "
                            f"{validation.char_count}/{validation.limit} chars "
                            f"(over by {validation.chars_over})"
                        )
                        limit_warnings.append(warning)

                        if limit_action == LimitAction.ERROR:
                            console.print(f"    [red]Error: {warning}[/red]")
                            raise typer.Exit(1)
                        elif limit_action == LimitAction.TRUNCATE:
                            translated = truncate_to_limit(translated, field_type)
                            console.print(f"    [yellow]Truncated: {msg.key}[/yellow]")
                        else:  # warn
                            console.print(f"    [yellow]Warning: {warning}[/yellow]")

                    all_translations[target_locale][msg.key] = translated
                    progress.advance(task)

                # 2. Translate regular messages in batches
                if regular_messages:
                    requests = [
                        TranslationRequest(
                            key=m.key,
                            text=m.message,
                            comment=m.description,
                        )
                        for m in regular_messages
                    ]

                    results = await translator.translate_batch(requests, src_std, tgt_std)

                    for result in results:
                        if result.success and result.translated:
                            all_translations[target_locale][result.key] = result.translated
                        progress.advance(task)

        # Show preview if requested
        if preview:
            _show_chrome_preview(catalog, all_translations)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog
        source = catalog.get_source_locale()
        for target_locale, translations in all_translations.items():
            locale_data = catalog.get_or_create_locale(target_locale)
            for key, translated_text in translations.items():
                # Preserve description and placeholders from source
                src_msg = source.get_message(key) if source else None
                locale_data.set_message(
                    key=key,
                    message=translated_text,
                    description=src_msg.description if src_msg else None,
                    placeholders=src_msg.placeholders if src_msg else None,
                )

        # Write files
        write_extension(
            catalog,
            path,
            backup=backup,
            locales=list(all_translations.keys()),
        )

        console.print(f"\n[green]Saved translations to {path}[/green]")

        # Show limit warnings summary
        if limit_warnings:
            console.print(f"\n[yellow]Character limit warnings ({len(limit_warnings)}):[/yellow]")
            for warning in limit_warnings[:10]:
                console.print(f"  {warning}")
            if len(limit_warnings) > 10:
                console.print(f"  ... and {len(limit_warnings) - 10} more")


def _show_chrome_preview(catalog, all_translations: dict) -> None:
    """Show preview of Chrome Extension translations."""
    table = Table(title="Translation Preview")
    table.add_column("Locale", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Translation", style="green")
    table.add_column("Chars", style="yellow")

    count = 0
    for locale, translations in all_translations.items():
        for key, value in translations.items():
            preview_value = value[:60] + "..." if len(value) > 60 else value
            preview_value = preview_value.replace("\n", " ")
            table.add_row(locale, key[:30], preview_value, str(len(value)))
            count += 1
            if count >= 20:
                break
        if count >= 20:
            break

    total = sum(len(t) for t in all_translations.values())
    if total > 20:
        table.add_row("...", "", f"({total - 20} more)", "")

    console.print(table)


if __name__ == "__main__":
    app()
