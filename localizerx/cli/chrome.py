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
from localizerx.adapters.repository import ExtensionCatalogRepository
from localizerx.core.use_cases.translate_extension import (
    ExtensionTranslationPreview,
    ExtensionTranslationTask,
    TranslateExtensionRequest,
    TranslateExtensionUseCase,
)
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
    from localizerx.io.extension import detect_extension_path
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

    repository = ExtensionCatalogRepository()
    
    cache_dir = get_cache_dir(config)
    actual_model = model or config.chrome.model
    
    thinking_level = getattr(config.chrome, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    # Callbacks
    def on_remove(locales: list[str]):
        status = "Would remove" if dry_run else "Removed"
        console.print(
            f"[yellow]{status} {len(locales)} locale(s):[/yellow] "
            f"{', '.join(locales)}"
        )

    def on_task_summary(tasks: dict[str, ExtensionTranslationTask]):
        for locale, task in tasks.items():
            cws_count = sum(1 for m in task.messages if m.key in KNOWN_CWS_KEYS)
            regular_count = len(task.messages) - cws_count
            parts = []
            if cws_count:
                parts.append(f"{cws_count} CWS field(s)")
            if regular_count:
                parts.append(f"{regular_count} message(s)")
            console.print(f"  {get_chrome_locale_name(locale)}: {', '.join(parts)}")
            
        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            _show_chrome_dry_run_from_tasks(tasks)

    progress = None
    
    def on_translation_start(locale: str, total: int):
        nonlocal progress
        if not progress:
            progress = create_progress()
            progress.start()
        console.print(f"  Translating to {get_chrome_locale_name(locale)}...")
        return progress.add_task(f"    {locale}", total=total)

    def on_translation_progress(task_id, advance_by):
        if progress:
            progress.advance(task_id, advance_by)

    def on_preview_request(items: list[ExtensionTranslationPreview]) -> bool:
        if progress:
            progress.stop()
        table = Table(title="Translation Preview")
        table.add_column("Locale", style="cyan")
        table.add_column("Key", style="white")
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
                
            table.add_row(item.locale, item.key[:30], preview_value, chars_display)
            
        if len(items) > 20:
            table.add_row("...", "", f"({len(items) - 20} more)", "")
            
        console.print(table)
        apply = typer.confirm("Apply these translations?")
        if not apply:
            console.print("  [yellow]Cancelled[/yellow]")
        return apply

    async def _run_async():
        async with GeminiTranslator(
            thinking_config=thinking_config,
            model=actual_model,
            batch_size=config.chrome.batch_size,
            max_retries=config.chrome.max_retries,
            cache_dir=cache_dir,
        ) as translator:
            
            use_case = TranslateExtensionUseCase(repository=repository, translator=translator)
            request = TranslateExtensionRequest(
                path=path,
                source_locale=src,
                target_locales=target_locales,
                remove_locales=remove_locales,
                dry_run=dry_run,
                preview=preview,
                overwrite=overwrite,
                backup=backup,
                limit_action=limit_action,
            )
            
            try:
                result = await use_case.execute(
                    request=request,
                    on_remove=on_remove,
                    on_task_summary=on_task_summary,
                    on_translation_start=on_translation_start,
                    on_translation_progress=on_translation_progress,
                    on_preview_request=on_preview_request,
                )
                
                if result.saved:
                    console.print(f"\n[green]Saved translations to {path}[/green]")
                elif not result.tasks and not result.removed_locales and not dry_run:
                     console.print("[green]All messages already translated[/green]")
                
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


def _show_dry_run_table(tasks: dict[str, ExtensionTranslationTask]) -> None:
    """Show table of messages that would be translated."""
    # This matches the legacy function's signature but we'll use our Task objects
    _show_chrome_dry_run_from_tasks(tasks)

def _show_chrome_dry_run_from_tasks(tasks: dict[str, ExtensionTranslationTask]) -> None:
    """Show table of messages that would be translated."""
    from localizerx.parser.extension_model import KNOWN_CWS_KEYS

    table = Table(title="Messages to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Length", style="green")

    for locale, task in tasks.items():
        for msg in task.messages[:20]:
            msg_type = "CWS" if msg.key in KNOWN_CWS_KEYS else "msg"
            table.add_row(locale, msg.key[:40], msg_type, str(msg.char_count))

        if len(task.messages) > 20:
            table.add_row(locale, f"... ({len(task.messages) - 20} more)", "", "")

    console.print(table)
