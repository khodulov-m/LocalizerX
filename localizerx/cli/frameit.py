"""Fastlane Frameit commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console, create_progress
from localizerx.config import get_cache_dir, load_config
from localizerx.io.frameit import (
    detect_frameit_path,
    ensure_framefile,
    write_frameit_locale,
)
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.utils.locale import get_fastlane_locale_name, parse_fastlane_locale_list
from localizerx.adapters.repository import FrameitCatalogRepository
from localizerx.core.use_cases.translate_frameit import (
    FrameitTranslationPreview,
    FrameitTranslationTask,
    TranslateFrameitRequest,
    TranslateFrameitUseCase,
)

frameit_cmd = typer.Typer(help="Fastlane Frameit screenshot text translation")


@frameit_cmd.callback(invoke_without_command=True)
def frameit(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Path to fastlane screenshots directory"),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to", "-t", help="Target fastlane locales (comma-separated, e.g., 'fr-FR,de-DE')"
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option("--src", "-s", help="Source locale"),
    ] = "en-US",
    prepare: Annotated[
        bool,
        typer.Option(
            "--prepare", help="Prepare frameit structure (Framefile.json and templates) and exit"
        ),
    ] = False,
    custom_prompt: Annotated[
        Optional[str],
        typer.Option("--custom-prompt", help="Custom instructions for translation"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Gemini model to use"),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing translations"),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option("--preview", "-p", help="Preview translations before applying"),
    ] = False,
) -> None:
    """Translate frameit title.strings and keyword.strings to target locales."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_config()
    base_path = path if path else detect_frameit_path()
    repository = FrameitCatalogRepository()

    if prepare:
        ensure_framefile(base_path)
        catalog = repository.read(base_path, source_locale=src)
        source_metadata = catalog.get_source_metadata()

        if not source_metadata or (
            not source_metadata.title_strings and not source_metadata.keyword_strings
        ):
            source_metadata = catalog.get_or_create_locale(src)
            source_metadata.set_title("screenshot_1", "Your Catchy Title")
            source_metadata.set_keyword("screenshot_1", "KEYWORD")
            write_frameit_locale(base_path, source_metadata)
            console.print(f"[green]Created template in {base_path / src}[/green]")

        console.print(f"[green]Frameit structure prepared in {base_path}[/green]")
        raise typer.Exit(0)

    target_locales = parse_fastlane_locale_list(to) if to else config.default_targets
    if not target_locales:
        console.print("[red]Error:[/red] No target locales specified.")
        raise typer.Exit(1)

    # Initialize Framefile if needed
    ensure_framefile(base_path)

    # Read catalog early to validate source
    try:
        catalog = repository.read(base_path, source_locale=src)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    source_metadata = catalog.get_source_metadata()

    # If source is missing or empty, create a template
    if not source_metadata or (
        not source_metadata.title_strings and not source_metadata.keyword_strings
    ):
        console.print(
            f"[yellow]Source locale '{src}' not found or empty. Creating template...[/yellow]"
        )
        source_metadata = catalog.get_or_create_locale(src)
        source_metadata.set_title("App-Screenshot-1", "Amazing Feature")
        source_metadata.set_keyword("App-Screenshot-1", "Keyword")
        write_frameit_locale(base_path, source_metadata)
        console.print(f"[green]Created template in {base_path / src}[/green]")
        console.print("Please edit the template files and run again.")
        raise typer.Exit(0)

    console.print(f"[bold]Frameit path:[/bold] {base_path}")
    console.print(f"[bold]Source locale:[/bold] {src}")
    target_display = ", ".join(f"{get_fastlane_locale_name(loc)} ({loc})" for loc in target_locales)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Callbacks
    def on_task_summary(tasks: dict[str, FrameitTranslationTask]):
        for locale, task in tasks.items():
            parts = []
            if task.titles:
                parts.append(f"{len(task.titles)} title(s)")
            if task.keywords:
                parts.append(f"{len(task.keywords)} keyword(s)")
            console.print(f"  {get_fastlane_locale_name(locale)}: {', '.join(parts)}")

    progress = None
    
    def on_translation_start(locale: str, total: int):
        nonlocal progress
        if not progress:
            progress = create_progress()
            progress.start()
        console.print(f"  Translating to {get_fastlane_locale_name(locale)}...")
        return progress.add_task(f"    {locale}", total=total)

    def on_translation_progress(task_id, advance_by):
        if progress:
            progress.advance(task_id, advance_by)

    def on_preview_request(items: list[FrameitTranslationPreview]) -> bool:
        if progress:
            progress.stop()
        table = Table(title="Translation Preview")
        table.add_column("Locale", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Key", style="white")
        table.add_column("Translation", style="green")
        
        for i, item in enumerate(items):
            if i >= 20:
                break
            table.add_row(item.locale, item.type, item.key, item.translation)
            
        if len(items) > 20:
            table.add_row("...", "", "", f"({len(items) - 20} more)")
            
        console.print(table)
        apply = typer.confirm("Apply these translations?")
        if not apply:
            console.print("  [yellow]Cancelled[/yellow]")
        return apply

    async def _run_async():
        cache_dir = get_cache_dir(config)
        actual_model = model or config.frameit.model

        async with GeminiTranslator(
            model=actual_model,
            max_retries=config.frameit.max_retries,
            cache_dir=cache_dir,
            custom_instructions=custom_prompt,
        ) as translator:
            
            use_case = TranslateFrameitUseCase(repository=repository, translator=translator)
            request = TranslateFrameitRequest(
                path=base_path,
                source_locale=src,
                target_locales=target_locales,
                dry_run=False,
                preview=preview,
                overwrite=overwrite,
                custom_instructions=custom_prompt,
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
                    console.print(f"\n[green]Saved translations to {base_path}[/green]")
                elif not result.tasks:
                     console.print("[green]All strings already translated[/green]")
                     
            finally:
                if progress:
                    progress.stop()

    asyncio.run(_run_async())
