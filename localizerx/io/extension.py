"""I/O operations for Chrome Extension _locales/ files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from localizerx.parser.extension_model import ExtensionCatalog, ExtensionLocale, ExtensionMessage


def read_extension(path: Path, source_locale: str = "en") -> ExtensionCatalog:
    """
    Read Chrome Extension locale structure from a _locales/ directory.

    Expected structure:
        _locales/
        ├── en/
        │   └── messages.json
        ├── fr/
        │   └── messages.json
        └── ...

    Args:
        path: Path to the _locales/ directory
        source_locale: The source locale code (default: en)

    Returns:
        ExtensionCatalog containing all locale data
    """
    if not path.exists():
        raise FileNotFoundError(f"Locales directory not found: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    catalog = ExtensionCatalog(source_locale=source_locale)

    for locale_dir in sorted(path.iterdir()):
        if not locale_dir.is_dir():
            continue
        if locale_dir.name.startswith("."):
            continue

        messages_file = locale_dir / "messages.json"
        if not messages_file.exists():
            continue

        locale_code = locale_dir.name
        locale_data = _read_messages_json(messages_file, locale_code)

        if locale_data.field_count > 0:
            catalog.locales[locale_code] = locale_data

    return catalog


def _read_messages_json(file_path: Path, locale_code: str) -> ExtensionLocale:
    """Read a single messages.json file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    locale = ExtensionLocale(locale=locale_code)

    for key, msg_data in data.items():
        if not isinstance(msg_data, dict):
            continue
        message = msg_data.get("message", "")
        description = msg_data.get("description")
        placeholders = msg_data.get("placeholders")

        locale.messages[key] = ExtensionMessage(
            key=key,
            message=message,
            description=description,
            placeholders=placeholders,
        )

    return locale


def write_extension(
    catalog: ExtensionCatalog,
    path: Path,
    backup: bool = False,
    locales: list[str] | None = None,
) -> None:
    """
    Write extension catalog to _locales/ directory structure.

    Creates locale directories and messages.json files as needed.
    Preserves description and placeholders fields losslessly.

    Args:
        catalog: ExtensionCatalog to write
        path: Path to the _locales/ directory
        backup: Whether to create backups of existing files
        locales: Specific locales to write (None = all locales)
    """
    path.mkdir(parents=True, exist_ok=True)

    locales_to_write = locales or list(catalog.locales.keys())

    for locale_code in locales_to_write:
        if locale_code not in catalog.locales:
            continue

        locale_data = catalog.locales[locale_code]
        _write_messages_json(path, locale_data, backup)


def _write_messages_json(
    base_path: Path,
    locale_data: ExtensionLocale,
    backup: bool,
) -> None:
    """Write messages.json for a single locale."""
    locale_dir = base_path / locale_data.locale
    locale_dir.mkdir(parents=True, exist_ok=True)

    file_path = locale_dir / "messages.json"

    # Create backup if file exists
    if backup and file_path.exists():
        backup_path = file_path.with_suffix(".json.backup")
        shutil.copy2(file_path, backup_path)

    # Build the output dict preserving all fields
    output: dict[str, Any] = {}
    for key, msg in locale_data.messages.items():
        entry: dict[str, Any] = {"message": msg.message}
        if msg.description is not None:
            entry["description"] = msg.description
        if msg.placeholders is not None:
            entry["placeholders"] = msg.placeholders
        output[key] = entry

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")


def detect_extension_path(start_path: Path | None = None) -> Path | None:
    """
    Auto-detect Chrome Extension _locales/ directory.

    Searches in common locations:
    - ./_locales
    - ../_locales

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to _locales/ directory if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    candidates = [
        start_path / "_locales",
        start_path.parent / "_locales",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if _looks_like_locales_dir(candidate):
                return candidate

    return None


def _looks_like_locales_dir(path: Path) -> bool:
    """Check if a directory looks like a Chrome Extension _locales/ dir."""
    for subdir in path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            if (subdir / "messages.json").exists():
                return True
    return False
