"""xcstrings translate and info commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console, create_progress
from localizerx.config import (
    GEMINI_MODELS,
    Config,
    get_cache_dir,
    load_config,
)
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import Translation
from localizerx.translator.base import TranslationRequest
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.utils.context import extract_app_context_string
from localizerx.utils.locale import (
    get_language_name,
    parse_language_list,
    validate_language_code,
)
from localizerx.adapters.repository import XCStringsRepository
from localizerx.core.use_cases.translate_xcstrings import (
    TranslateCatalogRequest,
    TranslateCatalogUseCase,
    TranslationPreview,
    TranslationTask,
)


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
            help=(
                "Target languages (comma-separated, e.g., 'fr,es,de')."
                " Omit to use defaults from config."
            ),
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
    custom_prompt: Annotated[
        Optional[str],
        typer.Option(
            "--custom-prompt",
            "--instructions",
            help="Custom instructions for translation (e.g., 'Do not translate proper names')",
        ),
    ] = None,
    no_app_context: Annotated[
        bool,
        typer.Option(
            "--no-app-context",
            help=(
                "Disable automatic app context extraction (name, subtitle, description) "
                "from metadata or project files."
            ),
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Automatically add translations for new strings and delete stale strings.",
        ),
    ] = False,
    mark_empty: Annotated[
        bool,
        typer.Option(
            "--mark-empty",
            help="Mark empty or whitespace strings as translated for all target languages.",
        ),
    ] = False,
    remove: Annotated[
        Optional[str],
        typer.Option(
            "--remove",
            "-r",
            help="Languages to remove (comma-separated, e.g., 'fr,de').",
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
        temperature=temperature,
        custom_prompt=custom_prompt,
        no_app_context=no_app_context,
        refresh=refresh,
        mark_empty=mark_empty,
        remove=remove,
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
    temperature: float | None,
    custom_prompt: str | None,
    no_app_context: bool,
    refresh: bool,
    mark_empty: bool,
    remove: str | None = None,
) -> None:
    """Core translation logic."""
    # Load configuration
    config = load_config(config_path)

    # Parse target languages (use config defaults if not specified)
    target_langs = []
    if to:
        target_langs = parse_language_list(to)
    elif not remove:
        target_langs = config.default_targets.copy()
        if target_langs:
            console.print(
                f"[dim]Using default targets from config ({len(target_langs)} languages)[/dim]"
            )

    # Parse languages to remove
    remove_langs = []
    if remove:
        remove_langs = parse_language_list(remove)

    if not target_langs and not remove_langs:
        console.print("[red]Error:[/red] No target languages or languages to remove specified")
        console.print("Use --to or --remove option")
        raise typer.Exit(1)

    # Validate languages
    invalid_langs = [
        lang for lang in target_langs + remove_langs if not validate_language_code(lang)
    ]
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
    if target_langs:
        target_display = ", ".join(f"{get_language_name(lang)} ({lang})" for lang in target_langs)
        console.print(f"Targets: {target_display}")
    if remove_langs:
        remove_display = ", ".join(f"{get_language_name(lang)} ({lang})" for lang in remove_langs)
        console.print(f"Remove: [red]{remove_display}[/red]")
    console.print()

    # Process each file
    for file_path in files:
        _process_file(
            file_path=file_path,
            source_lang=src,
            target_langs=target_langs,
            remove_langs=remove_langs,
            config=config,
            dry_run=dry_run,
            preview=preview,
            overwrite=overwrite,
            backup=backup,
            batch_size=batch_size,
            model=model,
            temperature=temperature,
            custom_prompt=custom_prompt,
            no_app_context=no_app_context,
            refresh=refresh,
            mark_empty=mark_empty,
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
    remove_langs: list[str],
    config: Config,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    batch_size: int | None,
    model: str | None,
    temperature: float | None,
    custom_prompt: str | None,
    no_app_context: bool,
    refresh: bool,
    mark_empty: bool,
) -> None:
    """Process a single xcstrings file."""
    console.print(f"[bold]Processing:[/bold] {file_path}")

    repository = XCStringsRepository()

    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.translate.batch_size
    actual_model = model or config.translate.model
    actual_temperature = temperature if temperature is not None else config.translate.temperature
    actual_custom_instructions = custom_prompt or config.translate.custom_instructions

    app_context = None
    if config.translate.use_app_context and not no_app_context:
        app_context = extract_app_context_string(source_lang)
        if app_context:
            console.print("[dim]Using extracted app context for translations[/dim]")

    thinking_level = getattr(config.translate, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    # Callbacks for UI
    def on_read(total: int):
        console.print(f"  Found {total} string(s)")

    def on_task_summary(tasks: list[TranslationTask]):
        for task in tasks:
            console.print(f"  {get_language_name(task.lang)}: {len(task.requests)} string(s) to translate")
        if dry_run:
            console.print("  [yellow]Dry run - no changes made[/yellow]")
            _show_dry_run_table(tasks)

    progress = None
    progress_tasks = {}

    def on_translation_start(lang: str, total: int):
        nonlocal progress
        if not progress:
            progress = create_progress()
            progress.start()
        console.print(f"  Translating to {get_language_name(lang)}...")
        task_id = progress.add_task(f"    {lang}", total=total)
        progress_tasks[lang] = task_id
        return task_id

    def on_translation_progress(task_id, advance_by):
        if progress:
            progress.advance(task_id, advance_by)

    def on_preview_request(items: list[TranslationPreview]) -> bool:
        if progress:
            progress.stop()
        table = Table(title="Translation Preview")
        table.add_column("Key", style="cyan")
        table.add_column("Source", style="white")
        table.add_column("Language", style="yellow")
        table.add_column("Translation", style="green")
        
        for i, item in enumerate(items):
            if i >= 30:
                break
            source_display = item.source[:30] + "..." if len(item.source) > 30 else item.source
            table.add_row(item.key[:25], source_display, item.lang, item.translation)
            
        if len(items) > 30:
            table.add_row("...", "", "", f"({len(items) - 30} more)")
            
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
            max_retries=config.translate.max_retries,
            cache_dir=cache_dir,
            temperature=actual_temperature,
            custom_instructions=actual_custom_instructions,
            app_context=app_context,
        ) as translator:
            
            use_case = TranslateCatalogUseCase(repository=repository, translator=translator)
            request = TranslateCatalogRequest(
                file_path=file_path,
                source_lang=source_lang,
                target_langs=target_langs,
                remove_langs=remove_langs,
                dry_run=dry_run,
                preview=preview,
                overwrite=overwrite,
                backup=backup,
                mark_empty=mark_empty,
                refresh=refresh,
            )
            
            try:
                result = await use_case.execute(
                    request=request,
                    on_read=on_read,
                    on_task_summary=on_task_summary,
                    on_translation_start=on_translation_start,
                    on_translation_progress=on_translation_progress,
                    on_preview_request=on_preview_request,
                )
            finally:
                if progress:
                    progress.stop()
            
            # Print legacy summary lines
            if result.marked_empty_count > 0:
                msg = "Would mark" if dry_run else "Marked"
                console.print(f"  [green]{msg} {result.marked_empty_count} empty/whitespace string(s) as translated[/green]")
            if result.removed_languages:
                status = "Would remove" if dry_run else "Removed"
                console.print(f"  [yellow]{status} {len(result.removed_languages)} language(s)[/yellow]")
            if result.stale_keys_removed > 0:
                status = "Would remove" if dry_run else "Removed"
                console.print(f"  [yellow]{status} {result.stale_keys_removed} stale string(s)[/yellow]")

            if not result.tasks:
                if result.saved:
                    console.print(f"  [green]Saved {file_path}[/green]")
                elif not dry_run and not result.removed_languages and result.marked_empty_count == 0 and result.stale_keys_removed == 0:
                    console.print("  [green]All strings already translated[/green]")
            elif result.saved:
                console.print(f"  [green]Saved {file_path}[/green]")

    asyncio.run(_run_async())


def _show_dry_run_table(tasks: list[TranslationTask]) -> None:
    """Show table of strings that would be translated."""
    table = Table(title="Strings to Translate")
    table.add_column("Key", style="cyan")
    table.add_column("Source Text", style="white")
    table.add_column("Languages", style="green")

    # Collect all unique entries
    entries: dict[str, tuple[str, set[str]]] = {}
    for task in tasks:
        for req in task.requests:
            if req.key not in entries:
                entries[req.key] = (req.text, set())
            entries[req.key][1].add(task.lang)

    for key, (text, langs) in list(entries.items())[:20]:
        display_text = text[:50] + "..." if len(text) > 50 else text
        table.add_row(key[:40], display_text, ", ".join(sorted(langs)))

    if len(entries) > 20:
        table.add_row("...", f"({len(entries) - 20} more)", "")

    console.print(table)


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
