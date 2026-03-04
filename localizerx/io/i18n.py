"""I/O operations for frontend i18n JSON files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from localizerx.parser.i18n_model import I18nCatalog, I18nLocale, I18nMessage


def read_i18n(path: Path, source_locale: str = "en") -> I18nCatalog:
    """
    Read i18n JSON files from a locales directory.

    Auto-detects layout:
    - Flat files: locales/en.json, locales/fr.json
    - Dir-per-locale: locales/en/translation.json

    Args:
        path: Path to the locales directory
        source_locale: The source locale code (default: en)

    Returns:
        I18nCatalog containing all locale data
    """
    if not path.exists():
        raise FileNotFoundError(f"Locales directory not found: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    layout = _detect_layout(path)
    catalog = I18nCatalog(source_locale=source_locale)

    if layout == "flat":
        _read_flat_layout(path, catalog)
    elif layout == "dir":
        _read_dir_layout(path, catalog)
    else:
        raise ValueError(f"Could not detect i18n layout in: {path}")

    return catalog


def write_i18n(
    catalog: I18nCatalog,
    path: Path,
    backup: bool = False,
    locales: list[str] | None = None,
    update_index: bool = True,
) -> None:
    """
    Write i18n catalog to the locales directory.

    Uses source structure as template for preserving nesting.

    Args:
        catalog: I18nCatalog to write
        path: Path to the locales directory
        backup: Whether to create backups of existing files
        locales: Specific locales to write (None = all non-source locales)
        update_index: Whether to update index.ts (default: True)
    """
    path.mkdir(parents=True, exist_ok=True)

    layout = _detect_layout(path)
    source = catalog.get_source_locale()
    source_raw = source.get_raw_data() if source else None

    locales_to_write = locales or [
        loc for loc in catalog.locales.keys() if loc != catalog.source_locale
    ]

    for locale_code in locales_to_write:
        locale_data = catalog.locales.get(locale_code)
        if not locale_data:
            continue

        # Build output JSON using source structure as template
        if source_raw:
            output = _build_output_from_template(source_raw, locale_data)
        else:
            output = _build_flat_output(locale_data)

        # Determine output file path
        if layout == "dir":
            locale_dir = path / locale_code
            locale_dir.mkdir(parents=True, exist_ok=True)
            # Find the JSON filename used by source
            json_filename = _find_json_filename(path, catalog.source_locale)
            file_path = locale_dir / json_filename
        else:
            file_path = path / f"{locale_code}.json"

        # Create backup if file exists
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(".json.backup")
            shutil.copy2(file_path, backup_path)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            f.write("\n")

    if update_index:
        update_index_ts(path, catalog)


def delete_i18n_locale(path: Path, locale_code: str) -> bool:
    """
    Delete an i18n locale file or directory.

    Args:
        path: Path to the locales directory
        locale_code: Standard locale code to delete

    Returns:
        True if deleted, False if not found
    """
    layout = _detect_layout(path)

    if layout == "dir":
        locale_dir = path / locale_code
        if locale_dir.exists() and locale_dir.is_dir():
            shutil.rmtree(locale_dir)
            return True
    else:
        file_path = path / f"{locale_code}.json"
        if file_path.exists():
            file_path.unlink()
            return True

    return False


def update_index_ts(path: Path, catalog: I18nCatalog) -> None:
    """
    Update index.ts in the locales directory with current locales.

    Generates TypeScript imports and exports for all locales in the catalog.
    """
    index_path = path / "index.ts"
    layout = _detect_layout(path)

    imports = []
    exports = []

    for locale_code in sorted(catalog.locales.keys()):
        # Sanitize variable name for import (e.g. en-US -> enUS)
        var_name = locale_code.replace("-", "").replace("_", "")

        if layout == "dir":
            filename = _find_json_filename(path, catalog.source_locale)
            imports.append(f"import {var_name} from \"./{locale_code}/{filename}\";")
        else:
            imports.append(f"import {var_name} from \"./{locale_code}.json\";")

        exports.append(f"  \"{locale_code}\": {var_name},")

    lines = (
        imports
        + [""]
        + ["export default {"]
        + exports
        + ["} as const;", ""]
    )

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def detect_i18n_path(start_path: Path | None = None) -> Path | None:
    """
    Auto-detect i18n locales directory.

    Searches in common locations first, then performs a recursive search.

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to locales directory if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    # Common explicit candidates (fast check)
    candidates = [
        start_path / "locales",
        start_path / "src" / "locales",
        start_path / "i18n",
        start_path / "src" / "i18n",
        start_path / "public" / "locales",
        start_path / "assets" / "locales",
        start_path / "lang",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if _detect_layout(candidate) is not None:
                return candidate

    # Recursive search if not found in common locations
    ignore_dirs = {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "build",
        "dist",
        "__pycache__",
        "target",
    }
    search_names = {"locales", "i18n", "lang"}

    for path in start_path.rglob("*"):
        if path.is_dir() and path.name in search_names:
            # Skip if any parent is in ignore_dirs
            if any(p.name in ignore_dirs for p in path.parents):
                continue

            if _detect_layout(path) is not None:
                return path

    return None


def _detect_layout(path: Path) -> str | None:
    """
    Detect the i18n directory layout.

    Returns:
        "flat" for locale.json files, "dir" for locale/translation.json, None if unknown
    """
    # Check for flat layout: en.json, fr.json, etc.
    json_files = list(path.glob("*.json"))
    if json_files:
        # Check if files look like locale codes (2-letter or xx-YY)
        for f in json_files:
            stem = f.stem
            if len(stem) == 2 or (len(stem) <= 7 and "-" in stem):
                return "flat"

    # Check for dir layout: en/translation.json, en/messages.json, etc.
    for subdir in path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            name = subdir.name
            if len(name) == 2 or (len(name) <= 7 and "-" in name):
                json_files_in_dir = list(subdir.glob("*.json"))
                if json_files_in_dir:
                    return "dir"

    return None


def _read_flat_layout(path: Path, catalog: I18nCatalog) -> None:
    """Read flat layout: locales/en.json, locales/fr.json."""
    for json_file in sorted(path.glob("*.json")):
        locale_code = json_file.stem
        # Skip files that don't look like locale codes
        if len(locale_code) > 10:
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        locale = I18nLocale(locale=locale_code)
        locale.set_raw_data(data)

        messages = _flatten_json(data)
        for key, value in messages.items():
            locale.messages[key] = I18nMessage(key=key, value=value)

        if locale.message_count > 0:
            catalog.locales[locale_code] = locale


def _read_dir_layout(path: Path, catalog: I18nCatalog) -> None:
    """Read dir layout: locales/en/translation.json."""
    for subdir in sorted(path.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue

        locale_code = subdir.name
        json_files = list(subdir.glob("*.json"))
        if not json_files:
            continue

        # Read the first JSON file found
        json_file = json_files[0]
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        locale = I18nLocale(locale=locale_code)
        locale.set_raw_data(data)

        messages = _flatten_json(data)
        for key, value in messages.items():
            locale.messages[key] = I18nMessage(key=key, value=value)

        if locale.message_count > 0:
            catalog.locales[locale_code] = locale


def _flatten_json(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """
    Flatten a nested JSON dict to dotted key paths.

    Examples:
        {"common": {"hello": "Hello"}} → {"common.hello": "Hello"}
        {"greeting": "Hi"} → {"greeting": "Hi"}
    """
    result: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_json(value, full_key))
        elif isinstance(value, str):
            result[full_key] = value
    return result


def _unflatten_to_nested(flat: dict[str, str]) -> dict[str, Any]:
    """
    Unflatten dotted key paths back to a nested dict.

    Examples:
        {"common.hello": "Hello"} → {"common": {"hello": "Hello"}}
    """
    result: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def _build_output_from_template(
    template: dict[str, Any],
    locale_data: I18nLocale,
) -> dict[str, Any]:
    """Build output JSON using source structure as template, replacing leaf values."""
    # Get the locale's raw data if it exists (for existing locales)
    raw = locale_data.get_raw_data()
    if raw is not None:
        output = _deep_copy(raw)
    else:
        output = _deep_copy(template)

    # Update all leaf values from messages
    _update_leaves(output, "", locale_data.messages)
    return output


def _update_leaves(
    data: dict[str, Any],
    prefix: str,
    messages: dict[str, I18nMessage],
) -> None:
    """Recursively update leaf string values in nested dict from messages."""
    for key in data:
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(data[key], dict):
            _update_leaves(data[key], full_key, messages)
        elif isinstance(data[key], str):
            msg = messages.get(full_key)
            if msg:
                data[key] = msg.value


def _build_flat_output(locale_data: I18nLocale) -> dict[str, Any]:
    """Build output JSON from flat messages (unflatten if needed)."""
    flat = {msg.key: msg.value for msg in locale_data.messages.values()}
    # Check if any keys have dots (nested structure)
    if any("." in key for key in flat):
        return _unflatten_to_nested(flat)
    return flat


def _find_json_filename(path: Path, source_locale: str) -> str:
    """Find the JSON filename used in the source locale directory."""
    source_dir = path / source_locale
    if source_dir.exists():
        json_files = list(source_dir.glob("*.json"))
        if json_files:
            return json_files[0].name
    return "translation.json"


def _deep_copy(obj: Any) -> Any:
    """Create a deep copy of a JSON-compatible object."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_copy(item) for item in obj]
    else:
        return obj
