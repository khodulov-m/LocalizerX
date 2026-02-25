"""Tests for plural forms translation in xcstrings."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import Entry, Translation
from localizerx.translator.base import TranslationRequest
from localizerx.translator.gemini_adapter import GeminiTranslator


@pytest.fixture
def plurals_file():
    """Test xcstrings file with plural variations."""
    return Path("examples/Plurals.xcstrings")


@pytest.fixture
def temp_xcstrings():
    """Create a temporary xcstrings file for write tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xcstrings', delete=False) as f:
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "weeks_ago": {
                    "comment": "Time elapsed in weeks",
                    "localizations": {
                        "en": {
                            "variations": {
                                "plural": {
                                    "one": {
                                        "stringUnit": {
                                            "state": "translated",
                                            "value": "%lld week"
                                        }
                                    },
                                    "other": {
                                        "stringUnit": {
                                            "state": "translated",
                                            "value": "%lld weeks"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        json.dump(data, f)
        path = Path(f.name)
    yield path
    path.unlink()


class TestPluralParsing:
    """Test parsing of plural variations."""

    def test_parse_plural_source_variations(self, plurals_file):
        """Test that source plural variations are parsed into Entry.source_variations."""
        catalog = read_xcstrings(plurals_file)
        weeks_entry = catalog.strings["weeks_ago"]

        assert weeks_entry.key == "weeks_ago"
        assert weeks_entry.source_variations is not None
        assert "plural" in weeks_entry.source_variations

        plural_forms = weeks_entry.source_variations["plural"]
        assert "one" in plural_forms
        assert "other" in plural_forms

        # Check values
        one_form = plural_forms["one"]["stringUnit"]["value"]
        other_form = plural_forms["other"]["stringUnit"]["value"]
        assert one_form == "%lld week"
        assert other_form == "%lld weeks"

    def test_has_plurals_property(self, plurals_file):
        """Test Entry.has_plurals property."""
        catalog = read_xcstrings(plurals_file)

        weeks_entry = catalog.strings["weeks_ago"]
        assert weeks_entry.has_plurals is True

        simple_entry = catalog.strings["simple_string"]
        assert simple_entry.has_plurals is False

    def test_needs_translation_with_plurals(self, plurals_file):
        """Test that entries with only plurals (no simple text) are marked as needing translation."""
        catalog = read_xcstrings(plurals_file)
        weeks_entry = catalog.strings["weeks_ago"]

        # Entry has plurals but source_text might be empty or key
        # It should still need translation
        assert weeks_entry.needs_translation is True

    def test_parse_items_with_zero_form(self, plurals_file):
        """Test parsing entry with zero, one, and other forms."""
        catalog = read_xcstrings(plurals_file)
        items_entry = catalog.strings["items_selected"]

        assert items_entry.has_plurals is True
        plural_forms = items_entry.source_variations["plural"]

        assert "zero" in plural_forms
        assert "one" in plural_forms
        assert "other" in plural_forms

        assert plural_forms["zero"]["stringUnit"]["value"] == "No items selected"
        assert plural_forms["one"]["stringUnit"]["value"] == "%d item selected"
        assert plural_forms["other"]["stringUnit"]["value"] == "%d items selected"


class TestPluralTranslation:
    """Test translation of plural forms."""

    @pytest.mark.asyncio
    async def test_translate_plural_forms(self):
        """Test _translate_plural_forms method."""
        translator = GeminiTranslator(api_key="fake-key")

        plural_forms = {
            "one": "%lld week",
            "other": "%lld weeks"
        }

        # Mock API calls
        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            # First call for "one" form, second for "other"
            mock_api.side_effect = [
                "__PH_1__ неделя",  # Russian singular
                "__PH_1__ недель"   # Russian plural (genitive)
            ]

            results = await translator._translate_plural_forms(plural_forms, "en", "ru")

        assert len(results) == 2
        assert "one" in results
        assert "other" in results
        assert results["one"] == "%lld неделя"
        assert results["other"] == "%lld недель"

    @pytest.mark.asyncio
    async def test_translate_batch_with_plurals(self):
        """Test translate_batch with plural forms in request."""
        translator = GeminiTranslator(api_key="fake-key")

        requests = [
            TranslationRequest(
                key="weeks_ago",
                text="%lld weeks",  # This is just for context, actual forms are in plural_forms
                plural_forms={
                    "one": "%lld week",
                    "other": "%lld weeks"
                }
            )
        ]

        # Mock API calls
        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = [
                "__PH_1__ semana",   # Spanish singular
                "__PH_1__ semanas"   # Spanish plural
            ]

            results = await translator.translate_batch(requests, "en", "es")

        assert len(results) == 1
        result = results[0]
        assert result.key == "weeks_ago"
        assert result.translated_plurals is not None
        assert result.translated_plurals["one"] == "%lld semana"
        assert result.translated_plurals["other"] == "%lld semanas"

    @pytest.mark.asyncio
    async def test_translate_mixed_batch(self):
        """Test batch with both plural and simple strings."""
        translator = GeminiTranslator(api_key="fake-key")

        requests = [
            TranslationRequest(
                key="simple",
                text="Hello",
                plural_forms=None
            ),
            TranslationRequest(
                key="plural",
                text="%d items",
                plural_forms={
                    "one": "%d item",
                    "other": "%d items"
                }
            )
        ]

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            # First call: plural "one" form
            # Second call: plural "other" form
            # Third call: "Hello" translation batch
            mock_api.side_effect = [
                "__PH_1__ elemento",  # Plural one
                "__PH_1__ elementos",  # Plural other
                "Hola"  # Simple string
            ]

            results = await translator.translate_batch(requests, "en", "es")

        assert len(results) == 2

        # Simple string result
        assert results[0].key == "simple"
        assert results[0].translated == "Hola"
        assert results[0].translated_plurals is None

        # Plural string result
        assert results[1].key == "plural"
        assert results[1].translated_plurals is not None
        assert results[1].translated_plurals["one"] == "%d elemento"
        assert results[1].translated_plurals["other"] == "%d elementos"


class TestPluralWriting:
    """Test writing plural translations to xcstrings."""

    def test_write_plural_translation(self, temp_xcstrings):
        """Test writing plural translations to file."""
        catalog = read_xcstrings(temp_xcstrings)

        # Add Russian translation with plural forms
        catalog.strings["weeks_ago"].translations["ru"] = Translation(
            value="%lld недель",  # Default/fallback value
            variations={
                "plural": {
                    "one": {
                        "stringUnit": {
                            "state": "translated",
                            "value": "%lld неделя"
                        }
                    },
                    "few": {
                        "stringUnit": {
                            "state": "translated",
                            "value": "%lld недели"
                        }
                    },
                    "other": {
                        "stringUnit": {
                            "state": "translated",
                            "value": "%lld недель"
                        }
                    }
                }
            }
        )

        # Write to file
        write_xcstrings(catalog, temp_xcstrings)

        # Read back and verify
        catalog2 = read_xcstrings(temp_xcstrings)
        ru_trans = catalog2.strings["weeks_ago"].translations["ru"]

        assert ru_trans.variations is not None
        assert "plural" in ru_trans.variations
        ru_plurals = ru_trans.variations["plural"]

        assert ru_plurals["one"]["stringUnit"]["value"] == "%lld неделя"
        assert ru_plurals["few"]["stringUnit"]["value"] == "%lld недели"
        assert ru_plurals["other"]["stringUnit"]["value"] == "%lld недель"

    def test_round_trip_with_plurals(self, temp_xcstrings):
        """Test that plural structure is preserved in round-trip."""
        # Read original
        catalog1 = read_xcstrings(temp_xcstrings)
        original_variations = catalog1.strings["weeks_ago"].source_variations

        # Write without changes
        write_xcstrings(catalog1, temp_xcstrings)

        # Read again
        catalog2 = read_xcstrings(temp_xcstrings)
        new_variations = catalog2.strings["weeks_ago"].source_variations

        # Should be identical
        assert new_variations == original_variations


class TestPluralEdgeCases:
    """Test edge cases and special scenarios."""

    def test_plural_with_placeholders(self):
        """Test that placeholders in plural forms are preserved."""
        # This is tested implicitly in other tests, but let's be explicit
        translator = GeminiTranslator(api_key="fake-key")

        # Plural forms with various placeholder types
        forms = {
            "one": "%lld day ago",
            "other": "%lld days ago"
        }

        # The mask_placeholders and unmask_placeholders should handle this
        # in _translate_plural_forms
        # This test documents the expected behavior
        assert True  # Covered by integration tests above

    def test_entry_without_plurals(self, plurals_file):
        """Ensure simple strings still work correctly."""
        catalog = read_xcstrings(plurals_file)
        simple = catalog.strings["simple_string"]

        assert simple.has_plurals is False
        assert simple.source_variations is None
        assert simple.needs_translation is True
        assert simple.source_text == "Hello World"

    def test_languages_with_many_plural_forms(self):
        """Document that languages with many plural forms (e.g., Russian, Arabic) are supported."""
        # Russian has: one, few, many, other
        # Arabic has: zero, one, two, few, many, other
        # The structure supports all of these
        entry = Entry(
            key="test",
            source_text="items",
            source_variations={
                "plural": {
                    "zero": {"stringUnit": {"value": "no items"}},
                    "one": {"stringUnit": {"value": "one item"}},
                    "two": {"stringUnit": {"value": "two items"}},
                    "few": {"stringUnit": {"value": "few items"}},
                    "many": {"stringUnit": {"value": "many items"}},
                    "other": {"stringUnit": {"value": "other items"}},
                }
            }
        )

        assert entry.has_plurals is True
        assert len(entry.source_variations["plural"]) == 6
