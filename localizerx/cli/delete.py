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
