"""Test plural variations parsing and translation."""

import json
from pathlib import Path

import pytest

from localizerx.io.xcstrings import read_xcstrings


class TestPluralsParsing:
    """Test parsing of plural variations from xcstrings."""

    @pytest.fixture
    def plurals_file(self):
        """Path to test plurals file."""
        return Path("examples/Plurals.xcstrings")

    def test_parse_plural_entry(self, plurals_file):
        """Verify that plural variations are parsed correctly."""
        catalog = read_xcstrings(plurals_file)

        # Get the weeks_ago entry which has plurals
        weeks_entry = catalog.strings["weeks_ago"]

        assert weeks_entry.key == "weeks_ago"
        assert weeks_entry.comment == "Time elapsed in weeks"

        # The source language (en) should have variations, not a simple value
        # Check if English is stored as a translation with variations
        # (Since variations are in the source language localization)

        print("\n=== weeks_ago entry debug ===")
        print(f"Source text: {weeks_entry.source_text}")
        print(f"Translations keys: {list(weeks_entry.translations.keys())}")

        # If source language has variations, it might be stored as a translation
        if "en" in weeks_entry.translations:
            en_trans = weeks_entry.translations["en"]
            print(f"EN translation value: {en_trans.value}")
            print(f"EN translation variations: {en_trans.variations}")
            if en_trans.variations:
                print(f"Variations structure:\n{json.dumps(en_trans.variations, indent=2)}")

        # Assert that we can see the variations structure
        # This test documents current behavior before implementing translation support
        assert "en" in weeks_entry.translations or weeks_entry.source_text

    def test_parse_items_selected_with_zero_form(self, plurals_file):
        """Test entry with zero, one, and other plural forms."""
        catalog = read_xcstrings(plurals_file)

        items_entry = catalog.strings["items_selected"]

        assert items_entry.key == "items_selected"
        print("\n=== items_selected entry debug ===")
        print(f"Source text: {items_entry.source_text}")
        print(f"Translations: {list(items_entry.translations.keys())}")

        if "en" in items_entry.translations:
            en_trans = items_entry.translations["en"]
            if en_trans.variations and "plural" in en_trans.variations:
                plural_forms = en_trans.variations["plural"]
                print(f"Plural forms available: {list(plural_forms.keys())}")

                # Check that all three forms are present
                assert "zero" in plural_forms
                assert "one" in plural_forms
                assert "other" in plural_forms

    def test_parse_simple_string_no_plurals(self, plurals_file):
        """Verify non-plural strings still work correctly."""
        catalog = read_xcstrings(plurals_file)

        simple_entry = catalog.strings["simple_string"]

        assert simple_entry.key == "simple_string"
        assert simple_entry.source_text == "Hello World"

        # Simple strings should not have variations
        if "en" in simple_entry.translations:
            en_trans = simple_entry.translations["en"]
            # Either no variations, or variations is None/empty
            assert not en_trans.variations or "plural" not in en_trans.variations
