"""I/O operations for App Store screenshot text files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from localizerx.parser.screenshots_model import (
    ScreenshotLocale,
    ScreenshotsCatalog,
    ScreenshotScreen,
    ScreenshotText,
    ScreenshotTextType,
)


def read_screenshots(path: Path) -> ScreenshotsCatalog:
    """
    Read a screenshots texts.json file and parse it into a ScreenshotsCatalog.

    Expected JSON structure:
    {
        "sourceLanguage": "en",
        "screens": {
            "screen_1": {
                "headline": { "small": "Track Habits", "large": "Track Your Daily Habits" }
            }
        },
        "localizations": {
            "de": {
                "screen_1": {
                    "headline": { "small": "Gewohnheiten", "large": "Tägliche Gewohnheiten" }
                }
            }
        }
    }

    Args:
        path: Path to the texts.json file

    Returns:
        ScreenshotsCatalog containing all screenshot texts
    """
    if not path.exists():
        raise FileNotFoundError(f"Screenshots file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    source_language = data.get("sourceLanguage", "en")
    screens_data = data.get("screens", {})
    localizations_data = data.get("localizations", {})

    catalog = ScreenshotsCatalog(source_language=source_language)

    # Parse source screens
    for screen_id, screen_data in screens_data.items():
        screen = _parse_screen(screen_data)
        if screen.text_count > 0:
            catalog.screens[screen_id] = screen

    # Parse localizations
    for locale, locale_screens in localizations_data.items():
        locale_data = ScreenshotLocale(locale=locale)
        for screen_id, screen_data in locale_screens.items():
            screen = _parse_screen(screen_data)
            if screen.text_count > 0:
                locale_data.screens[screen_id] = screen
        if locale_data.screen_count > 0:
            catalog.localizations[locale] = locale_data

    # Store raw data for lossless round-trip
    catalog.set_raw_data(data)

    return catalog


def _parse_screen(data: dict[str, Any]) -> ScreenshotScreen:
    """Parse a single screen from JSON data."""
    screen = ScreenshotScreen()

    for text_type_str, text_data in data.items():
        try:
            text_type = ScreenshotTextType(text_type_str)
        except ValueError:
            # Unknown text type, skip
            continue

        if isinstance(text_data, dict):
            text = ScreenshotText(
                small=text_data.get("small"),
                large=text_data.get("large"),
            )
            if not text.is_empty:
                screen.texts[text_type] = text

    return screen


def write_screenshots(
    catalog: ScreenshotsCatalog,
    path: Path,
    backup: bool = False,
) -> None:
    """
    Write a ScreenshotsCatalog to a JSON file.

    Preserves the original structure for lossless round-trip.

    Args:
        catalog: ScreenshotsCatalog to write
        path: Path to the output file
        backup: Whether to create a backup of the existing file
    """
    if backup and path.exists():
        backup_path = path.with_suffix(".json.backup")
        shutil.copy2(path, backup_path)

    # Start from raw data if available for lossless round-trip
    raw_data = catalog.get_raw_data()
    if raw_data:
        data = _deep_copy(raw_data)
    else:
        data = {
            "sourceLanguage": catalog.source_language,
            "screens": {},
        }

    # Update source screens
    if "screens" not in data:
        data["screens"] = {}

    for screen_id, screen in catalog.screens.items():
        if screen_id not in data["screens"]:
            data["screens"][screen_id] = {}
        _update_screen_data(data["screens"][screen_id], screen)

    # Update localizations
    if catalog.localizations:
        if "localizations" not in data:
            data["localizations"] = {}

        for locale, locale_data in catalog.localizations.items():
            if locale not in data["localizations"]:
                data["localizations"][locale] = {}

            for screen_id, screen in locale_data.screens.items():
                if screen_id not in data["localizations"][locale]:
                    data["localizations"][locale][screen_id] = {}
                _update_screen_data(data["localizations"][locale][screen_id], screen)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write with consistent formatting
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _update_screen_data(data: dict[str, Any], screen: ScreenshotScreen) -> None:
    """Update screen data dictionary from ScreenshotScreen model."""
    for text_type, text in screen.texts.items():
        text_type_str = text_type.value
        if text_type_str not in data:
            data[text_type_str] = {}

        if text.small is not None:
            data[text_type_str]["small"] = text.small
        if text.large is not None:
            data[text_type_str]["large"] = text.large


def _deep_copy(obj: Any) -> Any:
    """Create a deep copy of a JSON-compatible object."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_copy(item) for item in obj]
    else:
        return obj


def detect_screenshots_path(start_path: Path | None = None) -> Path | None:
    """
    Auto-detect screenshots texts.json file.

    Searches in common locations:
    - ./screenshots/texts.json
    - ./texts.json
    - ../screenshots/texts.json

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to texts.json if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    # Common screenshot text file locations
    candidates = [
        start_path / "screenshots" / "texts.json",
        start_path / "texts.json",
        start_path.parent / "screenshots" / "texts.json",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def get_default_screenshots_path(start_path: Path | None = None) -> Path:
    """
    Get the default path for screenshots texts.json.

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to screenshots/texts.json
    """
    if start_path is None:
        start_path = Path.cwd()
    return start_path / "screenshots" / "texts.json"


def create_screenshots_template(
    path: Path,
    source_language: str = "en",
) -> ScreenshotsCatalog:
    """
    Create a template screenshots texts.json file.

    Args:
        path: Path where to create the file
        source_language: Source language code

    Returns:
        The created ScreenshotsCatalog
    """
    # Create template catalog with example structure
    catalog = ScreenshotsCatalog(source_language=source_language)

    # Add example screen 1
    screen1 = ScreenshotScreen()
    screen1.texts[ScreenshotTextType.HEADLINE] = ScreenshotText(
        small="Your Headline",
        large="Your Main Headline Here",
    )
    screen1.texts[ScreenshotTextType.SUBTITLE] = ScreenshotText(
        small="Short subtitle",
        large="A slightly longer subtitle",
    )
    catalog.screens["screen_1"] = screen1

    # Add example screen 2
    screen2 = ScreenshotScreen()
    screen2.texts[ScreenshotTextType.HEADLINE] = ScreenshotText(
        small="Feature Name",
        large="Amazing Feature Name",
    )
    catalog.screens["screen_2"] = screen2

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write the template
    write_screenshots(catalog, path, backup=False)

    return catalog


def screenshots_file_exists(path: Path | None = None) -> bool:
    """
    Check if screenshots texts.json file exists.

    Args:
        path: Explicit path or None to auto-detect

    Returns:
        True if file exists
    """
    if path is not None:
        return path.exists()

    detected = detect_screenshots_path()
    return detected is not None


def read_hints_file(path: Path) -> dict[str, str]:
    """
    Read screen hints/descriptions from a JSON file.

    Expected format:
    {
        "screen_1": "Main dashboard showing daily progress",
        "screen_2": "Settings page with customization options",
        "screen_3": "Achievement system and rewards"
    }

    Args:
        path: Path to the hints JSON file

    Returns:
        Dictionary mapping screen IDs to their descriptions

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is not valid JSON or has wrong format
    """
    if not path.exists():
        raise FileNotFoundError(f"Hints file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in hints file: {e}")

    if not isinstance(data, dict):
        raise ValueError("Hints file must contain a JSON object")

    # Validate all values are strings
    hints = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError(f"Hint keys must be strings, got: {type(key)}")
        if not isinstance(value, str):
            raise ValueError(f"Hint values must be strings, got: {type(value)} for key '{key}'")
        hints[key] = value

    return hints
