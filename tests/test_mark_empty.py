"""Tests for --mark-empty feature."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from localizerx.cli import app
from localizerx.io.xcstrings import read_xcstrings

runner = CliRunner()


@pytest.fixture
def mock_translator():
    """Mock GeminiTranslator to avoid real API calls."""
    with patch("localizerx.cli.translate.GeminiTranslator") as mock:
        translator_instance = mock.return_value
        translator_instance.__aenter__.return_value = translator_instance
        translator_instance.__aexit__.return_value = None

        # Mock translate_batch to return success results
        async def mock_translate_batch(requests, src, target):
            from localizerx.translator.base import TranslationResult

            results = []
            for r in requests:
                results.append(
                    TranslationResult(
                        key=r.key, original=r.text, translated=f"Translated-{r.text}", success=True
                    )
                )
            return results

        translator_instance.translate_batch = mock_translate_batch
        yield translator_instance


@pytest.fixture
def xcstrings_with_empty():
    """Sample xcstrings with empty and whitespace strings."""
    return {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "hello": {
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": "Hello"}}}
            },
            "empty": {
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": ""}}}
            },
            "space": {
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": " "}}}
            },
        },
    }


def test_mark_empty_flag(xcstrings_with_empty, mock_translator):
    """Test that --mark-empty marks empty/whitespace strings as translated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        file_path = tmpdir / "Localizable.xcstrings"
        file_path.write_text(json.dumps(xcstrings_with_empty))

        # Run translate with --mark-empty for French
        # Use --dry-run first to check output
        result = runner.invoke(
            app, ["translate", str(file_path), "--to", "fr", "--mark-empty", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Would mark 2 empty/whitespace string(s)" in result.stdout

        # Run without --dry-run
        result = runner.invoke(app, ["translate", str(file_path), "--to", "fr", "--mark-empty"])
        assert result.exit_code == 0
        assert "Marked 2 empty/whitespace string(s)" in result.stdout

        # Verify file content
        catalog = read_xcstrings(file_path)

        # 'hello' should have its translation from the mock
        assert "fr" in catalog.strings["hello"].translations
        assert catalog.strings["hello"].translations["fr"].value == "Translated-Hello"

        # 'empty' should HAVE 'fr' with empty value (from mark-empty logic, NOT translation)
        assert "fr" in catalog.strings["empty"].translations
        assert catalog.strings["empty"].translations["fr"].value == ""
        assert catalog.strings["empty"].translations["fr"].state == "translated"

        # 'space' should HAVE 'fr' with space value (from mark-empty logic, NOT translation)
        assert "fr" in catalog.strings["space"].translations
        assert catalog.strings["space"].translations["fr"].value == " "
        assert catalog.strings["space"].translations["fr"].state == "translated"


def test_mark_empty_respects_overwrite(xcstrings_with_empty, mock_translator):
    """Test that --mark-empty respects --overwrite flag."""
    # Add an existing translation for 'empty'
    xcstrings_with_empty["strings"]["empty"]["localizations"]["fr"] = {
        "stringUnit": {"state": "translated", "value": "Existing"}
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        file_path = tmpdir / "Localizable.xcstrings"
        file_path.write_text(json.dumps(xcstrings_with_empty))

        # Run without overwrite - should only mark 1 (the space one)
        result = runner.invoke(app, ["translate", str(file_path), "--to", "fr", "--mark-empty"])
        assert "Marked 1 empty/whitespace string(s)" in result.stdout

        catalog = read_xcstrings(file_path)
        assert catalog.strings["empty"].translations["fr"].value == "Existing"

        # Run with overwrite - should mark both
        result = runner.invoke(
            app, ["translate", str(file_path), "--to", "fr", "--mark-empty", "--overwrite"]
        )
        assert "Marked 2 empty/whitespace string(s)" in result.stdout

        catalog = read_xcstrings(file_path)
        assert catalog.strings["empty"].translations["fr"].value == ""


def test_mark_empty_multiple_targets(xcstrings_with_empty, mock_translator):
    """Test --mark-empty with multiple target languages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        file_path = tmpdir / "Localizable.xcstrings"
        file_path.write_text(json.dumps(xcstrings_with_empty))

        # Run for fr, es
        result = runner.invoke(app, ["translate", str(file_path), "--to", "fr,es", "--mark-empty"])
        assert "Marked 4 empty/whitespace string(s)" in result.stdout  # 2 strings * 2 languages

        catalog = read_xcstrings(file_path)
        assert "fr" in catalog.strings["empty"].translations
        assert "es" in catalog.strings["empty"].translations
        assert "fr" in catalog.strings["space"].translations
        assert "es" in catalog.strings["space"].translations


def test_mark_empty_only(xcstrings_with_empty, mock_translator):
    """Test --mark-empty when no other strings need translation."""
    # Pre-translate 'hello'
    xcstrings_with_empty["strings"]["hello"]["localizations"]["fr"] = {
        "stringUnit": {"state": "translated", "value": "Bonjour"}
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        file_path = tmpdir / "Localizable.xcstrings"
        file_path.write_text(json.dumps(xcstrings_with_empty))

        # Run translate with --mark-empty
        # 'hello' is already translated, so translation_tasks will be empty
        result = runner.invoke(app, ["translate", str(file_path), "--to", "fr", "--mark-empty"])
        assert "Marked 2 empty/whitespace string(s)" in result.stdout
        assert "Saved " in result.stdout

        catalog = read_xcstrings(file_path)
        assert "fr" in catalog.strings["empty"].translations
        assert catalog.strings["empty"].translations["fr"].value == ""
