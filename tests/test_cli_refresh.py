import json
from pathlib import Path

from typer.testing import CliRunner

from localizerx.cli import app

runner = CliRunner()


def test_translate_refresh_removes_stale_and_ignores_translated(tmp_path: Path):
    """Test --refresh option."""
    # Create sample xcstrings file
    sample = {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "hello": {
                "extractionState": "new",
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": "Hello"}}},
            },
            "world": {
                "extractionState": "stale",
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": "World"}}},
            },
            "translated_key": {
                "extractionState": "translated",
                "localizations": {
                    "en": {"stringUnit": {"state": "translated", "value": "Already"}}
                },
            },
        },
    }

    file_path = tmp_path / "Localizable.xcstrings"
    file_path.write_text(json.dumps(sample))

    # Run the refresh dry-run first
    result = runner.invoke(
        app, ["translate", str(file_path), "--to", "fr", "--refresh", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "Would remove 1 stale string(s)" in result.stdout
    assert "Dry run - no changes made" in result.stdout

    # Check dry run output
    assert "hello" in result.stdout  # "hello" should be queued for translation
    assert "world" not in result.stdout  # "world" shouldn't be queued
    assert "translated_key" not in result.stdout  # "translated_key" shouldn't be queued


def test_translate_refresh_removes_stale_saves_when_no_translations(tmp_path: Path):
    """Test --refresh option saves file when no strings to translate but stale strings exist."""
    # Create sample xcstrings file
    sample = {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "world": {
                "extractionState": "stale",
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": "World"}}},
            },
            "translated_key": {
                "extractionState": "translated",
                "localizations": {
                    "en": {"stringUnit": {"state": "translated", "value": "Already"}},
                    "fr": {"stringUnit": {"state": "translated", "value": "Déjà"}},
                },
            },
        },
    }

    file_path = tmp_path / "Localizable.xcstrings"
    file_path.write_text(json.dumps(sample))

    # Run the refresh normally (not dry run)
    result = runner.invoke(app, ["translate", str(file_path), "--to", "fr", "--refresh"])
    assert result.exit_code == 0
    assert "Removed 1 stale string(s)" in result.stdout
    assert "Saved " in result.stdout

    # Verify file content
    content = json.loads(file_path.read_text())
    assert "world" not in content["strings"]
    assert "translated_key" in content["strings"]
