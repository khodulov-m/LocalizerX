"""Fastlane metadata commands."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console, create_progress
from localizerx.config import get_cache_dir, load_config
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.adapters.repository import MetadataCatalogRepository
from localizerx.core.use_cases.translate_metadata import (
    MetadataTranslationPreview,
    MetadataTranslationTask,
    TranslateMetadataRequest,
    TranslateMetadataUseCase,
)
from localizerx.utils.locale import (
    get_fastlane_locale_name,
    parse_fastlane_locale_list,
    validate_fastlane_locale,
)

# Common stop words to ignore in duplicate detection (short words with little SEO value)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "my",
        "your",
        "his",
        "her",
        "our",
        "their",
        "&",
        "-",
        "—",
        "+",
    }
)


def _extract_words(text: str) -> set[str]:
    """Extract significant words from text for duplicate detection.

    Normalizes to lowercase and filters out stop words and short words.
    """
    # Split on non-alphanumeric characters (handles both spaces and commas)
    words = re.split(r"[^a-zA-Z0-9]+", text.lower())
    # Filter: non-empty, not a stop word, at least 2 characters
    return {w for w in words if w and w not in _STOP_WORDS and len(w) >= 2}


def _extract_keywords(keywords_text: str) -> set[str]:
    """Extract individual keywords from comma-separated keywords string.

    Returns both full keyword phrases and individual words within them.
    """
    words = set()
    for keyword in keywords_text.split(","):
        keyword = keyword.strip().lower()
        if keyword:
            # Add individual words from the keyword phrase
            words.update(_extract_words(keyword))
    return words


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
            help=(
                "Target locales (comma-separated, e.g., 'de-DE,fr-FR,es-ES')."
                " Omit to use defaults from config."
            ),
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
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Create backup before writing changes",
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
) -> None:
    """Translate fastlane App Store metadata to target locales."""
    from localizerx.io.metadata import detect_all_metadata_paths

    # Validate on_limit option
    from localizerx.utils.limits import LimitAction

    try:
        limit_action = LimitAction(on_limit)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid --on-limit value: {on_limit}")
        console.print("Valid options: warn, truncate, error")
        raise typer.Exit(1)

    # Determine paths to process
    if path is not None:
        if not path.exists():
            console.print(f"[red]Error:[/red] Path does not exist: {path}")
            raise typer.Exit(1)
        paths = [path]
    else:
        paths = detect_all_metadata_paths()
        if not paths:
            console.print("[red]Error:[/red] No metadata directory found")
            console.print("Run from a directory with fastlane/metadata or specify path")
            raise typer.Exit(1)

    for p in paths:
        if len(paths) > 1:
            rel_path = p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p
            console.print(f"\n[bold blue]Processing metadata in {rel_path}[/bold blue]")

        _run_metadata_translate(
            path=p,
            to=to,
            src=src,
            fields=fields,
            limit_action=limit_action,
            dry_run=dry_run,
            preview=preview,
            overwrite=overwrite,
            backup=backup,
            model=model,
            temperature=temperature,
        )


def metadata_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to fastlane metadata directory (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about fastlane metadata files."""
    from localizerx.io.metadata import detect_all_metadata_paths, read_metadata
    from localizerx.parser.metadata_model import FIELD_LIMITS, MetadataFieldType

    # Find metadata paths
    if path is not None:
        if not path.exists():
            console.print(f"[red]Error:[/red] Path does not exist: {path}")
            raise typer.Exit(1)
        paths = [path]
    else:
        paths = detect_all_metadata_paths()
        if not paths:
            console.print("[red]Error:[/red] No metadata directory found")
            console.print("Run from a directory with fastlane/metadata or specify path")
            raise typer.Exit(1)

    for p in paths:
        rel_path = p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p
        if len(paths) > 1:
            console.print(f"\n[bold blue]Metadata in {rel_path}:[/bold blue]")

        # Read metadata
        try:
            catalog = read_metadata(p)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        console.print(f"[bold]Metadata Directory:[/bold] {p}")
        console.print(f"[bold]Source Locale:[/bold] {catalog.source_locale}")
        console.print(f"[bold]Total Locales:[/bold] {catalog.locale_count}")
        console.print()

        # Show locale table
        table = Table(title=f"Locale Status ({p.name})")
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
    skip_duplicates: Annotated[
        bool,
        typer.Option(
            "--skip-duplicates",
            help="Skip duplicate word check between name/subtitle/keywords",
        ),
    ] = False,
) -> None:
    """Check metadata files for App Store character limit compliance and ASO optimization."""
    from localizerx.io.metadata import detect_all_metadata_paths, read_metadata
    from localizerx.parser.metadata_model import FIELD_LIMITS, MetadataFieldType
    from localizerx.utils.limits import validate_limit

    # Find metadata paths
    if path is not None:
        if not path.exists():
            console.print(f"[red]Error:[/red] Path does not exist: {path}")
            raise typer.Exit(1)
        paths = [path]
    else:
        paths = detect_all_metadata_paths()
        if not paths:
            console.print("[red]Error:[/red] No metadata directory found")
            console.print("Run from a directory with fastlane/metadata or specify path")
            raise typer.Exit(1)

    all_paths_valid = True
    any_locales_checked = False

    # Parse field filter early
    field_type_filter: MetadataFieldType | None = None
    if field:
        try:
            field_type_filter = MetadataFieldType(field.lower())
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid field type: {field}")
            console.print(f"Valid fields: {', '.join(f.value for f in MetadataFieldType)}")
            raise typer.Exit(1)

    for p in paths:
        rel_path = p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p
        if len(paths) > 1:
            console.print(f"\n[bold blue]Checking metadata in {rel_path}:[/bold blue]")

        # Read metadata
        try:
            catalog = read_metadata(p)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        # Filter locales
        locales_to_check = [locale] if locale else list(catalog.locales.keys())
        locales_to_check = [loc for loc in locales_to_check if loc in catalog.locales]

        if not locales_to_check:
            if locale:  # Explicit locale requested
                console.print(f"[red]Error:[/red] No valid locales to check in {p}")
                all_paths_valid = False
            else:
                console.print(f"[yellow]Warning:[/yellow] No valid locales to check in {p}")
            continue

        any_locales_checked = True

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

        # Check for duplicate words between name/subtitle/keywords (ASO optimization)
        duplicates: list[dict] = []
        if not skip_duplicates:
            for locale_code in sorted(locales_to_check):
                locale_meta = catalog.locales[locale_code]
                locale_name = get_fastlane_locale_name(locale_code)

                # Get content from ASO-critical fields
                name_field = locale_meta.get_field(MetadataFieldType.NAME)
                subtitle_field = locale_meta.get_field(MetadataFieldType.SUBTITLE)
                keywords_field = locale_meta.get_field(MetadataFieldType.KEYWORDS)

                name_words = _extract_words(name_field.content) if name_field else set()
                subtitle_words = _extract_words(subtitle_field.content) if subtitle_field else set()
                keywords_words = (
                    _extract_keywords(keywords_field.content) if keywords_field else set()
                )

                # Find duplicates between fields
                name_in_keywords = name_words & keywords_words
                subtitle_in_keywords = subtitle_words & keywords_words
                name_in_subtitle = name_words & subtitle_words

                if name_in_keywords:
                    duplicates.append(
                        {
                            "locale": locale_code,
                            "locale_name": locale_name,
                            "fields": "name → keywords",
                            "words": sorted(name_in_keywords),
                        }
                    )
                if subtitle_in_keywords:
                    duplicates.append(
                        {
                            "locale": locale_code,
                            "locale_name": locale_name,
                            "fields": "subtitle → keywords",
                            "words": sorted(subtitle_in_keywords),
                        }
                    )
                if name_in_subtitle:
                    duplicates.append(
                        {
                            "locale": locale_code,
                            "locale_name": locale_name,
                            "fields": "name → subtitle",
                            "words": sorted(name_in_subtitle),
                        }
                    )

        # Display results
        console.print(f"[bold]Metadata Directory:[/bold] {p}")
        console.print(f"[bold]Locales Checked:[/bold] {len(locales_to_check)}")
        console.print(f"[bold]Fields Checked:[/bold] {field or 'all'}")
        console.print()

        # Character limit results
        if all_valid:
            console.print("[green]✓ All fields are within character limits[/green]")
        else:
            all_paths_valid = False
            console.print(
                f"[red]✗ Found {len(violations)} field(s) exceeding character limits[/red]"
            )
            console.print()

            # Show violations table
            violations_table = Table(title=f"Character Limit Violations ({p.name})")
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

        # Duplicate word results (ASO optimization)
        console.print()
        if skip_duplicates:
            console.print("[dim]Duplicate word check skipped (--skip-duplicates)[/dim]")
        elif not duplicates:
            console.print("[green]✓ No duplicate words between name/subtitle/keywords[/green]")
        else:
            console.print(
                f"[yellow]⚠ Found {len(duplicates)} duplicate word issue(s) "
                "(ASO optimization)[/yellow]"
            )
            console.print()

            # Show duplicates table
            duplicates_table = Table(title=f"Duplicate Words (ASO) - {p.name}")
            duplicates_table.add_column("Locale", style="cyan")
            duplicates_table.add_column("Fields", style="yellow")
            duplicates_table.add_column("Duplicated Words", style="magenta")

            for d in duplicates:
                words_str = ", ".join(d["words"])
                duplicates_table.add_row(
                    f"{d['locale']}\n{d['locale_name']}",
                    d["fields"],
                    words_str,
                )

            console.print(duplicates_table)

        # Summary
        if not all_valid or (not skip_duplicates and duplicates):
            # Skip summary if there are issues
            pass
        else:
            console.print()
            summary_table = Table(title=f"Character Limit Summary ({p.name})")
            summary_table.add_column("Field", style="cyan")
            summary_table.add_column("Limit", style="white")

            field_types_to_show = (
                [field_type_filter] if field_type_filter else list(MetadataFieldType)
            )
            for ft in field_types_to_show:
                summary_table.add_row(ft.value, str(FIELD_LIMITS[ft]))

            console.print(summary_table)

    if not any_locales_checked:
        raise typer.Exit(1)

    if not all_paths_valid:
        raise typer.Exit(1)


def metadata_urls(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to fastlane metadata directory (auto-detected if omitted)",
        ),
    ] = None,
    marketing: Annotated[
        Optional[str],
        typer.Option("--marketing", help="URL for marketing_url.txt"),
    ] = None,
    privacy: Annotated[
        Optional[str],
        typer.Option("--privacy", help="URL for privacy_url.txt"),
    ] = None,
    support: Annotated[
        Optional[str],
        typer.Option("--support", help="URL for support_url.txt"),
    ] = None,
    apple_tv_privacy: Annotated[
        Optional[str],
        typer.Option("--apple-tv-privacy", help="URL for apple_tv_privacy_policy.txt"),
    ] = None,
) -> None:
    """Set URL files for all existing locales in fastlane metadata."""
    from localizerx.io.metadata import detect_all_metadata_paths, get_available_locales

    # Find metadata paths
    if path is not None:
        if not path.exists():
            console.print(f"[red]Error:[/red] Path does not exist: {path}")
            raise typer.Exit(1)
        paths = [path]
    else:
        paths = detect_all_metadata_paths()
        if not paths:
            console.print("[red]Error:[/red] No metadata directory found")
            console.print("Run from a directory with fastlane/metadata or specify path")
            raise typer.Exit(1)

    urls = {}
    if marketing is not None:
        urls["marketing_url.txt"] = marketing
    if privacy is not None:
        urls["privacy_url.txt"] = privacy
    if support is not None:
        urls["support_url.txt"] = support
    if apple_tv_privacy is not None:
        urls["apple_tv_privacy_policy.txt"] = apple_tv_privacy

    if not urls:
        console.print(
            "[yellow]No URLs specified. Use --marketing, --privacy, "
            "--support, or --apple-tv-privacy.[/yellow]"
        )
        raise typer.Exit(0)

    for p in paths:
        rel_path = p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p
        locales = get_available_locales(p)
        if not locales:
            console.print(f"[yellow]Warning:[/yellow] No locales found in {rel_path}")
            continue

        for locale in locales:
            locale_dir = p / locale
            for filename, url in urls.items():
                file_path = locale_dir / filename
                file_path.write_text(url + "\n", encoding="utf-8")

        console.print(
            f"[green]Successfully updated URLs for {len(locales)} locales in {rel_path}[/green]"
        )


def _run_metadata_translate(
    path: Path,
    to: str,
    src: str,
    fields: str | None,
    limit_action,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
    temperature: float | None,
) -> None:
    """Core metadata translation logic."""
    from localizerx.io.metadata import read_metadata
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

    repository = MetadataCatalogRepository()
    
    cache_dir = get_cache_dir(config)
    actual_model = model or config.metadata.model
    actual_temperature = temperature if temperature is not None else config.metadata.temperature
    
    thinking_level = getattr(config.metadata, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    # Read metadata early to validate source locale
    try:
        catalog = repository.read(path, source_locale=src)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

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

    # Callbacks
    def on_task_summary(tasks: dict[str, MetadataTranslationTask]):
        for locale, task in tasks.items():
            field_names = ", ".join(f.value for f in task.field_types)
            console.print(f"  {get_fastlane_locale_name(locale)}: {field_names}")
            
        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            # Use the catalog we already read
            _show_metadata_dry_run_from_tasks(catalog, tasks)

    progress = None
    
    def on_translation_start(locale: str, total: int):
        nonlocal progress
        if not progress:
            progress = create_progress()
            progress.start()
        # console.print(f"  Translating to {get_fastlane_locale_name(locale)}...")
        return progress.add_task(f"Translating metadata...", total=total)

    def on_translation_progress(task_id, advance_by):
        if progress:
            progress.advance(task_id, advance_by)

    def on_preview_request(items: list[MetadataTranslationPreview]) -> bool:
        if progress:
            progress.stop()
        table = Table(title="Translation Preview")
        table.add_column("Locale", style="cyan")
        table.add_column("Field", style="white")
        table.add_column("Translation", style="green")
        table.add_column("Chars", style="yellow")
        
        for i, item in enumerate(items):
            if i >= 20:
                break
            preview_value = item.translation[:60] + "..." if len(item.translation) > 60 else item.translation
            preview_value = preview_value.replace("\n", " ")
            
            chars_display = str(item.chars)
            if item.is_over_limit:
                chars_display = f"[red]{chars_display} (limit {item.limit})[/red]"
                
            table.add_row(item.locale, item.field_type.value, preview_value, chars_display)
            
        if len(items) > 20:
            table.add_row("...", "", "", f"({len(items) - 20} more)")
            
        console.print(table)
        apply = typer.confirm("Apply these translations?")
        if not apply:
            console.print("  [yellow]Cancelled[/yellow]")
        return apply

    async def _run_async():
        async with GeminiTranslator(
            thinking_config=thinking_config,
            model=actual_model,
            max_retries=config.metadata.max_retries,
            cache_dir=cache_dir,
            temperature=actual_temperature,
        ) as translator:
            
            use_case = TranslateMetadataUseCase(repository=repository, translator=translator)
            request = TranslateMetadataRequest(
                path=path,
                source_locale=src,
                target_locales=target_locales,
                field_types=field_types,
                dry_run=dry_run,
                preview=preview,
                overwrite=overwrite,
                limit_action=limit_action,
                backup=backup,
            )
            
            try:
                result = await use_case.execute(
                    request=request,
                    on_task_summary=on_task_summary,
                    on_translation_start=on_translation_start,
                    on_translation_progress=on_translation_progress,
                    on_preview_request=on_preview_request,
                )
                
                if result.saved:
                    console.print(f"\n[green]Saved translations to {path}[/green]")
                elif not result.tasks and not dry_run:
                     console.print("[green]All fields already translated[/green]")
                
                if result.limit_warnings:
                    console.print(f"\n[yellow]Character limit warnings ({len(result.limit_warnings)}):[/yellow]")
                    for warning in result.limit_warnings[:10]:
                        console.print(f"  {warning}")
                    if len(result.limit_warnings) > 10:
                        console.print(f"  ... and {len(result.limit_warnings) - 10} more")
                     
            finally:
                if progress:
                    progress.stop()

    asyncio.run(_run_async())


def _show_metadata_dry_run_from_tasks(catalog, tasks: dict[str, MetadataTranslationTask]) -> None:
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

    for locale, task in tasks.items():
        for field_type in task.field_types:
            field = source.get_field(field_type)
            if field:
                table.add_row(
                    locale,
                    field_type.value,
                    str(field.char_count),
                    str(FIELD_LIMITS[field_type]),
                )

    console.print(table)
