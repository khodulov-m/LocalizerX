"""delete command for removing languages from xcstrings files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import StringCatalog
from localizerx.utils.locale import get_language_name, parse_language_list


def _determine_languages_to_delete(
    catalog: StringCatalog,
    languages: str | None,
    delete_all: bool,
    keep: bool,
) -> set[str]:
    """Determine which languages to delete based on mode.

    Args:
        catalog: The string catalog
        languages: Comma-separated list of language codes
        delete_all: Whether to delete all languages except source
        keep: Whether to keep specified languages (delete all others)

    Returns:
        Set of language codes to delete
    """
    if delete_all and not keep:
        # Mode 1: Delete all except source
        existing_langs = set()
        for entry in catalog.strings.values():
            existing_langs.update(entry.translations.keys())
        return existing_langs - {catalog.source_language}

    if languages and not keep:
        # Mode 2: Delete specific languages
        langs_to_delete = set(parse_language_list(languages))

        # Protect source language
        if catalog.source_language in langs_to_delete:
            langs_to_delete.discard(catalog.source_language)

        return langs_to_delete

    if keep and languages:
        # Mode 3: Keep specified languages, delete all others
        existing_langs = set()
        for entry in catalog.strings.values():
            existing_langs.update(entry.translations.keys())

        keep_langs = set(parse_language_list(languages))
        keep_langs.add(catalog.source_language)  # Always keep source

        return existing_langs - keep_langs

    return set()


def _delete_languages_from_catalog(
    catalog: StringCatalog,
    languages: set[str],
) -> dict[str, int]:
    """Delete languages from catalog.

    Args:
        catalog: The string catalog
        languages: Set of language codes to delete

    Returns:
        Dict mapping language code to count of deleted translations
    """
    deleted_counts = {lang: 0 for lang in languages}

    # Delete from entries
    for entry in catalog.strings.values():
        for lang in languages:
            if lang in entry.translations:
                del entry.translations[lang]
                deleted_counts[lang] += 1

    # Delete from raw_data for lossless write
    raw_data = catalog.get_raw_data()
    if raw_data and "strings" in raw_data:
        for key, entry_data in raw_data["strings"].items():
            if "localizations" in entry_data:
                locs = entry_data["localizations"]
                for lang in languages:
                    locs.pop(lang, None)

    return deleted_counts


def delete(
    languages: Annotated[
        Optional[str],
        typer.Argument(
            help="Languages to delete (comma-separated, e.g., 'fr,es,de'). Use --all to delete all except source.",
        ),
    ] = None,
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to .xcstrings file or directory (auto-detected if omitted)",
        ),
    ] = None,
    delete_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Delete all languages except source",
        ),
    ] = False,
    keep: Annotated[
        bool,
        typer.Option(
            "--keep",
            help="Keep specified languages, delete all others",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip confirmation prompt",
        ),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Create backup before deleting",
        ),
    ] = False,
) -> None:
    """Delete languages from .xcstrings files.

    Examples:
        localizerx delete fr,es           # Delete French and Spanish
        localizerx delete --all           # Delete all except source
        localizerx delete en,ru --keep    # Keep English and Russian, delete others
    """
    _run_delete(
        languages=languages,
        path=path,
        delete_all=delete_all,
        keep=keep,
        yes=yes,
        backup=backup,
    )


def _run_delete(
    languages: str | None,
    path: Path | None,
    delete_all: bool,
    keep: bool,
    yes: bool,
    backup: bool,
) -> None:
    """Core deletion logic."""
    # Validate arguments BEFORE any reassignment
    if not delete_all and not languages:
        console.print("[red]Error:[/red] Specify languages to delete or use --all")
        console.print("Examples:")
        console.print("  localizerx delete fr,es")
        console.print("  localizerx delete --all")
        console.print("  localizerx delete en,ru --keep")
        raise typer.Exit(1)

    # Check for contradictory --all with specific languages
    # But allow if languages looks like a path (will be reassigned below)
    if delete_all and languages and not path:
        # Check if languages looks like actual language codes (not a path)
        potential_path = Path(languages)
        is_path_like = potential_path.exists() or languages.endswith('.xcstrings') or '/' in languages
        if not is_path_like:
            console.print("[red]Error:[/red] Cannot use --all with specific languages")
            raise typer.Exit(1)

    if delete_all and keep:
        console.print("[red]Error:[/red] Cannot use --all with --keep")
        raise typer.Exit(1)

    # Handle case where path is passed as first argument with --all
    # (Typer assigns first positional to languages parameter)
    if delete_all and languages and not path:
        # Check if languages looks like a path
        potential_path = Path(languages)
        if potential_path.exists() or languages.endswith('.xcstrings') or '/' in languages:
            path = potential_path
            languages = None

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

    console.print(f"Found {len(files)} .xcstrings file(s)\n")

    # Process each file
    for file_path in files:
        _process_file(
            file_path=file_path,
            languages=languages,
            delete_all=delete_all,
            keep=keep,
            yes=yes,
            backup=backup,
        )


def _find_xcstrings_files(path: Path) -> list[Path]:
    """Find all .xcstrings files in path."""
    if path.is_file():
        if path.suffix == ".xcstrings":
            return [path]
        return []

    return sorted(path.rglob("*.xcstrings"))


def _prompt_file_selection(files: list[Path]) -> list[Path]:
    """Prompt user to select which files to process."""
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

    choice = typer.prompt("Select file(s) to process (number, comma-separated, or 'a' for all)")
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
    languages: str | None,
    delete_all: bool,
    keep: bool,
    yes: bool,
    backup: bool,
) -> None:
    """Process a single xcstrings file."""
    console.print(f"[bold]Processing:[/bold] {file_path}")

    # Read file
    catalog = read_xcstrings(file_path)
    console.print(f"  Source language: {get_language_name(catalog.source_language)} ({catalog.source_language})")
    console.print(f"  Total strings: {len(catalog.strings)}")

    # Determine which languages to delete
    langs_to_delete = _determine_languages_to_delete(
        catalog=catalog,
        languages=languages,
        delete_all=delete_all,
        keep=keep,
    )

    if not langs_to_delete:
        console.print("  [yellow]No languages to delete[/yellow]\n")
        return

    # Show what will be deleted
    _show_deletion_table(catalog, langs_to_delete)

    # Confirm deletion
    if not yes:
        confirm = typer.confirm("\nProceed with deletion?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]\n")
            return

    # Delete languages
    deleted_counts = _delete_languages_from_catalog(catalog, langs_to_delete)

    # Write changes
    write_xcstrings(catalog, file_path, backup=backup)

    # Show summary
    console.print("\n[green]Deletion complete:[/green]")
    for lang in sorted(langs_to_delete):
        count = deleted_counts[lang]
        console.print(f"  {get_language_name(lang)} ({lang}): {count} translation(s) removed")
    console.print()


def _show_deletion_table(catalog: StringCatalog, langs_to_delete: set[str]) -> None:
    """Show a table of languages to be deleted."""
    table = Table(title="Languages to Delete")
    table.add_column("Language", style="cyan")
    table.add_column("Code", style="white")
    table.add_column("Translations", style="yellow", justify="right")

    # Count translations per language
    lang_counts = {lang: 0 for lang in langs_to_delete}
    for entry in catalog.strings.values():
        for lang in langs_to_delete:
            if lang in entry.translations:
                lang_counts[lang] += 1

    # Add rows sorted by language name
    for lang in sorted(langs_to_delete, key=lambda l: get_language_name(l)):
        table.add_row(
            get_language_name(lang),
            lang,
            str(lang_counts[lang]),
        )

    console.print()
    console.print(table)
