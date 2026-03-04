"""Lossless I/O for .xcstrings files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from localizerx.parser.model import Entry, StringCatalog, Translation


def read_xcstrings(path: Path) -> StringCatalog:
    """
    Read an .xcstrings file and parse it into a StringCatalog.

    Preserves the original JSON structure for lossless round-trip writes.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        data = json.loads(content)

    source_language = data.get("sourceLanguage", "en")
    version = data.get("version", "1.0")
    strings_data = data.get("strings", {})

    strings: dict[str, Entry] = {}
    for key, entry_data in strings_data.items():
        entry = _parse_entry(key, entry_data, source_language)
        strings[key] = entry

    catalog = StringCatalog(
        source_language=source_language,
        strings=strings,
        version=version,
    )
    catalog.set_raw_data(data)
    _apply_formatting_to_catalog(content, catalog)
    return catalog


def _apply_formatting_to_catalog(content: str, catalog: StringCatalog) -> None:
    """Detect and set formatting (indent and separators) from the original file content."""
    import re

    # Detect indentation
    indent = 2
    match = re.search(r"\n(\s+)\"", content)
    if match:
        indent_str = match.group(1)
        if indent_str:
            indent = len(indent_str)

    # Detect key-value separator
    separators = (",", ": ")
    # Look for the first key-value separator pattern: "key" : "value" or "key" : {
    sep_match = re.search(r'"[^"]+"(\s*:\s*)["{]', content)
    if sep_match:
        separators = (",", sep_match.group(1))

    catalog.set_formatting(indent, separators)


def _parse_entry(key: str, data: dict[str, Any], source_language: str) -> Entry:
    """Parse a single entry from xcstrings format."""
    comment = data.get("comment")
    extraction_state = data.get("extractionState")
    should_translate = data.get("shouldTranslate", True)

    # Get source text and variations from the source language localization
    localizations = data.get("localizations", {})
    source_text = key  # Default to key
    source_variations = None

    if source_language in localizations:
        source_loc = localizations[source_language]
        if "stringUnit" in source_loc:
            source_text = source_loc["stringUnit"].get("value", key)
        # Extract source variations (for plurals/gender forms)
        if "variations" in source_loc:
            source_variations = source_loc["variations"]

    # Parse existing translations
    translations: dict[str, Translation] = {}
    for lang, loc_data in localizations.items():
        if lang == source_language:
            continue
        translation = _parse_translation(loc_data)
        if translation:
            translations[lang] = translation

    return Entry(
        key=key,
        source_text=source_text,
        comment=comment,
        translations=translations,
        extraction_state=extraction_state,
        should_translate=should_translate,
        source_variations=source_variations,
    )


def _parse_translation(loc_data: dict[str, Any]) -> Translation | None:
    """Parse a translation from localization data."""
    if "stringUnit" in loc_data:
        unit = loc_data["stringUnit"]
        return Translation(
            value=unit.get("value", ""),
            state=unit.get("state", "translated"),
            variations=loc_data.get("variations"),
        )
    elif "variations" in loc_data:
        # Handle plural-only entries
        return Translation(
            value="",
            state="translated",
            variations=loc_data["variations"],
        )
    return None


def write_xcstrings(
    catalog: StringCatalog,
    path: Path,
    backup: bool = False,
) -> None:
    """
    Write a StringCatalog back to an .xcstrings file.

    Preserves the original structure, only adding/updating translations.
    """
    if backup and path.exists():
        backup_path = path.with_suffix(".xcstrings.backup")
        shutil.copy2(path, backup_path)

    # Start from original data if available for lossless round-trip
    raw_data = catalog.get_raw_data()
    if raw_data:
        data = _deep_copy(raw_data)
    else:
        data = {
            "sourceLanguage": catalog.source_language,
            "version": catalog.version,
            "strings": {},
        }

    # Ensure strings dict exists
    if "strings" not in data:
        data["strings"] = {}

    # Remove strings that were deleted from catalog
    keys_to_remove = [k for k in data["strings"].keys() if k not in catalog.strings]
    for k in keys_to_remove:
        del data["strings"][k]

    # Update translations in the data
    for key, entry in catalog.strings.items():
        if key not in data["strings"]:
            data["strings"][key] = {}

        entry_data = data["strings"][key]
        if "localizations" not in entry_data:
            entry_data["localizations"] = {}

        # Remove languages not present in entry.translations (except source_language)
        existing_langs = list(entry_data["localizations"].keys())
        for lang in existing_langs:
            if lang != catalog.source_language and lang not in entry.translations:
                del entry_data["localizations"][lang]

        # Add/update translations
        for lang, translation in entry.translations.items():
            entry_data["localizations"][lang] = translation.to_xcstrings_dict()

    # Get formatting from catalog
    indent, separators = catalog.get_formatting()

    # Write with consistent formatting
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=indent,
            separators=separators,
            sort_keys=False,
        )
        f.write("\n")  # Trailing newline


def _deep_copy(obj: Any) -> Any:
    """Create a deep copy of a JSON-compatible object."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_copy(item) for item in obj]
    else:
        return obj
