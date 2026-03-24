"""Frontend i18n JSON file commands."""

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
from localizerx.adapters.repository import I18nCatalogRepository
from localizerx.core.use_cases.translate_i18n import (
    I18nTranslationPreview,
    I18nTranslationTask,
    TranslateI18nRequest,
    TranslateI18nUseCase,
)
from localizerx.utils.locale import (
    get_language_name,
    parse_language_list,
)


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
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Create backup before writing changes",
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
    update_index: Annotated[
        bool,
        typer.Option(
            "--index/--no-index",
            help="Automatically update index.ts with locale imports",
        ),
    ] = True,
    remove: Annotated[
        Optional[str],
        typer.Option(
            "--remove",
            "-r",
            help="Locales to remove (comma-separated, e.g., 'fr,de').",
        ),
    ] = None,
) -> None:
    """Translate frontend i18n JSON files to target locales."""
    if not to and not remove:
        console.print("[red]Error:[/red] --to or --remove option is required")
        raise typer.Exit(1)

    _run_i18n_translate(
        path=path,
        to=to,
        src=src,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=backup,
        batch_size=batch_size,
        model=model,
        update_index=update_index,
        remove=remove,
    )


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

    index_ts = path / "index.ts"
    index_status = "[green]Present[/green]" if index_ts.exists() else "[yellow]Missing[/yellow]"

    console.print(f"[bold]Locales Directory:[/bold] {path}")
    console.print(f"[bold]Source Locale:[/bold] {catalog.source_locale}")
    console.print(f"[bold]Total Locales:[/bold] {catalog.locale_count}")
    console.print(f"[bold]index.ts Status:[/bold] {index_status}")
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
    update_index: bool = True,
    remove: str | None = None,
) -> None:
    """Core i18n translation logic."""
    from localizerx.io.i18n import detect_i18n_path

    config = load_config()

    target_locales = parse_language_list(to) if to else []
    remove_locales = parse_language_list(remove) if remove else []

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

    repository = I18nCatalogRepository()
    
    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.i18n.batch_size
    actual_model = model or config.i18n.model
    
    thinking_level = getattr(config.i18n, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    console.print(f"[bold]Locales Directory:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_language_name(src)} ({src})")
    if target_locales:
        target_display = ", ".join(f"{get_language_name(loc)} ({loc})" for loc in target_locales)
        console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Callbacks
    def on_remove(locales: list[str]):
        status = "Would remove" if dry_run else "Removed"
        console.print(
            f"[yellow]{status} {len(locales)} locale(s):[/yellow] "
            f"{', '.join(locales)}"
        )

    def on_task_summary(tasks: dict[str, I18nTranslationTask]):
        for locale, task in tasks.items():
            console.print(f"  {get_language_name(locale)}: {len(task.messages)} message(s) to translate")
            
        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            _show_i18n_dry_run_from_tasks(tasks)

    progress = None
    
    def on_translation_start(locale: str, total: int):
        nonlocal progress
        if not progress:
            progress = create_progress()
            progress.start()
        console.print(f"  Translating to {get_language_name(locale)}...")
        return progress.add_task(f"    {locale}", total=total)

    def on_translation_progress(task_id, advance_by):
        if progress:
            progress.advance(task_id, advance_by)

    def on_preview_request(items: list[I18nTranslationPreview]) -> bool:
        if progress:
            progress.stop()
        table = Table(title="Translation Preview")
        table.add_column("Locale", style="cyan")
        table.add_column("Key", style="white")
        table.add_column("Translation", style="green")
        
        for i, item in enumerate(items):
            if i >= 20:
                break
            preview_value = item.translation[:60] + "..." if len(item.translation) > 60 else item.translation
            table.add_row(item.locale, item.key[:30], preview_value)
            
        if len(items) > 20:
            table.add_row("...", "", f"({len(items) - 20} more)")
            
        console.print(table)
        apply = typer.confirm("Apply these translations?")
        if not apply:
            console.print("  [yellow]Cancelled[/yellow]")
        return apply

    async def _run_async():
        async with GeminiTranslator(
            thinking_config=thinking_config,
            model=actual_model,
            batch_size=actual_batch_size,
            max_retries=config.i18n.max_retries,
            cache_dir=cache_dir,
        ) as translator:
            
            use_case = TranslateI18nUseCase(repository=repository, translator=translator)
            request = TranslateI18nRequest(
                path=path,
                source_locale=src,
                target_locales=target_locales,
                remove_locales=remove_locales,
                dry_run=dry_run,
                preview=preview,
                overwrite=overwrite,
                backup=backup,
                update_index=update_index,
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
                    if update_index:
                         console.print(f"[green]Updated {path}/index.ts[/green]")
                elif not result.tasks and not result.removed_locales and not dry_run:
                     console.print("[green]All messages already translated[/green]")
                     if update_index:
                          console.print(f"[green]Updated {path}/index.ts[/green]")
                     
            finally:
                if progress:
                    progress.stop()

    asyncio.run(_run_async())


def _show_i18n_dry_run_from_tasks(tasks: dict[str, I18nTranslationTask]) -> None:
    """Show table of messages that would be translated."""
    table = Table(title="Messages to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Value", style="green")

    for locale, task in tasks.items():
        for msg in task.messages[:20]:
            display_value = msg.value[:50] + "..." if len(msg.value) > 50 else msg.value
            table.add_row(locale, msg.key[:40], display_value)

        if len(task.messages) > 20:
            table.add_row(locale, f"... ({len(task.messages) - 20} more)", "")

    console.print(table)
