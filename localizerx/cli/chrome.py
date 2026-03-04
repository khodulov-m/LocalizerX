"""Chrome Extension locale commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console, create_progress
from localizerx.config import get_cache_dir, load_config
from localizerx.translator.base import TranslationRequest
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.utils.locale import (
    chrome_to_standard_locale,
    get_chrome_locale_name,
    parse_chrome_locale_list,
    validate_chrome_locale,
)


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
    remove: Annotated[
        Optional[str],
        typer.Option(
            "--remove",
            "-r",
            help="Locales to remove (comma-separated, e.g., 'fr,de').",
        ),
    ] = None,
) -> None:
    """Translate Chrome Extension _locales/ messages to target locales."""
    if not to and not remove:
        console.print("[red]Error:[/red] --to or --remove option is required")
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
        backup=backup,
        model=model,
        remove=remove,
    )


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
    remove: str | None = None,
) -> None:
    """Core Chrome Extension translation logic."""
    from localizerx.io.extension import delete_extension_locale, detect_extension_path, read_extension
    from localizerx.parser.extension_model import KNOWN_CWS_KEYS

    config = load_config()

    # Parse target locales (hyphen -> underscore)
    target_locales = parse_chrome_locale_list(to) if to else []
    remove_locales = parse_chrome_locale_list(remove) if remove else []

    # Validate locales
    invalid_locales = [
        loc for loc in target_locales + remove_locales if not validate_chrome_locale(loc)
    ]
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

    # Handle removal first
    actually_removed = []
    if remove_locales:
        for loc in remove_locales:
            if loc == src:
                console.print(f"[yellow]Skipping source locale removal:[/yellow] {loc}")
                continue

            if dry_run:
                actually_removed.append(loc)
                continue

            if delete_extension_locale(path, loc):
                actually_removed.append(loc)

        if actually_removed:
            status = "Would remove" if dry_run else "Removed"
            console.print(f"[yellow]{status} {len(actually_removed)} locale(s):[/yellow] {', '.join(actually_removed)}")

        if not target_locales:
            if dry_run:
                console.print("\n[yellow]Dry run - no changes made[/yellow]")
            return

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

    thinking_level = getattr(config.translator, "thinking_level", "0")
    thinking_config = {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None

    async with GeminiTranslator(
        thinking_config=thinking_config,
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

            with create_progress() as progress:
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
