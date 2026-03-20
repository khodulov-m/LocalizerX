"""I/O operations for fastlane frameit files."""

from __future__ import annotations

import json
import re
from pathlib import Path

from localizerx.parser.frameit_model import FrameitCatalog, FrameitLocale

# Regex to capture "Key" = "Value"; from .strings files
# Allows optional spaces and comments might be ignored if they don't match
STRINGS_PATTERN = re.compile(r'(?m)^"(.+?)"\s*=\s*"(.+?)";')


def read_strings_file(path: Path) -> dict[str, str]:
    """Read a .strings file and return a dictionary of key-value pairs."""
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    matches = STRINGS_PATTERN.findall(content)
    return {k: v for k, v in matches}


def write_strings_file(path: Path, data: dict[str, str]) -> None:
    """Write a dictionary of key-value pairs to a .strings file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'"{k}" = "{v}";' for k, v in data.items()]
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")


def ensure_framefile(base_path: Path) -> None:
    """Create a basic Framefile.json if it doesn't exist."""
    base_path.mkdir(parents=True, exist_ok=True)
    framefile_path = base_path / "Framefile.json"
    if not framefile_path.exists():
        template = {
            "default": {
                "title": {
                    "color": "#000000"
                },
                "background": "./background.png"
            },
            "data": []
        }
        with open(framefile_path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)
            f.write("\n")


def detect_frameit_path(start_path: Path | None = None) -> Path:
    """Detect or return default fastlane/screenshots path."""
    if start_path is None:
        start_path = Path.cwd()

    candidates = [
        start_path / "fastlane" / "screenshots",
        start_path / "screenshots",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            # Check if it looks like frameit directory
            if (candidate / "Framefile.json").exists():
                return candidate
            for subdir in candidate.iterdir():
                if subdir.is_dir() and (subdir / "title.strings").exists():
                    return candidate

    # Default to fastlane/screenshots if not found
    return start_path / "fastlane" / "screenshots"


def read_frameit_catalog(base_path: Path, source_locale: str = "en-US") -> FrameitCatalog:
    """Read frameit strings from the base path."""
    catalog = FrameitCatalog(source_locale=source_locale)
    if not base_path.exists() or not base_path.is_dir():
        return catalog

    for subdir in base_path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            locale = subdir.name
            frameit_locale = catalog.get_or_create_locale(locale)

            title_strings = read_strings_file(subdir / "title.strings")
            for k, v in title_strings.items():
                frameit_locale.set_title(k, v)

            keyword_strings = read_strings_file(subdir / "keyword.strings")
            for k, v in keyword_strings.items():
                frameit_locale.set_keyword(k, v)

    return catalog


def write_frameit_locale(base_path: Path, frameit_locale: FrameitLocale) -> None:
    """Write frameit strings for a locale."""
    locale_dir = base_path / frameit_locale.locale

    if frameit_locale.title_strings:
        title_data = {k: v.value for k, v in frameit_locale.title_strings.items()}
        write_strings_file(locale_dir / "title.strings", title_data)

    if frameit_locale.keyword_strings:
        keyword_data = {k: v.value for k, v in frameit_locale.keyword_strings.items()}
        write_strings_file(locale_dir / "keyword.strings", keyword_data)
