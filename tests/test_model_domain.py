"""Unit tests for StringCatalog domain logic."""

import pytest
from localizerx.parser.model import StringCatalog, Entry, Translation

def test_catalog_refresh_removes_stale():
    catalog = StringCatalog(
        source_language="en",
        strings={
            "new_key": Entry(key="new_key", source_text="New", extraction_state="new"),
            "stale_key": Entry(key="stale_key", source_text="Stale", extraction_state="stale"),
            "trans_key": Entry(key="trans_key", source_text="Trans", extraction_state="translated"),
        }
    )
    
    removed = catalog.refresh()
    
    assert removed == ["stale_key"]
    assert "stale_key" not in catalog.strings
    assert "new_key" in catalog.strings
    assert "trans_key" in catalog.strings

def test_catalog_mark_empty_as_translated():
    catalog = StringCatalog(
        source_language="en",
        strings={
            "empty": Entry(key="empty", source_text="", translations={"fr": Translation(value="old")}),
            "whitespace": Entry(key="whitespace", source_text="   "),
            "content": Entry(key="content", source_text="content"),
            "variations": Entry(key="variations", source_text="", source_variations={"plural": {}}),
        }
    )
    
    # Without overwrite
    marked = catalog.mark_empty_as_translated(["fr", "es"], overwrite=False)
    
    assert marked == 3 # whitespace to fr/es (2) + empty to es (1)
    
    assert "fr" in catalog.strings["empty"].translations
    assert catalog.strings["empty"].translations["fr"].value == "old" # not overwritten
    
    assert "es" in catalog.strings["empty"].translations
    assert catalog.strings["empty"].translations["es"].value == ""
    
    assert "fr" in catalog.strings["whitespace"].translations
    assert "es" in catalog.strings["whitespace"].translations
    
    assert "fr" not in catalog.strings["content"].translations
    assert "fr" not in catalog.strings["variations"].translations

    # With overwrite
    marked_overwrite = catalog.mark_empty_as_translated(["fr"], overwrite=True)
    assert marked_overwrite == 2 # empty and whitespace
    assert catalog.strings["empty"].translations["fr"].value == "" # overwritten

def test_catalog_remove_languages():
    catalog = StringCatalog(
        source_language="en",
        strings={
            "key1": Entry(
                key="key1", 
                source_text="text", 
                translations={
                    "fr": Translation(value="fr text"),
                    "es": Translation(value="es text")
                }
            )
        }
    )
    
    removed = catalog.remove_languages(["fr", "de"])
    
    assert removed == ["fr"] # de was not present
    assert "fr" not in catalog.strings["key1"].translations
    assert "es" in catalog.strings["key1"].translations

def test_get_entries_needing_translation_flags():
    catalog = StringCatalog(
        source_language="en",
        strings={
            "new_key": Entry(key="new_key", source_text="New", extraction_state="new"),
            "trans_key": Entry(
                key="trans_key", 
                source_text="Trans", 
                extraction_state="translated",
                translations={"fr": Translation(value="fr trans")}
            ),
        }
    )
    
    # Standard request
    entries = catalog.get_entries_needing_translation("fr")
    assert len(entries) == 1
    assert entries[0].key == "new_key"
    
    # With overwrite
    entries_overwrite = catalog.get_entries_needing_translation("fr", overwrite=True)
    assert len(entries_overwrite) == 2
    
    # With refresh (only target new strings)
    entries_refresh = catalog.get_entries_needing_translation("fr", refresh=True)
    assert len(entries_refresh) == 1
    assert entries_refresh[0].key == "new_key"
    
    entries_refresh_overwrite = catalog.get_entries_needing_translation("fr", overwrite=True, refresh=True)
    assert len(entries_refresh_overwrite) == 1 # still only new_key because trans_key is not "new"
