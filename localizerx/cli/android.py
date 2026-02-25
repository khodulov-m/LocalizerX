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
        backup=backup,
        batch_size=batch_size,
        model=model,
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

    thinking_level = getattr(config.translator, "thinking_level", "0")
    thinking_config = {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None

    async with GeminiTranslator(
        thinking_config=thinking_config,
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

            with create_progress() as progress:
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
