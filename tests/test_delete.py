"""Tests for delete command."""

import json

import pytest

from localizerx.parser.model import Entry, StringCatalog, Translation


@pytest.fixture
def catalog_with_multiple_languages():
    """Create a catalog with translations in multiple languages."""
    catalog = StringCatalog(
        source_language="en",
        strings={
            "hello": Entry(
                key="hello",
                source_text="Hello",
                translations={
                    "fr": Translation(value="Bonjour"),
                    "de": Translation(value="Hallo"),
                    "es": Translation(value="Hola"),
                    "ru": Translation(value="Привет"),
                },
            ),
            "goodbye": Entry(
                key="goodbye",
                source_text="Goodbye",
                translations={
                    "fr": Translation(value="Au revoir"),
                    "de": Translation(value="Auf Wiedersehen"),
                    "es": Translation(value="Adiós"),
                    "ru": Translation(value="До свидания"),
                },
            ),
        },
    )
    # Set raw data to simulate file read
    catalog.set_raw_data(
        {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                        "es": {"stringUnit": {"state": "translated", "value": "Hola"}},
                        "ru": {"stringUnit": {"state": "translated", "value": "Привет"}},
                    }
                },
                "goodbye": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Goodbye"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Au revoir"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Auf Wiedersehen"}},
                        "es": {"stringUnit": {"state": "translated", "value": "Adiós"}},
                        "ru": {"stringUnit": {"state": "translated", "value": "До свидания"}},
                    }
                },
            },
        }
    )
    return catalog


class TestDetermineLanguagesToDelete:
    def test_delete_specific_languages(self, catalog_with_multiple_languages):
        """Test determining languages to delete for specific mode."""
        from localizerx.cli.delete import _determine_languages_to_delete

        # Delete fr and de
        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages="fr,de",
            delete_all=False,
            keep=False,
        )

        assert langs_to_delete == {"fr", "de"}
        assert "en" not in langs_to_delete  # Source protected
        assert "es" not in langs_to_delete
        assert "ru" not in langs_to_delete

    def test_delete_all_languages(self, catalog_with_multiple_languages):
        """Test deleting all languages except source."""
        from localizerx.cli.delete import _determine_languages_to_delete

        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages=None,
            delete_all=True,
            keep=False,
        )

        assert langs_to_delete == {"fr", "de", "es", "ru"}
        assert "en" not in langs_to_delete  # Source protected

    def test_delete_with_keep(self, catalog_with_multiple_languages):
        """Test keeping specific languages, deleting all others."""
        from localizerx.cli.delete import _determine_languages_to_delete

        # Keep only ru and fr, delete de and es
        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages="ru,fr",
            delete_all=False,
            keep=True,
        )

        assert langs_to_delete == {"de", "es"}
        assert "en" not in langs_to_delete  # Source protected
        assert "ru" not in langs_to_delete  # Explicitly kept
        assert "fr" not in langs_to_delete  # Explicitly kept

    def test_protect_source_language(self, catalog_with_multiple_languages):
        """Test that source language is protected from deletion."""
        from localizerx.cli.delete import _determine_languages_to_delete

        # Try to delete source language
        langs_to_delete = _determine_languages_to_delete(
            catalog=catalog_with_multiple_languages,
            languages="en,fr",
            delete_all=False,
            keep=False,
        )

        assert "en" not in langs_to_delete
        assert "fr" in langs_to_delete


class TestDeleteLanguagesFromCatalog:
    def test_delete_languages_from_entries(self, catalog_with_multiple_languages):
        """Test deleting languages from catalog entries."""
        from localizerx.cli.delete import _delete_languages_from_catalog

        langs_to_delete = {"fr", "de"}
        deleted_counts = _delete_languages_from_catalog(
            catalog_with_multiple_languages, langs_to_delete
        )

        # Check counts
        assert deleted_counts == {"fr": 2, "de": 2}  # 2 strings each

        # Check that languages were removed
        for entry in catalog_with_multiple_languages.strings.values():
            assert "fr" not in entry.translations
            assert "de" not in entry.translations
            assert "es" in entry.translations  # Not deleted
            assert "ru" in entry.translations  # Not deleted

    def test_delete_languages_from_raw_data(self, catalog_with_multiple_languages):
        """Test deleting languages from raw_data for lossless write."""
        from localizerx.cli.delete import _delete_languages_from_catalog

        langs_to_delete = {"fr", "de"}
        _delete_languages_from_catalog(catalog_with_multiple_languages, langs_to_delete)

        # Check raw_data
        raw_data = catalog_with_multiple_languages.get_raw_data()
        assert raw_data is not None

        for key, entry_data in raw_data["strings"].items():
            locs = entry_data["localizations"]
            assert "fr" not in locs
            assert "de" not in locs
            assert "es" in locs
            assert "ru" in locs


class TestDeleteIntegration:
    def test_delete_specific_languages_from_file(self, tmp_path):
        """Test deleting specific languages from a real file."""
        # Create test file
        test_file = tmp_path / "test.xcstrings"
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                        "es": {"stringUnit": {"state": "translated", "value": "Hola"}},
                    }
                },
                "goodbye": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Goodbye"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Au revoir"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Auf Wiedersehen"}},
                        "es": {"stringUnit": {"state": "translated", "value": "Adiós"}},
                    }
                }
            }
        }

        with open(test_file, "w") as f:
            json.dump(data, f, indent=2)

        # Read, delete, write
        from localizerx.cli.delete import _process_file
        from localizerx.io.xcstrings import read_xcstrings

        _process_file(
            file_path=test_file,
            languages="fr,de",
            delete_all=False,
            keep=False,
            yes=True,
            backup=False,
        )

        # Verify languages were deleted
        catalog = read_xcstrings(test_file)
        for entry in catalog.strings.values():
            assert "fr" not in entry.translations
            assert "de" not in entry.translations
            assert "es" in entry.translations

        # Verify JSON structure preserved
        with open(test_file) as f:
            result = json.load(f)

        assert result["sourceLanguage"] == "en"
        assert result["version"] == "1.0"
        assert "hello" in result["strings"]
        assert "goodbye" in result["strings"]

    def test_delete_all_except_source(self, tmp_path):
        """Test --all mode."""
        test_file = tmp_path / "test.xcstrings"
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                        "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                    }
                }
            }
        }

        with open(test_file, "w") as f:
            json.dump(data, f, indent=2)

        from localizerx.cli.delete import _process_file
        from localizerx.io.xcstrings import read_xcstrings

        _process_file(
            file_path=test_file,
            languages=None,
            delete_all=True,
            keep=False,
            yes=True,
            backup=False,
        )

        # Verify all languages deleted except source
        catalog = read_xcstrings(test_file)
        for entry in catalog.strings.values():
            assert len(entry.translations) == 0

    def test_delete_with_backup(self, tmp_path):
        """Test backup functionality."""
        test_file = tmp_path / "test.xcstrings"
        data = {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}},
                        "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                    }
                }
            }
        }

        with open(test_file, "w") as f:
            json.dump(data, f, indent=2)

        from localizerx.cli.delete import _process_file

        _process_file(
            file_path=test_file,
            languages="fr",
            delete_all=False,
            keep=False,
            yes=True,
            backup=True,
        )

        # Verify backup was created
        backup_file = test_file.with_suffix(".xcstrings.backup")
        assert backup_file.exists()

        # Verify backup contains original data
        with open(backup_file) as f:
            backup_data = json.load(f)

        assert "fr" in backup_data["strings"]["hello"]["localizations"]
