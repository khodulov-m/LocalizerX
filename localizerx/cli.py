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
            help="Target locales (comma-separated, e.g., 'de-DE,fr-FR,es-ES'). Omit to use defaults from config.",
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


@app.command("metadata-check")
def metadata_check(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to fastlane metadata directory (auto-detected if omitted)",
        ),
    ] = None,
    locale: Annotated[
        Optional[str],
        typer.Option(
            "--locale",
            "-l",
            help="Check specific locale only (default: all locales)",
        ),
    ] = None,
    field: Annotated[
        Optional[str],
        typer.Option(
            "--field",
            "-f",
            help="Check specific field only (e.g., name, subtitle, keywords)",
        ),
    ] = None,
) -> None:
    """Check metadata files for App Store character limit compliance."""
    from localizerx.io.metadata import detect_metadata_path, read_metadata
    from localizerx.parser.metadata_model import MetadataFieldType
    from localizerx.utils.limits import validate_limit

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

    # Parse field filter
    field_type_filter: MetadataFieldType | None = None
    if field:
        try:
            field_type_filter = MetadataFieldType(field.lower())
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid field type: {field}")
            console.print(
                f"Valid fields: {', '.join(f.value for f in MetadataFieldType)}"
            )
            raise typer.Exit(1)

    # Read metadata
    try:
        catalog = read_metadata(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Filter locales
    locales_to_check = [locale] if locale else list(catalog.locales.keys())
    locales_to_check = [loc for loc in locales_to_check if loc in catalog.locales]

    if not locales_to_check:
        console.print("[red]Error:[/red] No valid locales to check")
        raise typer.Exit(1)

    # Check all fields
    all_valid = True
    violations = []

    for locale_code in sorted(locales_to_check):
        locale_meta = catalog.locales[locale_code]
        locale_name = get_fastlane_locale_name(locale_code)

        # Filter fields if specified
        if field_type_filter:
            # Only check the specified field if it exists in this locale
            fields_to_check = (
                {field_type_filter: locale_meta.fields[field_type_filter]}
                if field_type_filter in locale_meta.fields
                else {}
            )
        else:
            # Check all fields
            fields_to_check = locale_meta.fields

        for field_type, metadata_field in fields_to_check.items():
            result = validate_limit(metadata_field.content, field_type)

            if not result.is_valid:
                all_valid = False
                violations.append(
                    {
                        "locale": locale_code,
                        "locale_name": locale_name,
                        "field_type": field_type,
                        "result": result,
                    }
                )

    # Display results
    console.print(f"[bold]Metadata Directory:[/bold] {path}")
    console.print(f"[bold]Locales Checked:[/bold] {len(locales_to_check)}")
    console.print(f"[bold]Fields Checked:[/bold] {field or 'all'}")
    console.print()

    if all_valid:
        console.print("[green]✓ All fields are within character limits[/green]")
        console.print()

        # Show summary table
        summary_table = Table(title="Character Limit Summary")
        summary_table.add_column("Field", style="cyan")
        summary_table.add_column("Limit", style="white")

        field_types_to_show = (
            [field_type_filter] if field_type_filter else list(MetadataFieldType)
        )
        for ft in field_types_to_show:
            from localizerx.parser.metadata_model import FIELD_LIMITS

            summary_table.add_row(ft.value, str(FIELD_LIMITS[ft]))

        console.print(summary_table)
    else:
        console.print(
            f"[red]✗ Found {len(violations)} field(s) exceeding character limits[/red]"
        )
        console.print()

        # Show violations table
        violations_table = Table(title="Character Limit Violations")
        violations_table.add_column("Locale", style="cyan")
        violations_table.add_column("Field", style="yellow")
        violations_table.add_column("Characters", style="white")
        violations_table.add_column("Limit", style="white")
        violations_table.add_column("Over By", style="red")

        for v in violations:
            result = v["result"]
            violations_table.add_row(
                f"{v['locale']}\n{v['locale_name']}",
                result.field_type.value,
                str(result.char_count),
                str(result.limit),
                str(result.chars_over),
            )

        console.print(violations_table)
        console.print()
        console.print(
            "[yellow]Tip:[/yellow] Use --field to check a specific field or --locale to check a specific locale"
        )
        raise typer.Exit(1)


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

    # Parse target locales (use config defaults if not specified)
    if to:
        target_locales = parse_fastlane_locale_list(to)
    else:
        target_locales = config.default_targets.copy()
        if target_locales:
            console.print(
                f"[dim]Using default targets from config ({len(target_locales)} languages)[/dim]"
            )

    if not target_locales:
        console.print("[red]Error:[/red] No target locales specified")
        console.print("Use --to option or set default_targets in config.toml")
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


@app.command("i18n")
def i18n_translate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to i18n locales directory (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Target locales (comma-separated, e.g., 'fr,es,de')",
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
    """Translate frontend i18n JSON files to target locales."""
    if not to:
        console.print("[red]Error:[/red] --to option is required (e.g., --to fr,es,de)")
        raise typer.Exit(1)

    _run_i18n_translate(
        path=path,
        to=to,
        src=src,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=not no_backup,
        batch_size=batch_size,
        model=model,
    )


@app.command("i18n-info")
def i18n_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to i18n locales directory (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about i18n locale files."""
    from localizerx.io.i18n import detect_i18n_path, read_i18n

    # Find locales path
    if path is None:
        path = detect_i18n_path()
        if path is None:
            console.print("[red]Error:[/red] No i18n locales directory found")
            console.print("Run from a directory with locales/ or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_i18n(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Locales Directory:[/bold] {path}")
    console.print(f"[bold]Source Locale:[/bold] {catalog.source_locale}")
    console.print(f"[bold]Total Locales:[/bold] {catalog.locale_count}")
    console.print()

    source = catalog.get_source_locale()
    total_keys = source.message_count if source else 0

    # Show locale table
    table = Table(title="Locale Status")
    table.add_column("Locale", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Messages", style="green")
    table.add_column("Coverage", style="yellow")

    for locale_code, locale_data in sorted(catalog.locales.items()):
        locale_name = get_language_name(locale_code)
        msg_count = locale_data.message_count
        pct = (msg_count / total_keys * 100) if total_keys > 0 else 0
        is_source = " (source)" if locale_code == catalog.source_locale else ""

        table.add_row(
            f"{locale_code}{is_source}",
            locale_name,
            str(msg_count),
            f"{pct:.1f}%",
        )

    console.print(table)


def _run_i18n_translate(
    path: Path | None,
    to: str,
    src: str,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Core i18n translation logic."""
    from localizerx.io.i18n import detect_i18n_path, read_i18n

    config = load_config()

    target_locales = parse_language_list(to)
    if not target_locales:
        console.print("[red]Error:[/red] No valid target locales specified")
        raise typer.Exit(1)

    # Find locales path
    if path is None:
        path = detect_i18n_path()
        if path is None:
            console.print("[red]Error:[/red] No i18n locales directory found")
            console.print("Run from a directory with locales/ or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_i18n(path, source_locale=src)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    source = catalog.get_source_locale()
    if not source:
        console.print(f"[red]Error:[/red] Source locale '{src}' not found")
        console.print(f"Available locales: {', '.join(catalog.locales.keys())}")
        raise typer.Exit(1)

    console.print(f"[bold]Locales Directory:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_language_name(src)} ({src})")
    target_display = ", ".join(f"{get_language_name(loc)} ({loc})" for loc in target_locales)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Determine messages to translate per locale
    translation_tasks: dict[str, list] = {}

    for target_locale in target_locales:
        if overwrite:
            needs = [m for m in source.messages.values() if m.needs_translation]
        else:
            needs = catalog.get_messages_needing_translation(target_locale)

        if needs:
            translation_tasks[target_locale] = needs

    if not translation_tasks:
        console.print("[green]All messages already translated[/green]")
        return

    for locale, msgs in translation_tasks.items():
        console.print(f"  {get_language_name(locale)}: {len(msgs)} message(s) to translate")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        _show_i18n_dry_run(translation_tasks)
        return

    asyncio.run(
        _translate_i18n(
            catalog=catalog,
            path=path,
            source_locale=src,
            translation_tasks=translation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            batch_size=batch_size,
            model=model,
        )
    )


def _show_i18n_dry_run(tasks: dict[str, list]) -> None:
    """Show table of messages that would be translated."""
    table = Table(title="Messages to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Value", style="green")

    for locale, msgs in tasks.items():
        for msg in msgs[:20]:
            display_value = msg.value[:50] + "..." if len(msg.value) > 50 else msg.value
            table.add_row(locale, msg.key[:40], display_value)

        if len(msgs) > 20:
            table.add_row(locale, f"... ({len(msgs) - 20} more)", "")

    console.print(table)


async def _translate_i18n(
    catalog,
    path: Path,
    source_locale: str,
    translation_tasks: dict[str, list],
    config,
    preview: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Perform i18n translations and update catalog."""
    from localizerx.io.i18n import write_i18n

    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.translator.batch_size
    actual_model = model or config.translator.model

    async with GeminiTranslator(
        model=actual_model,
        batch_size=actual_batch_size,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        all_translations: dict[str, dict[str, str]] = {}  # locale -> {key: translated}

        for target_locale, messages in translation_tasks.items():
            console.print(f"  Translating to {get_language_name(target_locale)}...")
            all_translations[target_locale] = {}

            requests = [TranslationRequest(key=m.key, text=m.value) for m in messages]

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"    {target_locale}", total=len(requests))

                results = await translator.translate_batch(requests, source_locale, target_locale)

                for result in results:
                    if result.success and result.translated:
                        all_translations[target_locale][result.key] = result.translated
                    progress.advance(task)

        # Show preview if requested
        if preview:
            _show_i18n_preview(all_translations)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog
        for target_locale, translations in all_translations.items():
            locale_data = catalog.get_or_create_locale(target_locale)
            for key, translated_text in translations.items():
                locale_data.set_message(key, translated_text)

        # Write files
        write_i18n(
            catalog,
            path,
            backup=backup,
            locales=list(all_translations.keys()),
        )

        console.print(f"\n[green]Saved translations to {path}[/green]")


def _show_i18n_preview(all_translations: dict) -> None:
    """Show preview of i18n translations."""
    table = Table(title="Translation Preview")
    table.add_column("Locale", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Translation", style="green")

    count = 0
    for locale, translations in all_translations.items():
        for key, value in translations.items():
            preview_value = value[:60] + "..." if len(value) > 60 else value
            table.add_row(locale, key[:30], preview_value)
            count += 1
            if count >= 20:
                break
        if count >= 20:
            break

    total = sum(len(t) for t in all_translations.values())
    if total > 20:
        table.add_row("...", "", f"({total - 20} more)")

    console.print(table)


@app.command("android")
def android_translate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to Android res/ directory (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Target locales (comma-separated, e.g., 'fr,es,de,pt-BR')",
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
    include_arrays: Annotated[
        bool,
        typer.Option(
            "--include-arrays",
            help="Also translate string-array resources",
        ),
    ] = False,
    include_plurals: Annotated[
        bool,
        typer.Option(
            "--include-plurals",
            help="Also translate plurals resources",
        ),
    ] = False,
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
    """Translate Android strings.xml files to target locales."""
    if not to:
        console.print("[red]Error:[/red] --to option is required (e.g., --to fr,es,de)")
        raise typer.Exit(1)

    _run_android_translate(
        path=path,
        to=to,
        src=src,
        include_arrays=include_arrays,
        include_plurals=include_plurals,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=not no_backup,
        batch_size=batch_size,
        model=model,
    )


@app.command("android-info")
def android_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to Android res/ directory (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about Android string resources."""
    from localizerx.io.android import detect_android_path, read_android

    # Find res path
    if path is None:
        path = detect_android_path()
        if path is None:
            console.print("[red]Error:[/red] No Android res/ directory found")
            console.print("Run from a directory with res/ or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_android(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Resource Directory:[/bold] {path}")
    console.print(f"[bold]Source Locale:[/bold] {catalog.source_locale}")
    console.print(f"[bold]Total Locales:[/bold] {catalog.locale_count}")
    console.print()

    source = catalog.get_source_locale()

    # Show locale table
    table = Table(title="Locale Status")
    table.add_column("Locale", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Strings", style="green")
    table.add_column("Arrays", style="blue")
    table.add_column("Plurals", style="magenta")

    for locale_code, locale_data in sorted(catalog.locales.items()):
        locale_name = get_language_name(locale_code)
        is_source = " (source)" if locale_code == catalog.source_locale else ""

        table.add_row(
            f"{locale_code}{is_source}",
            locale_name,
            str(locale_data.string_count),
            str(len(locale_data.string_arrays)),
            str(len(locale_data.plurals)),
        )

    console.print(table)

    # Show source details
    if source:
        translatable = source.translatable_strings
        non_translatable = [s for s in source.strings.values() if not s.translatable]
        console.print()
        console.print(f"[bold]Source ({catalog.source_locale}):[/bold]")
        console.print(f"  Translatable strings: {len(translatable)}")
        if non_translatable:
            console.print(f"  Non-translatable: {len(non_translatable)}")
        if source.string_arrays:
            console.print(f"  String arrays: {len(source.string_arrays)}")
        if source.plurals:
            console.print(f"  Plurals: {len(source.plurals)}")


def _run_android_translate(
    path: Path | None,
    to: str,
    src: str,
    include_arrays: bool,
    include_plurals: bool,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Core Android translation logic."""
    from localizerx.io.android import detect_android_path, read_android

    config = load_config()

    target_locales = parse_language_list(to)
    if not target_locales:
        console.print("[red]Error:[/red] No valid target locales specified")
        raise typer.Exit(1)

    # Find res path
    if path is None:
        path = detect_android_path()
        if path is None:
            console.print("[red]Error:[/red] No Android res/ directory found")
            console.print("Run from a directory with res/ or specify path")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_android(path, source_locale=src)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    source = catalog.get_source_locale()
    if not source:
        console.print(f"[red]Error:[/red] Source locale '{src}' not found")
        console.print(f"Available locales: {', '.join(catalog.locales.keys())}")
        raise typer.Exit(1)

    console.print(f"[bold]Resource Directory:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_language_name(src)} ({src})")
    target_display = ", ".join(f"{get_language_name(loc)} ({loc})" for loc in target_locales)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Determine what to translate per locale
    translation_tasks: dict[str, dict] = {}

    for target_locale in target_locales:
        task: dict[str, list] = {"strings": [], "arrays": [], "plurals": []}

        if overwrite:
            task["strings"] = list(source.translatable_strings)
        else:
            task["strings"] = catalog.get_strings_needing_translation(target_locale)

        if include_arrays:
            if overwrite:
                task["arrays"] = [a for a in source.string_arrays.values() if a.translatable]
            else:
                task["arrays"] = catalog.get_arrays_needing_translation(target_locale)

        if include_plurals:
            if overwrite:
                task["plurals"] = [p for p in source.plurals.values() if p.translatable]
            else:
                task["plurals"] = catalog.get_plurals_needing_translation(target_locale)

        if task["strings"] or task["arrays"] or task["plurals"]:
            translation_tasks[target_locale] = task

    if not translation_tasks:
        console.print("[green]All strings already translated[/green]")
        return

    for locale, task in translation_tasks.items():
        parts = []
        if task["strings"]:
            parts.append(f"{len(task['strings'])} string(s)")
        if task["arrays"]:
            parts.append(f"{len(task['arrays'])} array(s)")
        if task["plurals"]:
            parts.append(f"{len(task['plurals'])} plural(s)")
        console.print(f"  {get_language_name(locale)}: {', '.join(parts)}")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        _show_android_dry_run(translation_tasks)
        return

    asyncio.run(
        _translate_android(
            catalog=catalog,
            path=path,
            source_locale=src,
            translation_tasks=translation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            batch_size=batch_size,
            model=model,
        )
    )


def _show_android_dry_run(tasks: dict[str, dict]) -> None:
    """Show table of strings that would be translated."""
    table = Table(title="Strings to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Name", style="white")
    table.add_column("Value", style="green")

    for locale, task in tasks.items():
        for s in task["strings"][:15]:
            display = s.value[:40] + "..." if len(s.value) > 40 else s.value
            table.add_row(locale, "string", s.name, display)
        for a in task["arrays"][:5]:
            table.add_row(locale, "array", a.name, f"{len(a.items)} items")
        for p in task["plurals"][:5]:
            table.add_row(locale, "plural", p.name, f"{len(p.items)} forms")

        total = len(task["strings"]) + len(task["arrays"]) + len(task["plurals"])
        shown = (
            min(len(task["strings"]), 15)
            + min(len(task["arrays"]), 5)
            + min(len(task["plurals"]), 5)
        )
        if total > shown:
            table.add_row(locale, "", f"... ({total - shown} more)", "")

    console.print(table)


async def _translate_android(
    catalog,
    path: Path,
    source_locale: str,
    translation_tasks: dict[str, dict],
    config,
    preview: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
) -> None:
    """Perform Android translations and update catalog."""
    from localizerx.io.android import write_android
    from localizerx.parser.android_model import AndroidPlural, AndroidString, AndroidStringArray

    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.translator.batch_size
    actual_model = model or config.translator.model

    async with GeminiTranslator(
        model=actual_model,
        batch_size=actual_batch_size,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        all_results: dict[str, dict] = {}  # locale -> {strings: {}, arrays: {}, plurals: {}}

        for target_locale, task in translation_tasks.items():
            console.print(f"  Translating to {get_language_name(target_locale)}...")
            all_results[target_locale] = {"strings": {}, "arrays": {}, "plurals": {}}

            total = len(task["strings"]) + len(task["arrays"]) + len(task["plurals"])

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                ptask = progress.add_task(f"    {target_locale}", total=total)

                # Translate strings in batch
                if task["strings"]:
                    requests = [
                        TranslationRequest(key=s.name, text=s.value, comment=s.comment)
                        for s in task["strings"]
                    ]
                    results = await translator.translate_batch(
                        requests, source_locale, target_locale
                    )
                    for result in results:
                        if result.success and result.translated:
                            all_results[target_locale]["strings"][result.key] = result.translated
                        progress.advance(ptask)

                # Translate arrays (each item individually, batched)
                for arr in task["arrays"]:
                    requests = [
                        TranslationRequest(key=f"{arr.name}[{i}]", text=item)
                        for i, item in enumerate(arr.items)
                    ]
                    results = await translator.translate_batch(
                        requests, source_locale, target_locale
                    )
                    translated_items = []
                    for result in results:
                        if result.success and result.translated:
                            translated_items.append(result.translated)
                        else:
                            # Keep original on failure
                            idx = int(result.key.split("[")[1].rstrip("]"))
                            translated_items.append(arr.items[idx])
                    all_results[target_locale]["arrays"][arr.name] = translated_items
                    progress.advance(ptask)

                # Translate plurals (each quantity individually)
                for plural in task["plurals"]:
                    requests = [
                        TranslationRequest(key=f"{plural.name}:{qty}", text=text)
                        for qty, text in plural.items.items()
                    ]
                    results = await translator.translate_batch(
                        requests, source_locale, target_locale
                    )
                    translated_items = {}
                    for result in results:
                        if result.success and result.translated:
                            qty = result.key.split(":")[1]
                            translated_items[qty] = result.translated
                    all_results[target_locale]["plurals"][plural.name] = translated_items
                    progress.advance(ptask)

        # Show preview if requested
        if preview:
            _show_android_preview(all_results)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog
        for target_locale, results in all_results.items():
            locale_data = catalog.get_or_create_locale(target_locale)

            for name, value in results["strings"].items():
                locale_data.strings[name] = AndroidString(name=name, value=value)

            for name, items in results["arrays"].items():
                locale_data.string_arrays[name] = AndroidStringArray(name=name, items=items)

            for name, items in results["plurals"].items():
                locale_data.plurals[name] = AndroidPlural(name=name, items=items)

        # Write files
        write_android(
            catalog,
            path,
            backup=backup,
            locales=list(all_results.keys()),
        )

        console.print(f"\n[green]Saved translations to {path}[/green]")


def _show_android_preview(all_results: dict) -> None:
    """Show preview of Android translations."""
    table = Table(title="Translation Preview")
    table.add_column("Locale", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Translation", style="green")

    count = 0
    for locale, results in all_results.items():
        for name, value in results["strings"].items():
            preview_value = value[:60] + "..." if len(value) > 60 else value
            table.add_row(locale, name, preview_value)
            count += 1
            if count >= 20:
                break
        if count >= 20:
            break

    total = sum(
        len(r["strings"]) + len(r["arrays"]) + len(r["plurals"]) for r in all_results.values()
    )
    if total > 20:
        table.add_row("...", "", f"({total - 20} more)")

    console.print(table)


@app.command("screenshots")
def screenshots_translate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to screenshots/texts.json (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Target languages (comma-separated). If not specified, uses default_targets from config.",
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source language (defaults to sourceLanguage from file or 'en')",
        ),
    ] = "",
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
    """Translate App Store screenshot texts to target languages.

    If screenshots/texts.json doesn't exist, creates a template.
    If it exists, translates to target languages (--to or config defaults).
    """
    _run_screenshots_translate(
        path=path,
        to=to,
        src=src,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=not no_backup,
        model=model,
    )


@app.command("screenshots-info")
def screenshots_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to screenshots/texts.json (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about screenshot texts file."""
    from localizerx.io.screenshots import detect_screenshots_path, read_screenshots
    from localizerx.parser.screenshots_model import (
        DeviceClass,
        SCREENSHOT_TEXT_WORD_LIMIT,
    )

    # Find screenshots path
    if path is None:
        path = detect_screenshots_path()
        if path is None:
            console.print("[red]Error:[/red] No screenshots/texts.json file found")
            console.print("Run 'localizerx screenshots' to create a template")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] File does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_screenshots(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Screenshots File:[/bold] {path}")
    console.print(f"[bold]Source Language:[/bold] {catalog.source_language}")
    console.print(f"[bold]Screens:[/bold] {catalog.screen_count}")
    console.print(f"[bold]Localized Languages:[/bold] {catalog.locale_count}")
    console.print()

    # Show screens table
    table = Table(title="Source Screens")
    table.add_column("Screen", style="cyan")
    table.add_column("Texts", style="green")
    table.add_column("Issues", style="yellow")

    for screen_id, screen in catalog.screens.items():
        text_count = screen.text_count
        over_limit = screen.get_over_limit_texts()

        issues = []
        if over_limit:
            issues.append(f"{len(over_limit)} over {SCREENSHOT_TEXT_WORD_LIMIT} words")

        issues_str = ", ".join(issues) if issues else "-"

        table.add_row(screen_id, str(text_count), issues_str)

    console.print(table)
    console.print()

    # Show localizations summary
    if catalog.localizations:
        loc_table = Table(title="Localizations")
        loc_table.add_column("Language", style="cyan")
        loc_table.add_column("Name", style="white")
        loc_table.add_column("Screens", style="green")

        for locale, locale_data in sorted(catalog.localizations.items()):
            locale_name = get_language_name(locale)
            loc_table.add_row(locale, locale_name, str(locale_data.screen_count))

        console.print(loc_table)
    else:
        console.print("[dim]No localizations yet[/dim]")


@app.command("screenshots-generate")
def screenshots_generate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to screenshots/texts.json (auto-detected or created if omitted)",
        ),
    ] = None,
    metadata_path: Annotated[
        Optional[Path],
        typer.Option(
            "--metadata",
            help="Path to fastlane/metadata directory (auto-detected if omitted)",
        ),
    ] = None,
    hints: Annotated[
        Optional[Path],
        typer.Option(
            "--hints",
            help="JSON file with screen descriptions (interactive mode if omitted)",
        ),
    ] = None,
    text_types: Annotated[
        Optional[str],
        typer.Option(
            "--text-types",
            help="Comma-separated text types to generate (default: headline,subtitle)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show prompts without making API calls",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            "-p",
            help="Show generated texts before saving",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing source texts",
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
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source language for the generated texts (default: en)",
        ),
    ] = "en",
) -> None:
    """Generate marketing-optimized screenshot texts using Gemini AI.

    Reads app context from fastlane/metadata to understand your app,
    then generates compelling screenshot texts based on screen descriptions.

    Two modes:
    - Interactive: prompts for screen descriptions one by one
    - Hints file: reads descriptions from a JSON file (--hints)

    Examples:

        # Interactive mode - prompts for screen descriptions
        localizerx screenshots-generate

        # From hints file
        localizerx screenshots-generate --hints hints.json

        # Generate only headlines
        localizerx screenshots-generate --text-types headline

        # Preview before saving
        localizerx screenshots-generate --preview
    """
    _run_screenshots_generate(
        path=path,
        metadata_path=metadata_path,
        hints_path=hints,
        text_types=text_types,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=not no_backup,
        model=model,
        src_lang=src,
    )


def _run_screenshots_generate(
    path: Path | None,
    metadata_path: Path | None,
    hints_path: Path | None,
    text_types: str | None,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
    src_lang: str,
) -> None:
    """Core screenshots generation logic."""
    from localizerx.io.metadata import detect_metadata_path, read_metadata
    from localizerx.io.screenshots import (
        detect_screenshots_path,
        get_default_screenshots_path,
        read_hints_file,
        read_screenshots,
        write_screenshots,
    )
    from localizerx.parser.app_context import AppContext
    from localizerx.parser.screenshots_model import (
        DeviceClass,
        ScreenshotsCatalog,
        ScreenshotScreen,
        ScreenshotText,
        ScreenshotTextType,
    )

    config = load_config()

    # Parse text types to generate
    if text_types:
        type_names = [t.strip().lower() for t in text_types.split(",")]
        types_to_generate = []
        for name in type_names:
            try:
                types_to_generate.append(ScreenshotTextType(name))
            except ValueError:
                console.print(f"[yellow]Warning:[/yellow] Unknown text type '{name}'")
        if not types_to_generate:
            console.print("[red]Error:[/red] No valid text types specified")
            raise typer.Exit(1)
    else:
        # Default: headline and subtitle
        types_to_generate = [ScreenshotTextType.HEADLINE, ScreenshotTextType.SUBTITLE]

    # Detect or read metadata for app context
    if metadata_path is None:
        metadata_path = detect_metadata_path()

    if metadata_path is None:
        console.print("[yellow]Warning:[/yellow] No fastlane/metadata found")
        console.print("Creating minimal app context. For better results, create fastlane/metadata.")
        app_context = AppContext(name="App")
    else:
        try:
            # Read metadata with en-US as default source locale
            catalog = read_metadata(metadata_path, source_locale="en-US")
            source_metadata = catalog.get_source_metadata()
            if source_metadata is None:
                # Try to find any locale with data
                for locale in ["en-US", "en", "en-GB"]:
                    source_metadata = catalog.get_locale(locale)
                    if source_metadata and source_metadata.field_count > 0:
                        break

            if source_metadata:
                app_context = AppContext.from_metadata(source_metadata)
                console.print(f"[green]Reading app context from {metadata_path}[/green]")
                console.print(f"  App: {app_context.name}")
                if app_context.subtitle:
                    console.print(f"  Subtitle: {app_context.subtitle}")
            else:
                console.print("[yellow]Warning:[/yellow] No source metadata found")
                app_context = AppContext(name="App")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to read metadata: {e}")
            app_context = AppContext(name="App")

    console.print()

    # Get screen hints (from file or interactive)
    if hints_path:
        try:
            screen_hints = read_hints_file(hints_path)
            console.print(f"[green]Read {len(screen_hints)} screen hints from {hints_path}[/green]")
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    else:
        # Interactive mode
        screen_hints = _interactive_screen_hints()

    if not screen_hints:
        console.print("[yellow]No screens defined. Exiting.[/yellow]")
        raise typer.Exit(0)

    console.print()
    console.print(f"[bold]Screens:[/bold] {len(screen_hints)}")
    console.print(f"[bold]Text types:[/bold] {', '.join(t.value for t in types_to_generate)}")
    console.print()

    # Determine screenshots file path
    if path is None:
        path = detect_screenshots_path()
    if path is None:
        path = get_default_screenshots_path()

    # Load existing catalog or create new one
    if path.exists():
        try:
            catalog = read_screenshots(path)
            console.print(f"[dim]Using existing file: {path}[/dim]")
        except Exception:
            catalog = ScreenshotsCatalog(source_language=src_lang)
    else:
        catalog = ScreenshotsCatalog(source_language=src_lang)
        console.print(f"[dim]Will create new file: {path}[/dim]")

    # Determine which texts need to be generated
    generation_tasks: list[tuple[str, ScreenshotTextType, DeviceClass, str]] = []

    for screen_id, hint in screen_hints.items():
        for text_type in types_to_generate:
            for device_class in DeviceClass:
                # Check if text already exists
                screen = catalog.screens.get(screen_id)
                if screen and not overwrite:
                    existing_text = screen.get_text(text_type)
                    if existing_text:
                        existing_value = existing_text.get_variant(device_class)
                        if existing_value and existing_value.strip():
                            continue  # Skip - already exists

                generation_tasks.append((screen_id, text_type, device_class, hint))

    if not generation_tasks:
        console.print("[green]All texts already exist (use --overwrite to regenerate)[/green]")
        return

    console.print(f"[bold]Texts to generate:[/bold] {len(generation_tasks)}")

    if dry_run:
        console.print("\n[yellow]Dry run - showing prompts without API calls[/yellow]")
        _show_generation_dry_run(app_context, generation_tasks)
        return

    # Perform generation
    asyncio.run(
        _generate_screenshots(
            catalog=catalog,
            path=path,
            app_context=app_context,
            generation_tasks=generation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            model=model,
        )
    )


def _interactive_screen_hints() -> dict[str, str]:
    """Interactively prompt for screen descriptions."""
    console.print("[bold]Interactive mode[/bold] - describe each screenshot screen")
    console.print("[dim]Enter screen descriptions to help generate marketing text.[/dim]")
    console.print("[dim]Press Enter with empty description to finish.[/dim]")
    console.print()

    screen_hints: dict[str, str] = {}
    screen_num = 1

    while True:
        # Prompt for screen ID
        default_id = f"screen_{screen_num}"
        screen_id = typer.prompt(
            f"Screen {screen_num} ID",
            default=default_id,
            show_default=True,
        )

        if not screen_id:
            break

        # Prompt for description
        description = typer.prompt(
            f"  Description (what does this screen show?)",
            default="",
        )

        if not description:
            console.print("[dim]  Empty description, skipping this screen[/dim]")
            if not screen_hints:
                continue  # Keep asking if no screens yet
            break

        screen_hints[screen_id] = description
        screen_num += 1
        console.print()

    return screen_hints


def _show_generation_dry_run(
    app_context,
    tasks: list[tuple[str, str, str, str]],
) -> None:
    """Show generation prompts for dry run."""
    from localizerx.translator.screenshots_generation_prompts import build_generation_prompt

    console.print("\n[bold]Prompts that would be sent:[/bold]\n")

    # Show first few prompts
    for i, (screen_id, text_type, device_class, hint) in enumerate(tasks[:3]):
        prompt = build_generation_prompt(
            app_context=app_context,
            screen_id=screen_id,
            text_type=text_type,
            device_class=device_class,
            user_hint=hint,
        )

        console.print(f"[cyan]--- {screen_id} / {text_type.value} / {device_class.value} ---[/cyan]")
        # Show truncated prompt
        lines = prompt.split("\n")
        preview_lines = lines[:15]
        console.print("\n".join(preview_lines))
        if len(lines) > 15:
            console.print(f"[dim]... ({len(lines) - 15} more lines)[/dim]")
        console.print()

    if len(tasks) > 3:
        console.print(f"[dim]... and {len(tasks) - 3} more prompts[/dim]")


async def _generate_screenshots(
    catalog,
    path: Path,
    app_context,
    generation_tasks: list[tuple[str, str, str, str]],
    config,
    preview: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Perform screenshot text generation and update file."""
    from localizerx.io.screenshots import write_screenshots
    from localizerx.parser.screenshots_model import DeviceClass, ScreenshotTextType
    from localizerx.translator.screenshots_generation_prompts import build_generation_prompt

    ss_cfg = config.translator.screenshots
    cache_dir = get_cache_dir(config)
    actual_model = model or ss_cfg.model
    thinking_config = {"thinkingLevel": ss_cfg.thinking_level}

    # {(screen_id, text_type, device_class): generated_text}
    all_generations: dict[tuple, str] = {}

    async with GeminiTranslator(
        model=actual_model,
        batch_size=1,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
        temperature=ss_cfg.temperature,
        thinking_config=thinking_config,
    ) as translator:
        console.print("Generating screenshot texts...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Generating", total=len(generation_tasks))

            for screen_id, text_type, device_class, hint in generation_tasks:
                # Build generation prompt
                prompt = build_generation_prompt(
                    app_context=app_context,
                    screen_id=screen_id,
                    text_type=text_type,
                    device_class=device_class,
                    user_hint=hint,
                )

                try:
                    generated = await translator._call_api(prompt)
                    generated = generated.strip()
                except Exception as e:
                    console.print(
                        f"  [red]Error generating {screen_id}/{text_type.value}: {e}[/red]"
                    )
                    progress.advance(task)
                    continue

                all_generations[(screen_id, text_type, device_class)] = generated
                progress.advance(task)

    if not all_generations:
        console.print("[red]No texts were generated[/red]")
        return

    # Show preview if requested
    if preview:
        _show_generation_preview(all_generations)
        if not typer.confirm("Save these generated texts?"):
            console.print("  [yellow]Cancelled[/yellow]")
            return

    # Update catalog
    for (screen_id, text_type, device_class), generated_text in all_generations.items():
        screen = catalog.get_or_create_source_screen(screen_id)
        screen.set_text_variant(text_type, device_class, generated_text)

    # Write file
    write_screenshots(catalog, path, backup=backup)

    console.print(f"\n[green]Saved {len(all_generations)} generated texts to {path}[/green]")
    console.print("\nNext steps:")
    console.print("  1. Review and edit the generated texts in the file")
    console.print("  2. Translate to other languages with:")
    console.print("     localizerx screenshots --to de,fr,es")


def _show_generation_preview(generations: dict) -> None:
    """Show preview of generated texts."""
    table = Table(title="Generated Texts Preview")
    table.add_column("Screen", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Device", style="blue")
    table.add_column("Generated Text", style="green")

    count = 0
    for (screen_id, text_type, device_class), text in generations.items():
        text_preview = text[:40] + "..." if len(text) > 40 else text
        table.add_row(
            screen_id,
            text_type.value,
            device_class.value,
            text_preview,
        )
        count += 1
        if count >= 20:
            break

    if len(generations) > 20:
        table.add_row("...", "", "", f"({len(generations) - 20} more)")

    console.print(table)


def _run_screenshots_translate(
    path: Path | None,
    to: str,
    src: str,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Core screenshots translation logic."""
    from localizerx.io.screenshots import (
        create_screenshots_template,
        detect_screenshots_path,
        get_default_screenshots_path,
        read_screenshots,
    )

    config = load_config()

    # Determine file path
    if path is None:
        path = detect_screenshots_path()

    # If file doesn't exist, create template
    if path is None or not path.exists():
        template_path = path or get_default_screenshots_path()
        console.print(f"[yellow]Creating template:[/yellow] {template_path}")

        src_lang = src if src else config.source_language
        create_screenshots_template(template_path, source_language=src_lang)

        console.print(f"[green]Created screenshots template at {template_path}[/green]")
        console.print("\nEdit the file to add your screenshot texts, then run:")
        console.print(f"  localizerx screenshots --to de,fr,es")
        return

    # File exists, translate it
    try:
        catalog = read_screenshots(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Determine source language
    source_lang = src if src else catalog.source_language

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

    # Validate
    invalid_langs = [lang for lang in target_langs if not validate_language_code(lang)]
    if invalid_langs:
        codes = ", ".join(invalid_langs)
        console.print(f"[yellow]Warning:[/yellow] Unrecognized language codes: {codes}")

    console.print(f"[bold]Screenshots File:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_language_name(source_lang)} ({source_lang})")
    target_display = ", ".join(f"{get_language_name(loc)} ({loc})" for loc in target_langs)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Determine texts to translate per language
    from localizerx.parser.screenshots_model import DeviceClass

    translation_tasks: dict[str, list] = {}  # lang -> [(screen_id, text_type, device_class)]

    for target_lang in target_langs:
        needs = catalog.get_texts_needing_translation(target_lang, overwrite=overwrite)
        if needs:
            translation_tasks[target_lang] = needs

    if not translation_tasks:
        console.print("[green]All texts already translated[/green]")
        return

    # Show summary
    for lang, texts in translation_tasks.items():
        console.print(f"  {get_language_name(lang)}: {len(texts)} text(s) to translate")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        _show_screenshots_dry_run(catalog, translation_tasks)
        return

    # Perform translation
    asyncio.run(
        _translate_screenshots(
            catalog=catalog,
            path=path,
            source_lang=source_lang,
            translation_tasks=translation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            model=model,
        )
    )


def _show_screenshots_dry_run(
    catalog,
    tasks: dict[str, list],
) -> None:
    """Show table of texts that would be translated."""
    from localizerx.parser.screenshots_model import SCREENSHOT_TEXT_WORD_LIMIT

    table = Table(title="Texts to Translate")
    table.add_column("Language", style="cyan")
    table.add_column("Screen", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Device", style="blue")
    table.add_column("Words", style="green")

    for lang, items in tasks.items():
        for screen_id, text_type, device_class in items[:20]:
            screen = catalog.screens.get(screen_id)
            if screen:
                text = screen.get_text(text_type)
                if text:
                    word_count = text.word_count(device_class)
                    words_str = str(word_count)
                    if word_count > SCREENSHOT_TEXT_WORD_LIMIT:
                        words_str = f"[red]{word_count}[/red]"
                    table.add_row(
                        lang,
                        screen_id,
                        text_type.value,
                        device_class.value,
                        words_str,
                    )

        if len(items) > 20:
            table.add_row(lang, f"... ({len(items) - 20} more)", "", "", "")

    console.print(table)


async def _translate_screenshots(
    catalog,
    path: Path,
    source_lang: str,
    translation_tasks: dict[str, list],
    config,
    preview: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Perform screenshot text translations and update file."""
    from localizerx.io.screenshots import write_screenshots
    from localizerx.parser.screenshots_model import DeviceClass, ScreenshotTextType
    from localizerx.translator.screenshots_prompts import (
        build_batch_screenshot_prompt,
        build_screenshot_prompt,
        parse_batch_screenshot_response,
    )

    ss_cfg = config.translator.screenshots
    cache_dir = get_cache_dir(config)
    actual_model = model or ss_cfg.model
    thinking_config = {"thinkingLevel": ss_cfg.thinking_level}

    batch_size = ss_cfg.batch_size

    async with GeminiTranslator(
        model=actual_model,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
        temperature=ss_cfg.temperature,
        thinking_config=thinking_config,
    ) as translator:
        # {lang: {(screen_id, text_type, device_class): translated_text}}
        all_translations: dict[str, dict[tuple, str]] = {}

        for target_lang, items in translation_tasks.items():
            console.print(f"  Translating to {get_language_name(target_lang)}...")
            all_translations[target_lang] = {}

            # Resolve source texts, filtering out missing screens/variants
            resolved: list[tuple[str, ScreenshotTextType, DeviceClass, str]] = []
            for screen_id, text_type, device_class in items:
                screen = catalog.screens.get(screen_id)
                if not screen:
                    continue
                text_obj = screen.get_text(text_type)
                if not text_obj:
                    continue
                source_text = text_obj.get_variant(device_class)
                if not source_text:
                    continue
                resolved.append((screen_id, text_type, device_class, source_text))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"    {target_lang}", total=len(resolved))

                for batch_start in range(0, len(resolved), batch_size):
                    batch = resolved[batch_start : batch_start + batch_size]

                    try:
                        if len(batch) == 1:
                            screen_id, text_type, device_class, source_text = batch[0]
                            prompt = build_screenshot_prompt(
                                text=source_text,
                                text_type=text_type,
                                device_class=device_class,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                            )
                            response = await translator._call_api(prompt)
                            translations = [response.strip()]
                        else:
                            prompt = build_batch_screenshot_prompt(
                                items=batch,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                            )
                            response = await translator._call_api(prompt)
                            translations = parse_batch_screenshot_response(
                                response, len(batch)
                            )

                        for (screen_id, text_type, device_class, _), translated in zip(
                            batch, translations
                        ):
                            if translated:
                                all_translations[target_lang][
                                    (screen_id, text_type, device_class)
                                ] = translated
                    except Exception as e:
                        items_str = ", ".join(
                            f"{sid}/{tt.value}" for sid, tt, _, _ in batch
                        )
                        console.print(
                            f"    [red]Error translating batch [{items_str}]: {e}[/red]"
                        )

                    progress.advance(task, advance=len(batch))

        # Show preview if requested
        if preview:
            _show_screenshots_preview(catalog, all_translations)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog
        for target_lang, translations in all_translations.items():
            locale_data = catalog.get_or_create_locale(target_lang)

            for (screen_id, text_type, device_class), translated_text in translations.items():
                target_screen = locale_data.get_or_create_screen(screen_id)
                target_screen.set_text_variant(text_type, device_class, translated_text)

        # Write file
        write_screenshots(catalog, path, backup=backup)

        console.print(f"\n[green]Saved translations to {path}[/green]")


def _show_screenshots_preview(catalog, all_translations: dict) -> None:
    """Show preview of screenshot translations."""
    table = Table(title="Translation Preview")
    table.add_column("Language", style="cyan")
    table.add_column("Screen", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Original", style="dim")
    table.add_column("Translation", style="green")

    count = 0
    for lang, translations in all_translations.items():
        for (screen_id, text_type, device_class), translated in translations.items():
            screen = catalog.screens.get(screen_id)
            original = ""
            if screen:
                text = screen.get_text(text_type)
                if text:
                    original = text.get_variant(device_class) or ""

            orig_preview = original[:25] + "..." if len(original) > 25 else original
            trans_preview = translated[:25] + "..." if len(translated) > 25 else translated

            table.add_row(
                lang,
                screen_id,
                f"{text_type.value}/{device_class.value}",
                orig_preview,
                trans_preview,
            )
            count += 1
            if count >= 20:
                break
        if count >= 20:
            break

    total = sum(len(t) for t in all_translations.values())
    if total > 20:
        table.add_row("...", "", "", "", f"({total - 20} more)")

    console.print(table)


if __name__ == "__main__":
    app()
