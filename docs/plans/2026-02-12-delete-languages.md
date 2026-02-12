# Delete Languages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Реализовать команду `localizerx delete` для удаления языков из `.xcstrings` файлов с тремя режимами работы.

**Architecture:** Новый CLI модуль `localizerx/cli/delete.py` с командой Typer, использующий существующие IO функции для чтения/записи xcstrings файлов. Поддержка трех режимов: удаление всех языков (`--all`), удаление указанных языков (позиционный аргумент), и удаление всех кроме указанных (`--keep`).

**Tech Stack:** Python 3.9+, Typer (CLI), Rich (formatting), pytest (testing)

---

## Task 1: Создать тесты для удаления указанных языков

**Files:**
- Create: `tests/test_delete.py`

**Step 1: Написать failing test для удаления указанных языков**

```python
"""Tests for delete command."""

import json
import tempfile
from pathlib import Path

import pytest

from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import Entry, StringCatalog, Translation


@pytest.fixture
def catalog_with_multiple_languages():
    """Create a catalog with translations in multiple languages."""
    catalog = StringCatalog(
        source_language="en",
        strings={
            "hello": Entry(
                key="hello",
                source_text="Hello",
                translations={
                    "fr": Translation(value="Bonjour"),
                    "de": Translation(value="Hallo"),
                    "es": Translation(value="Hola"),
                    "ru": Translation(value="Привет"),
                }
            ),
            "goodbye": Entry(
                key="goodbye",
                source_text="Goodbye",
                translations={
                    "fr": Translation(value="Au revoir"),
                    "de": Translation(value="Auf Wiedersehen"),
                    "es": Translation(value="Adiós"),
                    "ru": Translation(value="До свидания"),
                }
            ),
        }
    )
    # Set raw data to simulate file read
    catalog.set_raw_data({
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "hello": {
                "localizations": {
                    "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                    "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                    "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                    "es": {"stringUnit": {"state": "translated", "value": "Hola"}},
                    "ru": {"stringUnit": {"state": "translated", "value": "Привет"}},
                }
            },
            "goodbye": {
                "localizations": {
                    "en": {"stringUnit": {"state": "translated", "value": "Goodbye"}},
                    "fr": {"stringUnit": {"state": "translated", "value": "Au revoir"}},
                    "de": {"stringUnit": {"state": "translated", "value": "Auf Wiedersehen"}},
                    "es": {"stringUnit": {"state": "translated", "value": "Adiós"}},
                    "ru": {"stringUnit": {"state": "translated", "value": "До свидания"}},
                }
            }
        }
    })
    return catalog


class TestDetermineLanguagesToDelete:
    def test_delete_specific_languages(self, catalog_with_multiple_languages):
        """Test determining languages to delete for specific mode."""
        from localizerx.cli.delete import _determine_languages_to_delete

        # Delete fr and de
        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages="fr,de",
            delete_all=False,
            keep=False,
        )

        assert langs_to_delete == {"fr", "de"}
        assert "en" not in langs_to_delete  # Source protected
        assert "es" not in langs_to_delete
        assert "ru" not in langs_to_delete
```

**Step 2: Запустить тест для проверки, что он падает**

```bash
pytest tests/test_delete.py::TestDetermineLanguagesToDelete::test_delete_specific_languages -v
```

Expected: `ModuleNotFoundError: No module named 'localizerx.cli.delete'`

**Step 3: Создать минимальную реализацию `_determine_languages_to_delete`**

Create: `localizerx/cli/delete.py`

```python
"""delete command for removing languages from xcstrings files."""

from __future__ import annotations

from localizerx.parser.model import StringCatalog
from localizerx.utils.locale import parse_language_list


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
```

**Step 4: Запустить тест для проверки, что он проходит**

```bash
pytest tests/test_delete.py::TestDetermineLanguagesToDelete::test_delete_specific_languages -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_delete.py localizerx/cli/delete.py
git commit -m "feat(delete): add _determine_languages_to_delete with test for specific mode"
```

---

## Task 2: Добавить тесты для режимов --all и --keep

**Files:**
- Modify: `tests/test_delete.py`

**Step 1: Написать failing tests для режимов --all и --keep**

Add to `tests/test_delete.py`:

```python
class TestDetermineLanguagesToDelete:
    # ... existing test_delete_specific_languages ...

    def test_delete_all_languages(self, catalog_with_multiple_languages):
        """Test deleting all languages except source."""
        from localizerx.cli.delete import _determine_languages_to_delete

        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages=None,
            delete_all=True,
            keep=False,
        )

        assert langs_to_delete == {"fr", "de", "es", "ru"}
        assert "en" not in langs_to_delete  # Source protected

    def test_delete_with_keep(self, catalog_with_multiple_languages):
        """Test keeping specific languages, deleting all others."""
        from localizerx.cli.delete import _determine_languages_to_delete

        # Keep only ru and fr, delete de and es
        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages="ru,fr",
            delete_all=False,
            keep=True,
        )

        assert langs_to_delete == {"de", "es"}
        assert "en" not in langs_to_delete  # Source protected
        assert "ru" not in langs_to_delete  # Explicitly kept
        assert "fr" not in langs_to_delete  # Explicitly kept

    def test_protect_source_language(self, catalog_with_multiple_languages):
        """Test that source language is protected from deletion."""
        from localizerx.cli.delete import _determine_languages_to_delete

        # Try to delete source language
        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages="en,fr",
            delete_all=False,
            keep=False,
        )

        assert "en" not in langs_to_delete
        assert "fr" in langs_to_delete
```

**Step 2: Запустить тесты**

```bash
pytest tests/test_delete.py::TestDetermineLanguagesToDelete -v
```

Expected: All tests PASS (функция уже реализована в Task 1)

**Step 3: Commit**

```bash
git add tests/test_delete.py
git commit -m "test(delete): add tests for --all and --keep modes"
```

---

## Task 3: Реализовать функцию удаления языков из каталога

**Files:**
- Modify: `tests/test_delete.py`
- Modify: `localizerx/cli/delete.py`

**Step 1: Написать failing test для удаления языков из каталога**

Add to `tests/test_delete.py`:

```python
class TestDeleteLanguagesFromCatalog:
    def test_delete_languages_from_entries(self, catalog_with_multiple_languages):
        """Test deleting languages from catalog entries."""
        from localizerx.cli.delete import _delete_languages_from_catalog

        langs_to_delete = {"fr", "de"}
        deleted_counts = _delete_languages_from_catalog(
            catalog_with_multiple_languages,
            langs_to_delete
        )

        # Check counts
        assert deleted_counts == {"fr": 2, "de": 2}  # 2 strings each

        # Check that languages were removed
        for entry in catalog_with_multiple_languages.strings.values():
            assert "fr" not in entry.translations
            assert "de" not in entry.translations
            assert "es" in entry.translations  # Not deleted
            assert "ru" in entry.translations  # Not deleted

    def test_delete_languages_from_raw_data(self, catalog_with_multiple_languages):
        """Test deleting languages from raw_data for lossless write."""
        from localizerx.cli.delete import _delete_languages_from_catalog

        langs_to_delete = {"fr", "de"}
        _delete_languages_from_catalog(catalog_with_multiple_languages, langs_to_delete)

        # Check raw_data
        raw_data = catalog_with_multiple_languages.get_raw_data()
        assert raw_data is not None

        for key, entry_data in raw_data["strings"].items():
            locs = entry_data["localizations"]
            assert "fr" not in locs
            assert "de" not in locs
            assert "es" in locs
            assert "ru" in locs
```

**Step 2: Запустить тесты**

```bash
pytest tests/test_delete.py::TestDeleteLanguagesFromCatalog -v
```

Expected: `AttributeError: module 'localizerx.cli.delete' has no attribute '_delete_languages_from_catalog'`

**Step 3: Реализовать `_delete_languages_from_catalog`**

Add to `localizerx/cli/delete.py`:

```python
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
```

**Step 4: Запустить тесты**

```bash
pytest tests/test_delete.py::TestDeleteLanguagesFromCatalog -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_delete.py localizerx/cli/delete.py
git commit -m "feat(delete): implement _delete_languages_from_catalog"
```

---

## Task 4: Реализовать CLI команду delete

**Files:**
- Modify: `localizerx/cli/delete.py`

**Step 1: Реализовать основную команду delete**

Add to `localizerx/cli/delete.py`:

```python
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.utils.locale import get_language_name


def delete(
    languages: Annotated[
        Optional[str],
        typer.Argument(
            help="Comma-separated language codes to delete (e.g., 'fr,de,es')",
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
            "-a",
            help="Delete all languages except source",
        ),
    ] = False,
    keep: Annotated[
        bool,
        typer.Option(
            "--keep",
            "-k",
            help="Keep specified languages, delete all others",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Delete without confirmation",
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
        # Delete all languages except source
        localizerx delete --all

        # Delete specific languages
        localizerx delete fr,de,es

        # Keep only specified languages (delete all others)
        localizerx delete ru,fr --keep
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
    # Validate arguments
    if not delete_all and not languages:
        console.print("[red]Error:[/red] Specify --all or provide language codes")
        raise typer.Exit(1)

    if delete_all and languages and not keep:
        console.print("[red]Error:[/red] Cannot use both --all and specify languages without --keep")
        raise typer.Exit(1)

    if keep and not languages:
        console.print("[red]Error:[/red] --keep requires language codes")
        raise typer.Exit(1)

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
    console.print(f"  Source language: {catalog.source_language}")

    # Determine languages to delete
    langs_to_delete = _determine_languages_to_delete(
        catalog=catalog,
        languages=languages,
        delete_all=delete_all,
        keep=keep,
    )

    if not langs_to_delete:
        console.print("  [yellow]No languages to delete[/yellow]\n")
        return

    # Check if languages exist
    existing_langs = set()
    for entry in catalog.strings.values():
        existing_langs.update(entry.translations.keys())

    non_existent = langs_to_delete - existing_langs
    if non_existent:
        codes = ", ".join(sorted(non_existent))
        console.print(f"  [yellow]Warning:[/yellow] Languages not found: {codes}")
        langs_to_delete = langs_to_delete & existing_langs

    if not langs_to_delete:
        console.print("  [yellow]No languages to delete[/yellow]\n")
        return

    # Collect info about languages
    lang_info = {}
    for lang in langs_to_delete:
        count = sum(1 for entry in catalog.strings.values() if lang in entry.translations)
        lang_info[lang] = count

    # Show table
    _show_deletion_table(lang_info, file_path)

    # Ask confirmation
    if not yes:
        if not typer.confirm(f"\nDelete {len(langs_to_delete)} language(s)?"):
            console.print("  [yellow]Cancelled[/yellow]\n")
            return

    # Delete languages
    deleted_counts = _delete_languages_from_catalog(catalog, langs_to_delete)

    # Write file
    write_xcstrings(catalog, file_path, backup=backup)

    # Show result
    console.print(f"\n[green]✓[/green] Deleted {len(langs_to_delete)} language(s) from {file_path.name}")
    for lang in sorted(langs_to_delete):
        lang_name = get_language_name(lang)
        count = deleted_counts[lang]
        console.print(f"  - {lang_name} ({lang}): {count} string(s)")

    if backup:
        backup_path = file_path.with_suffix(".xcstrings.backup")
        console.print(f"\nBackup saved: {backup_path}")

    console.print()


def _show_deletion_table(lang_info: dict[str, int], file_path: Path) -> None:
    """Show table of languages to be deleted."""
    table = Table(title=f"Languages to delete from {file_path.name}")
    table.add_column("Language", style="cyan")
    table.add_column("Code", style="white")
    table.add_column("Strings", style="yellow")

    for lang in sorted(lang_info.keys()):
        lang_name = get_language_name(lang)
        count = lang_info[lang]
        table.add_row(lang_name, lang, str(count))

    console.print()
    console.print(table)
```

**Step 2: Протестировать команду вручную**

Create test file: `/tmp/test.xcstrings`

```bash
cat > /tmp/test.xcstrings << 'EOF'
{
  "sourceLanguage": "en",
  "version": "1.0",
  "strings": {
    "hello": {
      "localizations": {
        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
        "de": {"stringUnit": {"state": "translated", "value": "Hallo"}}
      }
    }
  }
}
EOF
```

Test the command:

```bash
localizerx delete fr /tmp/test.xcstrings --yes
```

Expected: Successfully deletes French translation

**Step 3: Commit**

```bash
git add localizerx/cli/delete.py
git commit -m "feat(delete): implement CLI command with file selection and confirmation"
```

---

## Task 5: Зарегистрировать команду в CLI app

**Files:**
- Modify: `localizerx/cli/__init__.py`

**Step 1: Добавить команду delete в CLI app**

Add import and registration in `localizerx/cli/__init__.py`:

```python
# After line 29, add:
from localizerx.cli import (  # noqa: E402
    android,
    chrome,
    delete,  # Add this line
    i18n,
    metadata,
    screenshots,
    translate,
)

# After line 249, add:
app.command()(delete.delete)
```

**Step 2: Проверить, что команда зарегистрирована**

```bash
localizerx --help
```

Expected: Должна появиться команда `delete` в списке

**Step 3: Протестировать команду**

```bash
localizerx delete --help
```

Expected: Показывает help для команды delete

**Step 4: Commit**

```bash
git add localizerx/cli/__init__.py
git commit -m "feat(delete): register delete command in CLI app"
```

---

## Task 6: Добавить интеграционные тесты

**Files:**
- Modify: `tests/test_delete.py`

**Step 1: Написать интеграционный тест с файлом**

Add to `tests/test_delete.py`:

```python
class TestDeleteIntegration:
    def test_delete_specific_languages_from_file(self, tmp_path):
        """Test deleting specific languages from a real file."""
        # Create test file
        test_file = tmp_path / "test.xcstrings"
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                        "es": {"stringUnit": {"state": "translated", "value": "Hola"}},
                    }
                },
                "goodbye": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Goodbye"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Au revoir"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Auf Wiedersehen"}},
                        "es": {"stringUnit": {"state": "translated", "value": "Adiós"}},
                    }
                }
            }
        }

        with open(test_file, "w") as f:
            json.dump(data, f, indent=2)

        # Read, delete, write
        from localizerx.cli.delete import _process_file

        _process_file(
            file_path=test_file,
            languages="fr,de",
            delete_all=False,
            keep=False,
            yes=True,
            backup=False,
        )

        # Verify languages were deleted
        catalog = read_xcstrings(test_file)
        for entry in catalog.strings.values():
            assert "fr" not in entry.translations
            assert "de" not in entry.translations
            assert "es" in entry.translations

        # Verify JSON structure preserved
        with open(test_file) as f:
            result = json.load(f)

        assert result["sourceLanguage"] == "en"
        assert result["version"] == "1.0"
        assert "hello" in result["strings"]
        assert "goodbye" in result["strings"]

    def test_delete_all_except_source(self, tmp_path):
        """Test --all mode."""
        test_file = tmp_path / "test.xcstrings"
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                    }
                }
            }
        }

        with open(test_file, "w") as f:
            json.dump(data, f, indent=2)

        from localizerx.cli.delete import _process_file

        _process_file(
            file_path=test_file,
            languages=None,
            delete_all=True,
            keep=False,
            yes=True,
            backup=False,
        )

        # Verify all languages deleted except source
        catalog = read_xcstrings(test_file)
        for entry in catalog.strings.values():
            assert len(entry.translations) == 0

    def test_delete_with_backup(self, tmp_path):
        """Test backup functionality."""
        test_file = tmp_path / "test.xcstrings"
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                    }
                }
            }
        }

        with open(test_file, "w") as f:
            json.dump(data, f, indent=2)

        from localizerx.cli.delete import _process_file

        _process_file(
            file_path=test_file,
            languages="fr",
            delete_all=False,
            keep=False,
            yes=True,
            backup=True,
        )

        # Verify backup was created
        backup_file = test_file.with_suffix(".xcstrings.backup")
        assert backup_file.exists()

        # Verify backup contains original data
        with open(backup_file) as f:
            backup_data = json.load(f)

        assert "fr" in backup_data["strings"]["hello"]["localizations"]
```

**Step 2: Запустить интеграционные тесты**

```bash
pytest tests/test_delete.py::TestDeleteIntegration -v
```

Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_delete.py
git commit -m "test(delete): add integration tests for file operations"
```

---

## Task 7: Запустить все тесты и проверить

**Step 1: Запустить все тесты delete**

```bash
pytest tests/test_delete.py -v
```

Expected: All tests PASS

**Step 2: Запустить весь test suite**

```bash
pytest
```

Expected: All tests PASS

**Step 3: Проверить покрытие кода**

```bash
pytest tests/test_delete.py --cov=localizerx.cli.delete --cov-report=term-missing
```

Expected: Высокое покрытие (>90%)

**Step 4: Commit если нужны правки**

```bash
git add .
git commit -m "test(delete): ensure test coverage"
```

---

## Task 8: Проверить линтинг и форматирование

**Step 1: Запустить ruff**

```bash
ruff check localizerx/cli/delete.py tests/test_delete.py
```

Expected: No errors

**Step 2: Запустить black**

```bash
black localizerx/cli/delete.py tests/test_delete.py --check
```

Expected: All files formatted correctly

**Step 3: Исправить если нужно**

```bash
black localizerx/cli/delete.py tests/test_delete.py
ruff check localizerx/cli/delete.py tests/test_delete.py --fix
```

**Step 4: Commit если были изменения**

```bash
git add localizerx/cli/delete.py tests/test_delete.py
git commit -m "style(delete): fix linting and formatting"
```

---

## Task 9: Обновить CLAUDE.md с информацией о команде

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Добавить информацию о команде delete**

Add to `CLAUDE.md` under "Development Commands":

```markdown
# Run delete command
localizerx delete fr,de --backup
localizerx delete --all --yes
localizerx delete ru --keep
```

Add to "Package Structure":

```markdown
- `localizerx/cli/delete.py` - Delete languages from xcstrings files
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add delete command to CLAUDE.md"
```

---

## Task 10: Финальная проверка и документация

**Step 1: Создать примеры использования**

Test all three modes manually:

```bash
# Create test file
cat > /tmp/demo.xcstrings << 'EOF'
{
  "sourceLanguage": "en",
  "version": "1.0",
  "strings": {
    "test": {
      "localizations": {
        "en": {"stringUnit": {"value": "Test"}},
        "fr": {"stringUnit": {"value": "Test"}},
        "de": {"stringUnit": {"value": "Test"}},
        "es": {"stringUnit": {"value": "Test"}},
        "ru": {"stringUnit": {"value": "Тест"}}
      }
    }
  }
}
EOF

# Test mode 1: delete specific
cp /tmp/demo.xcstrings /tmp/demo1.xcstrings
localizerx delete fr,de /tmp/demo1.xcstrings --yes

# Test mode 2: delete all
cp /tmp/demo.xcstrings /tmp/demo2.xcstrings
localizerx delete --all /tmp/demo2.xcstrings --yes

# Test mode 3: keep specific
cp /tmp/demo.xcstrings /tmp/demo3.xcstrings
localizerx delete ru --keep /tmp/demo3.xcstrings --yes
```

Expected: All commands work correctly

**Step 2: Запустить финальную проверку всех тестов**

```bash
pytest -v
ruff check .
black . --check
```

Expected: Everything passes

**Step 3: Создать финальный commit**

```bash
git add -A
git commit -m "feat(delete): complete implementation of delete command

- Implemented three deletion modes: --all, specific languages, and --keep
- Added comprehensive unit and integration tests
- Protected source language from deletion
- Added confirmation prompt with --yes flag for automation
- Support for backup with --backup flag
- Multi-file selection with auto-detection
- Rich table output showing languages and string counts

Closes implementation of delete command per design document.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Summary

Реализация включает:

1. ✅ Функцию `_determine_languages_to_delete()` для определения языков к удалению
2. ✅ Функцию `_delete_languages_from_catalog()` для удаления из структуры и raw_data
3. ✅ CLI команду `delete` с поддержкой трех режимов
4. ✅ Автопоиск файлов и выбор нескольких файлов
5. ✅ Подтверждение с флагом `--yes`
6. ✅ Backup с флагом `--backup`
7. ✅ Защита source language
8. ✅ Rich table вывод
9. ✅ Comprehensive тесты (unit + integration)
10. ✅ Документация в CLAUDE.md

Все изменения следуют существующей архитектуре проекта и стилю кода.
