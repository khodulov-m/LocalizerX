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
            console.print(f"Valid fields: {', '.join(f.value for f in MetadataFieldType)}")
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
            keywords_words = _extract_keywords(keywords_field.content) if keywords_field else set()

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
    console.print(f"[bold]Metadata Directory:[/bold] {path}")
    console.print(f"[bold]Locales Checked:[/bold] {len(locales_to_check)}")
    console.print(f"[bold]Fields Checked:[/bold] {field or 'all'}")
    console.print()

    has_issues = False

    # Character limit results
    if all_valid:
        console.print("[green]✓ All fields are within character limits[/green]")
    else:
        has_issues = True
        console.print(f"[red]✗ Found {len(violations)} field(s) exceeding character limits[/red]")
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

    # Duplicate word results (ASO optimization)
    console.print()
    if skip_duplicates:
        console.print("[dim]Duplicate word check skipped (--skip-duplicates)[/dim]")
    elif not duplicates:
        console.print("[green]✓ No duplicate words between name/subtitle/keywords[/green]")
    else:
        console.print(
            f"[yellow]⚠ Found {len(duplicates)} duplicate word issue(s) (ASO optimization)[/yellow]"
        )
        console.print()

        # Show duplicates table
        duplicates_table = Table(title="Duplicate Words (ASO)")
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
        console.print()
        console.print(
            "[yellow]Tip:[/yellow] Apple indexes words from name, subtitle, and keywords."
        )
        console.print("      Repeating words wastes valuable character space.")
        console.print("      Use --skip-duplicates to disable this check.")

    # Summary
    console.print()
    if not has_issues and not duplicates:
        # Show summary table
        summary_table = Table(title="Character Limit Summary")
        summary_table.add_column("Field", style="cyan")
        summary_table.add_column("Limit", style="white")

        field_types_to_show = [field_type_filter] if field_type_filter else list(MetadataFieldType)
        for ft in field_types_to_show:
            from localizerx.parser.metadata_model import FIELD_LIMITS

            summary_table.add_row(ft.value, str(FIELD_LIMITS[ft]))

        console.print(summary_table)

    if has_issues:
        console.print()
        console.print(
            "[yellow]Tip:[/yellow] Use --field to check a specific field"
            " or --locale to check a specific locale"
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
    temperature: float | None,
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
            temperature=temperature,
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
    temperature: float | None,
) -> None:
    """Perform metadata translations and update files.

    All fields for each locale are sent in a single batched API call.
    Locales are translated concurrently (up to 5 in parallel).
    """
    from localizerx.io.metadata import write_metadata
    from localizerx.parser.metadata_model import MetadataFieldType
    from localizerx.translator.metadata_prompts import (
        build_batch_metadata_prompt,
        build_keywords_prompt,
        build_metadata_prompt,
        parse_batch_metadata_response,
    )
    from localizerx.utils.limits import LimitAction, truncate_to_limit, validate_limit

    cache_dir = get_cache_dir(config)
    actual_model = model or config.translator.model
    actual_temperature = temperature if temperature is not None else config.translator.temperature

    source = catalog.get_source_metadata()
    if not source:
        return

    semaphore = asyncio.Semaphore(5)

    thinking_level = getattr(config.translator, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    async with GeminiTranslator(
        thinking_config=thinking_config,
        model=actual_model,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
        temperature=actual_temperature,
    ) as translator:
        all_translations: dict[str, dict[MetadataFieldType, str]] = {}

        async def _translate_locale(
            target_locale: str, field_types: list[MetadataFieldType]
        ) -> tuple[str, dict[MetadataFieldType, str]]:
            """Translate all fields for one locale in a single batch API call."""
            async with semaphore:
                items: list[tuple[MetadataFieldType, str]] = []
                for ft in field_types:
                    field = source.get_field(ft)
                    if field:
                        items.append((ft, field.content))

                if not items:
                    return target_locale, {}

                # Single field — use the specialized prompt for best quality
                if len(items) == 1:
                    ft, text = items[0]
                    if ft == MetadataFieldType.KEYWORDS:
                        prompt = build_keywords_prompt(text, source_locale, target_locale)
                    else:
                        prompt = build_metadata_prompt(text, ft, source_locale, target_locale)
                    response = await translator._call_api(prompt)
                    return target_locale, {ft: response.strip()}

                # Multiple fields — batch into a single API call
                prompt = build_batch_metadata_prompt(items, source_locale, target_locale)
                response = await translator._call_api(prompt)
                translations = parse_batch_metadata_response(response, len(items))

                result: dict[MetadataFieldType, str] = {}
                for (ft, _), translated in zip(items, translations):
                    if translated:
                        result[ft] = translated
                return target_locale, result

        with create_progress() as progress:
            progress_task = progress.add_task(
                "Translating metadata...", total=len(translation_tasks)
            )

            async def _with_progress(target_locale, field_types):
                try:
                    return await _translate_locale(target_locale, field_types)
                finally:
                    progress.advance(progress_task)

            results = await asyncio.gather(
                *[_with_progress(loc, fields) for loc, fields in translation_tasks.items()],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    console.print(f"    [red]Error: {result}[/red]")
                else:
                    locale, translations = result
                    all_translations[locale] = translations

        # Validate character limits
        limit_warnings: list[str] = []
        for target_locale, translations in all_translations.items():
            for field_type, translated in list(translations.items()):
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
                        all_translations[target_locale][field_type] = truncate_to_limit(
                            translated, field_type
                        )
                        console.print(
                            f"    [yellow]Truncated: [{target_locale}] {field_type.value}[/yellow]"
                        )
                    else:  # warn
                        console.print(f"    [yellow]Warning: {warning}[/yellow]")

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

        write_metadata(
            catalog,
            path,
            backup=backup,
            locales=list(all_translations.keys()),
        )

        # Copy untranslatable files from source locale to target locales
        import shutil

        untranslatable_files = [
            "marketing_url.txt",
            "privacy_url.txt",
            "support_url.txt",
            "apple_tv_privacy_policy.txt",
        ]
        source_dir = path / source_locale
        if source_dir.exists():
            for target_locale in all_translations.keys():
                target_dir = path / target_locale
                target_dir.mkdir(parents=True, exist_ok=True)
                for filename in untranslatable_files:
                    src_file = source_dir / filename
                    if src_file.exists():
                        dst_file = target_dir / filename
                        if backup and dst_file.exists():
                            backup_path = dst_file.with_suffix(".txt.backup")
                            shutil.copy2(dst_file, backup_path)
                        shutil.copy2(src_file, dst_file)

        console.print(f"\n[green]Saved translations to {path}[/green]")

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
