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
    from localizerx.io.i18n import (
        delete_i18n_locale,
        detect_i18n_path,
        read_i18n,
        update_index_ts,
    )

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

            if delete_i18n_locale(path, loc):
                actually_removed.append(loc)

        if actually_removed:
            status = "Would remove" if dry_run else "Removed"
            console.print(
                f"[yellow]{status} {len(actually_removed)} locale(s):[/yellow] "
                f"{', '.join(actually_removed)}"
            )

        if not target_locales:
            if dry_run:
                console.print("\n[yellow]Dry run - no changes made[/yellow]")
                return
            if actually_removed and update_index:
                # Update index.ts after removal
                catalog = read_i18n(path, source_locale=src)
                update_index_ts(path, catalog)
                console.print(f"[green]Updated {path}/index.ts[/green]")
            return

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
    if target_locales:
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
        if update_index:
            update_index_ts(path, catalog)
            console.print(f"[green]Updated {path}/index.ts[/green]")
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
            update_index=update_index,
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
    update_index: bool = True,
) -> None:
    """Perform i18n translations and update catalog."""
    from localizerx.io.i18n import write_i18n

    cache_dir = get_cache_dir(config)
    actual_batch_size = batch_size or config.i18n.batch_size
    actual_model = model or config.i18n.model

    thinking_level = getattr(config.i18n, "thinking_level", "0")
    thinking_config = (
        {"thinkingLevel": thinking_level} if thinking_level not in ("0", "none", "") else None
    )

    async with GeminiTranslator(
        thinking_config=thinking_config,
        model=actual_model,
        batch_size=actual_batch_size,
        max_retries=config.i18n.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        all_translations: dict[str, dict[str, str]] = {}  # locale -> {key: translated}

        for target_locale, messages in translation_tasks.items():
            console.print(f"  Translating to {get_language_name(target_locale)}...")
            all_translations[target_locale] = {}

            requests = [TranslationRequest(key=m.key, text=m.value) for m in messages]

            with create_progress() as progress:
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
            update_index=update_index,
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
