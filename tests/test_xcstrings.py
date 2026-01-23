"""Tests for xcstrings I/O."""

import json
import tempfile
from pathlib import Path

import pytest

from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.parser.model import Translation


@pytest.fixture
def sample_xcstrings():
    """Sample xcstrings content for testing."""
    return {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "hello": {
                "comment": "Greeting message",
                "extractionState": "manual",
                "localizations": {
                    "en": {
                        "stringUnit": {
                            "state": "translated",
                            "value": "Hello"
                        }
                    }
                }
            },
            "goodbye": {
                "localizations": {
                    "en": {
                        "stringUnit": {
                            "state": "translated",
                            "value": "Goodbye"
                        }
                    },
                    "es": {
                        "stringUnit": {
                            "state": "translated",
                            "value": "Adiós"
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def xcstrings_file(sample_xcstrings):
    """Create a temporary xcstrings file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xcstrings", delete=False
    ) as f:
        json.dump(sample_xcstrings, f)
        f.flush()
        yield Path(f.name)


class TestReadXcstrings:
    def test_read_basic(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)
        assert catalog.source_language == "en"
        assert catalog.version == "1.0"
        assert len(catalog.strings) == 2

    def test_read_entry_properties(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)
        hello = catalog.strings["hello"]
        assert hello.key == "hello"
        assert hello.source_text == "Hello"
        assert hello.comment == "Greeting message"

    def test_read_existing_translation(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)
        goodbye = catalog.strings["goodbye"]
        assert "es" in goodbye.translations
        assert goodbye.translations["es"].value == "Adiós"


class TestWriteXcstrings:
    def test_write_preserves_structure(self, xcstrings_file, sample_xcstrings):
        catalog = read_xcstrings(xcstrings_file)

        # Write back without changes
        write_xcstrings(catalog, xcstrings_file)

        # Read the file back
        with open(xcstrings_file) as f:
            written = json.load(f)

        # Core structure should be preserved
        assert written["sourceLanguage"] == sample_xcstrings["sourceLanguage"]
        assert written["version"] == sample_xcstrings["version"]
        assert "hello" in written["strings"]
        assert "goodbye" in written["strings"]

    def test_write_adds_translation(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)

        # Add a new translation
        catalog.strings["hello"].translations["fr"] = Translation(
            value="Bonjour", state="translated"
        )

        write_xcstrings(catalog, xcstrings_file)

        # Verify it was written
        with open(xcstrings_file) as f:
            written = json.load(f)

        assert "fr" in written["strings"]["hello"]["localizations"]
        fr_loc = written["strings"]["hello"]["localizations"]["fr"]
        assert fr_loc["stringUnit"]["value"] == "Bonjour"

    def test_write_creates_backup(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)
        write_xcstrings(catalog, xcstrings_file, backup=True)

        backup_path = xcstrings_file.with_suffix(".xcstrings.backup")
        assert backup_path.exists()


class TestRoundTrip:
    def test_lossless_round_trip(self, xcstrings_file):
        """Reading and writing should preserve the original structure."""
        # Read original
        with open(xcstrings_file) as f:
            original = json.load(f)

        # Round trip
        catalog = read_xcstrings(xcstrings_file)
        write_xcstrings(catalog, xcstrings_file)

        # Compare
        with open(xcstrings_file) as f:
            after = json.load(f)

        # Structure should match
        assert after["sourceLanguage"] == original["sourceLanguage"]
        assert after["version"] == original["version"]
        assert set(after["strings"].keys()) == set(original["strings"].keys())


class TestEntryHelpers:
    def test_needs_translation(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)

        # Hello doesn't have French
        entries = catalog.get_entries_needing_translation("fr")
        assert any(e.key == "hello" for e in entries)

        # Goodbye already has Spanish
        entries = catalog.get_entries_needing_translation("es")
        assert not any(e.key == "goodbye" for e in entries)

    def test_get_all_translatable(self, xcstrings_file):
        catalog = read_xcstrings(xcstrings_file)
        entries = catalog.get_all_translatable_entries()
        assert len(entries) == 2
