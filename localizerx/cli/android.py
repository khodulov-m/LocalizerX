"""Android strings.xml commands."""

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
from localizerx.adapters.repository import AndroidCatalogRepository
from localizerx.core.use_cases.translate_android import (
    AndroidTranslationPreview,
    AndroidTranslationTask,
    TranslateAndroidRequest,
    TranslateAndroidUseCase,
)
from localizerx.utils.locale import (
    get_language_name,
    parse_language_list,
)


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
    remove: Annotated[
        Optional[str],
        typer.Option(
            "--remove",
            "-r",
            help="Locales to remove (comma-separated, e.g., 'fr,de').",
        ),
    ] = None,
) -> None:
    """Translate Android strings.xml files to target locales."""
    if not to and not remove:
        console.print("[red]Error:[/red] --to or --remove option is required")
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
        backup=backup,
        batch_size=batch_size,
        model=model,
        remove=remove,
    )


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
    remove: str | None = None,
) -> None:
    """Core Android translation logic."""
    from localizerx.io.android import detect_android_path

    config = load_config()

    target_locales = parse_language_list(to) if to else []
    remove_locales = parse_language_list(remove) if remove else []

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

    repository = AndroidCatalogRepository()
    
    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.android.batch_size
    actual_model = model or config.android.model
    
    thinking_level = getattr(config.android, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    console.print(f"[bold]Resource Directory:[/bold] {path}")
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

    def on_task_summary(tasks: dict[str, AndroidTranslationTask]):
        for locale, task in tasks.items():
            parts = []
            if task.strings:
                parts.append(f"{len(task.strings)} string(s)")
            if task.arrays:
                parts.append(f"{len(task.arrays)} array(s)")
            if task.plurals:
                parts.append(f"{len(task.plurals)} plural(s)")
            console.print(f"  {get_language_name(locale)}: {', '.join(parts)}")
            
        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            _show_android_dry_run_from_tasks(tasks)

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

    def on_preview_request(items: list[AndroidTranslationPreview]) -> bool:
        if progress:
            progress.stop()
        table = Table(title="Translation Preview")
        table.add_column("Locale", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Translation", style="green")
        
        for i, item in enumerate(items):
            if i >= 20:
                break
            preview_value = item.translation[:60] + "..." if len(item.translation) > 60 else item.translation
            table.add_row(item.locale, item.name, preview_value)
            
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
            max_retries=config.android.max_retries,
            cache_dir=cache_dir,
        ) as translator:
            
            use_case = TranslateAndroidUseCase(repository=repository, translator=translator)
            request = TranslateAndroidRequest(
                path=path,
                source_locale=src,
                target_locales=target_locales,
                remove_locales=remove_locales,
                include_arrays=include_arrays,
                include_plurals=include_plurals,
                dry_run=dry_run,
                preview=preview,
                overwrite=overwrite,
                backup=backup,
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
                     console.print("[green]All strings already translated[/green]")
                     
            finally:
                if progress:
                    progress.stop()

    asyncio.run(_run_async())


def _show_android_dry_run_from_tasks(tasks: dict[str, AndroidTranslationTask]) -> None:
    """Show table of strings that would be translated."""
    table = Table(title="Strings to Translate")
    table.add_column("Locale", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Name", style="white")
    table.add_column("Value", style="green")

    for locale, task in tasks.items():
        for s in task.strings[:15]:
            display = s.value[:40] + "..." if len(s.value) > 40 else s.value
            table.add_row(locale, "string", s.name, display)
        for a in task.arrays[:5]:
            table.add_row(locale, "array", a.name, f"{len(a.items)} items")
        for p in task.plurals[:5]:
            table.add_row(locale, "plural", p.name, f"{len(p.items)} forms")

        total = len(task.strings) + len(task.arrays) + len(task.plurals)
        shown = (
            min(len(task.strings), 15)
            + min(len(task.arrays), 5)
            + min(len(task.plurals), 5)
        )
        if total > shown:
            table.add_row(locale, "", f"... ({total - shown} more)", "")

    console.print(table)
