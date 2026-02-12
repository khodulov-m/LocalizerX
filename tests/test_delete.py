"""Tests for delete command."""

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
                }
            ),
            "goodbye": Entry(
                key="goodbye",
                source_text="Goodbye",
                translations={
                    "fr": Translation(value="Au revoir"),
                    "de": Translation(value="Auf Wiedersehen"),
                    "es": Translation(value="Adiós"),
                    "ru": Translation(value="До свидания"),
                }
            ),
        }
    )
    # Set raw data to simulate file read
    catalog.set_raw_data({
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
            }
        }
    })
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
