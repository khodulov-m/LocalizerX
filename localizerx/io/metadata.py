"""I/O operations for fastlane metadata files."""

from __future__ import annotations

import shutil
from pathlib import Path

from localizerx.parser.metadata_model import (
    FIELD_TO_FILENAME,
    FILENAME_TO_FIELD,
    LocaleMetadata,
    MetadataCatalog,
    MetadataFieldType,
)


def read_metadata(path: Path, source_locale: str = "en-US") -> MetadataCatalog:
    """
    Read fastlane metadata structure from a directory.

    Expected structure:
        metadata/
        ├── en-US/
        │   ├── name.txt
        │   ├── subtitle.txt
        │   └── ...
        ├── de-DE/
        │   └── ...
        └── ...

    Args:
        path: Path to the metadata directory
        source_locale: The source locale code (default: en-US)

    Returns:
        MetadataCatalog containing all locale metadata
    """
    if not path.exists():
        raise FileNotFoundError(f"Metadata directory not found: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    catalog = MetadataCatalog(source_locale=source_locale)

    # Read each locale directory
    for locale_dir in sorted(path.iterdir()):
        if not locale_dir.is_dir():
            continue

        # Skip hidden directories
        if locale_dir.name.startswith("."):
            continue

        locale_code = locale_dir.name
        locale_metadata = _read_locale_dir(locale_dir, locale_code)

        if locale_metadata.field_count > 0:
            catalog.locales[locale_code] = locale_metadata

    return catalog


def _read_locale_dir(locale_dir: Path, locale_code: str) -> LocaleMetadata:
    """Read metadata files from a single locale directory."""
    metadata = LocaleMetadata(locale=locale_code)

    for filename, field_type in FILENAME_TO_FIELD.items():
        file_path = locale_dir / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8").strip()
            metadata.set_field(field_type, content)

    return metadata


def write_metadata(
    catalog: MetadataCatalog,
    path: Path,
    backup: bool = True,
    locales: list[str] | None = None,
) -> None:
    """
    Write metadata catalog to fastlane directory structure.

    Args:
        catalog: MetadataCatalog to write
        path: Path to the metadata directory
        backup: Whether to create backups of existing files
        locales: Specific locales to write (None = all locales)
    """
    path.mkdir(parents=True, exist_ok=True)

    locales_to_write = locales or list(catalog.locales.keys())

    for locale_code in locales_to_write:
        if locale_code not in catalog.locales:
            continue

        locale_metadata = catalog.locales[locale_code]
        _write_locale_dir(path, locale_metadata, backup)


def _write_locale_dir(
    base_path: Path,
    locale_metadata: LocaleMetadata,
    backup: bool,
) -> None:
    """Write metadata files for a single locale."""
    locale_dir = base_path / locale_metadata.locale
    locale_dir.mkdir(parents=True, exist_ok=True)

    for field_type, field in locale_metadata.fields.items():
        filename = FIELD_TO_FILENAME[field_type]
        file_path = locale_dir / filename

        # Create backup if file exists
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(".txt.backup")
            shutil.copy2(file_path, backup_path)

        # Write content with trailing newline
        file_path.write_text(field.content + "\n", encoding="utf-8")


def detect_metadata_path(start_path: Path | None = None) -> Path | None:
    """
    Auto-detect fastlane metadata directory.

    Searches in common locations:
    - ./fastlane/metadata
    - ./metadata
    - ../fastlane/metadata

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to metadata directory if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    # Common metadata directory locations
    candidates = [
        start_path / "fastlane" / "metadata",
        start_path / "metadata",
        start_path.parent / "fastlane" / "metadata",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            # Verify it looks like a metadata directory
            if _looks_like_metadata_dir(candidate):
                return candidate

    return None


def _looks_like_metadata_dir(path: Path) -> bool:
    """Check if a directory looks like a fastlane metadata directory."""
    # Should contain at least one subdirectory with a .txt file
    for subdir in path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            for file in subdir.iterdir():
                if file.suffix == ".txt" and file.stem in [
                    "name",
                    "subtitle",
                    "keywords",
                    "description",
                    "promotional_text",
                    "release_notes",
                ]:
                    return True
    return False


def get_available_locales(path: Path) -> list[str]:
    """
    Get list of locale codes available in a metadata directory.

    Args:
        path: Path to the metadata directory

    Returns:
        List of locale codes found
    """
    if not path.exists() or not path.is_dir():
        return []

    locales = []
    for subdir in sorted(path.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            locales.append(subdir.name)

    return locales


def get_locale_fields(path: Path, locale: str) -> list[MetadataFieldType]:
    """
    Get list of metadata fields available for a locale.

    Args:
        path: Path to the metadata directory
        locale: Locale code

    Returns:
        List of MetadataFieldType values for existing files
    """
    locale_dir = path / locale
    if not locale_dir.exists() or not locale_dir.is_dir():
        return []

    fields = []
    for filename, field_type in FILENAME_TO_FIELD.items():
        if (locale_dir / filename).exists():
            fields.append(field_type)

    return fields
