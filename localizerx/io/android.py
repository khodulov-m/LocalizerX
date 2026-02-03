"""I/O operations for Android res/values strings.xml files."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from localizerx.parser.android_model import (
    AndroidCatalog,
    AndroidLocale,
    AndroidPlural,
    AndroidString,
    AndroidStringArray,
)
from localizerx.utils.locale import android_to_standard_locale, standard_to_android_locale


def read_android(path: Path, source_locale: str = "en") -> AndroidCatalog:
    """
    Read Android string resources from a res/ directory.

    Expected structure:
        res/
        ├── values/           (default/source locale)
        │   └── strings.xml
        ├── values-fr/
        │   └── strings.xml
        ├── values-pt-rBR/
        │   └── strings.xml
        └── ...

    Args:
        path: Path to the res/ directory
        source_locale: The source locale code (default: en)

    Returns:
        AndroidCatalog containing all locale data
    """
    if not path.exists():
        raise FileNotFoundError(f"Resource directory not found: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    catalog = AndroidCatalog(source_locale=source_locale)

    for values_dir in sorted(path.iterdir()):
        if not values_dir.is_dir():
            continue
        if not values_dir.name.startswith("values"):
            continue

        strings_file = values_dir / "strings.xml"
        if not strings_file.exists():
            continue

        # Determine locale code
        dir_name = values_dir.name
        if dir_name == "values":
            locale_code = source_locale
        else:
            # values-fr → fr, values-pt-rBR → pt-BR
            suffix = dir_name[len("values-") :]
            locale_code = android_to_standard_locale(suffix)

        locale_data = _read_strings_xml(strings_file, locale_code)
        catalog.locales[locale_code] = locale_data

    return catalog


def write_android(
    catalog: AndroidCatalog,
    path: Path,
    backup: bool = False,
    locales: list[str] | None = None,
) -> None:
    """
    Write Android string resources to res/ directory.

    Args:
        catalog: AndroidCatalog to write
        path: Path to the res/ directory
        backup: Whether to create backups of existing files
        locales: Specific locales to write (None = all non-source locales)
    """
    path.mkdir(parents=True, exist_ok=True)

    locales_to_write = locales or [
        loc for loc in catalog.locales.keys() if loc != catalog.source_locale
    ]

    for locale_code in locales_to_write:
        locale_data = catalog.locales.get(locale_code)
        if not locale_data:
            continue

        # Determine directory name
        if locale_code == catalog.source_locale:
            dir_name = "values"
        else:
            suffix = standard_to_android_locale(locale_code)
            dir_name = f"values-{suffix}"

        values_dir = path / dir_name
        values_dir.mkdir(parents=True, exist_ok=True)

        file_path = values_dir / "strings.xml"

        # Create backup if file exists
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(".xml.backup")
            shutil.copy2(file_path, backup_path)

        _write_strings_xml(file_path, locale_data)


def detect_android_path(start_path: Path | None = None) -> Path | None:
    """
    Auto-detect Android res/ directory.

    Searches in common locations:
    - ./res, ./app/src/main/res, ./src/main/res

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to res/ directory if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    candidates = [
        start_path / "res",
        start_path / "app" / "src" / "main" / "res",
        start_path / "src" / "main" / "res",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if _looks_like_res_dir(candidate):
                return candidate

    return None


def _looks_like_res_dir(path: Path) -> bool:
    """Check if a directory looks like an Android res/ directory."""
    values_dir = path / "values"
    if values_dir.exists() and (values_dir / "strings.xml").exists():
        return True
    return False


def _read_strings_xml(file_path: Path, locale_code: str) -> AndroidLocale:
    """Read a single strings.xml file."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    locale = AndroidLocale(locale=locale_code)
    pending_comment: str | None = None

    for elem in root:
        # Skip XML comments (ET.Comment elements have callable tag)
        if callable(elem.tag):
            continue

        if elem.tag == "string":
            name = elem.get("name", "")
            translatable = elem.get("translatable", "true").lower() != "false"
            value = _get_element_text(elem)

            locale.strings[name] = AndroidString(
                name=name,
                value=value,
                translatable=translatable,
                comment=pending_comment,
            )
            pending_comment = None

        elif elem.tag == "string-array":
            name = elem.get("name", "")
            translatable = elem.get("translatable", "true").lower() != "false"
            items = [_get_element_text(item) for item in elem.findall("item")]

            locale.string_arrays[name] = AndroidStringArray(
                name=name,
                items=items,
                translatable=translatable,
                comment=pending_comment,
            )
            pending_comment = None

        elif elem.tag == "plurals":
            name = elem.get("name", "")
            translatable = elem.get("translatable", "true").lower() != "false"
            items = {}
            for item in elem.findall("item"):
                quantity = item.get("quantity", "")
                items[quantity] = _get_element_text(item)

            locale.plurals[name] = AndroidPlural(
                name=name,
                items=items,
                translatable=translatable,
                comment=pending_comment,
            )
            pending_comment = None

    return locale


def _get_element_text(elem: ET.Element) -> str:
    """Get text content from an XML element, handling mixed content."""
    # ElementTree stores text simply
    text = elem.text or ""
    # Handle child elements (e.g., <xliff:g>)
    for child in elem:
        text += ET.tostring(child, encoding="unicode", method="xml")
    return _unescape_android_string(text)


def _write_strings_xml(file_path: Path, locale_data: AndroidLocale) -> None:
    """Write a single strings.xml file."""
    root = ET.Element("resources")

    # Write strings
    for name, string in locale_data.strings.items():
        elem = ET.SubElement(root, "string", name=name)
        if not string.translatable:
            elem.set("translatable", "false")
        elem.text = _escape_android_string(string.value)

    # Write string-arrays
    for name, array in locale_data.string_arrays.items():
        arr_elem = ET.SubElement(root, "string-array", name=name)
        if not array.translatable:
            arr_elem.set("translatable", "false")
        for item_value in array.items:
            item_elem = ET.SubElement(arr_elem, "item")
            item_elem.text = _escape_android_string(item_value)

    # Write plurals
    for name, plural in locale_data.plurals.items():
        pl_elem = ET.SubElement(root, "plurals", name=name)
        if not plural.translatable:
            pl_elem.set("translatable", "false")
        for quantity, value in plural.items.items():
            item_elem = ET.SubElement(pl_elem, "item", quantity=quantity)
            item_elem.text = _escape_android_string(value)

    # Write with XML declaration and indentation
    ET.indent(root)
    tree = ET.ElementTree(root)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)

    # Add trailing newline
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n")


def _escape_android_string(text: str) -> str:
    """
    Escape a string for Android XML.

    Android requires escaping apostrophes and quotes in string resources.
    XML entities (&, <, >) are handled by ElementTree automatically.
    """
    # Escape apostrophes (not already escaped)
    text = text.replace("\\'", "\x00")  # Preserve already-escaped
    text = text.replace("'", "\\'")
    text = text.replace("\x00", "\\'")  # Restore

    return text


def _unescape_android_string(text: str) -> str:
    """
    Unescape an Android XML string.

    Reverses Android-specific escaping.
    """
    text = text.replace("\\'", "'")
    text = text.replace('\\"', '"')
    return text
