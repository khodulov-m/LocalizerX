"""Tests for screenshots I/O operations."""

import json
import tempfile
from pathlib import Path

import pytest

from localizerx.io.screenshots import (
    create_screenshots_template,
    detect_screenshots_path,
    get_default_screenshots_path,
    read_screenshots,
    screenshots_file_exists,
    write_screenshots,
)
from localizerx.parser.screenshots_model import (
    ScreenshotsCatalog,
    ScreenshotText,
    ScreenshotTextType,
)


@pytest.fixture
def sample_screenshots_json():
    """Return sample screenshots JSON structure."""
    return {
        "sourceLanguage": "en",
        "screens": {
            "screen_1": {
                "headline": {"small": "Track Habits", "large": "Track Your Daily Habits"},
                "subtitle": {"small": "Stay motivated", "large": "Stay motivated every day"},
            },
            "screen_2": {
                "headline": {"small": "Set Goals", "large": "Set Personal Goals"},
            },
        },
        "localizations": {
            "de": {
                "screen_1": {
                    "headline": {
                        "small": "Gewohnheiten tracken",
                        "large": "Tägliche Gewohnheiten tracken",
                    },
                },
            },
        },
    }


@pytest.fixture
def sample_screenshots_file(sample_screenshots_json):
    """Create a temporary screenshots file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "screenshots" / "texts.json"
        filepath.parent.mkdir(parents=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sample_screenshots_json, f, indent=2)

        yield filepath


@pytest.fixture
def empty_dir():
    """Create an empty temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestReadScreenshots:
    def test_read_basic(self, sample_screenshots_file):
        catalog = read_screenshots(sample_screenshots_file)

        assert catalog.source_language == "en"
        assert catalog.screen_count == 2
        assert catalog.locale_count == 1

    def test_read_source_screens(self, sample_screenshots_file):
        catalog = read_screenshots(sample_screenshots_file)

        screen1 = catalog.get_source_screen("screen_1")
        assert screen1 is not None
        assert screen1.text_count == 2

        headline = screen1.get_text(ScreenshotTextType.HEADLINE)
        assert headline is not None
        assert headline.small == "Track Habits"
        assert headline.large == "Track Your Daily Habits"

    def test_read_localizations(self, sample_screenshots_file):
        catalog = read_screenshots(sample_screenshots_file)

        de = catalog.get_locale("de")
        assert de is not None
        assert de.screen_count == 1

        de_screen = de.get_screen("screen_1")
        assert de_screen is not None

        headline = de_screen.get_text(ScreenshotTextType.HEADLINE)
        assert headline is not None
        assert headline.small == "Gewohnheiten tracken"

    def test_read_nonexistent_file(self, empty_dir):
        with pytest.raises(FileNotFoundError):
            read_screenshots(empty_dir / "texts.json")

    def test_read_preserves_raw_data(self, sample_screenshots_file):
        catalog = read_screenshots(sample_screenshots_file)

        raw = catalog.get_raw_data()
        assert raw is not None
        assert "sourceLanguage" in raw
        assert "screens" in raw


class TestWriteScreenshots:
    def test_write_basic(self, sample_screenshots_file):
        catalog = read_screenshots(sample_screenshots_file)

        # Add new translation
        fr = catalog.get_or_create_locale("fr")
        fr_screen = fr.get_or_create_screen("screen_1")
        fr_screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="Suivre les habitudes"),
        )

        # Write back
        write_screenshots(catalog, sample_screenshots_file, backup=False)

        # Verify
        with open(sample_screenshots_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "fr" in data["localizations"]
        assert (
            data["localizations"]["fr"]["screen_1"]["headline"]["small"] == "Suivre les habitudes"
        )

    def test_write_creates_backup(self, sample_screenshots_file):
        catalog = read_screenshots(sample_screenshots_file)

        write_screenshots(catalog, sample_screenshots_file, backup=True)

        backup_path = sample_screenshots_file.with_suffix(".json.backup")
        assert backup_path.exists()

    def test_write_creates_parent_dirs(self, empty_dir):
        filepath = empty_dir / "deep" / "path" / "texts.json"

        catalog = ScreenshotsCatalog(source_language="en")
        screen = catalog.get_or_create_source_screen("screen_1")
        screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Test"))

        write_screenshots(catalog, filepath, backup=False)

        assert filepath.exists()

    def test_write_preserves_structure(self, sample_screenshots_file, sample_screenshots_json):
        """Read and write should preserve unknown keys in original structure."""
        catalog = read_screenshots(sample_screenshots_file)

        # Just write back without changes
        write_screenshots(catalog, sample_screenshots_file, backup=False)

        # Verify core structure is preserved
        with open(sample_screenshots_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["sourceLanguage"] == sample_screenshots_json["sourceLanguage"]
        assert "screen_1" in data["screens"]
        assert "screen_2" in data["screens"]


class TestRoundTrip:
    def test_lossless_round_trip(self, sample_screenshots_file):
        """Read → write → read should produce equivalent data."""
        catalog1 = read_screenshots(sample_screenshots_file)

        write_screenshots(catalog1, sample_screenshots_file, backup=False)

        catalog2 = read_screenshots(sample_screenshots_file)

        assert catalog1.source_language == catalog2.source_language
        assert catalog1.screen_count == catalog2.screen_count
        assert catalog1.locale_count == catalog2.locale_count

    def test_round_trip_with_additions(self, sample_screenshots_file):
        """Round trip with new translations should preserve everything."""
        catalog = read_screenshots(sample_screenshots_file)

        # Add translation
        fr = catalog.get_or_create_locale("fr")
        fr_screen = fr.get_or_create_screen("screen_1")
        fr_screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="Bonjour", large="Bonjour le monde"),
        )

        write_screenshots(catalog, sample_screenshots_file, backup=False)

        catalog2 = read_screenshots(sample_screenshots_file)

        # Original data preserved
        assert catalog2.screen_count == 2
        assert "de" in catalog2.localizations

        # New data present
        fr2 = catalog2.get_locale("fr")
        assert fr2 is not None
        fr_headline = fr2.get_screen("screen_1").get_text(ScreenshotTextType.HEADLINE)
        assert fr_headline.small == "Bonjour"


class TestDetectScreenshotsPath:
    def test_detect_in_screenshots_dir(self, empty_dir):
        # Create screenshots/texts.json
        screenshots_dir = empty_dir / "screenshots"
        screenshots_dir.mkdir()
        filepath = screenshots_dir / "texts.json"
        filepath.write_text('{"sourceLanguage": "en", "screens": {}}')

        result = detect_screenshots_path(empty_dir)
        assert result == filepath

    def test_detect_in_current_dir(self, empty_dir):
        # Create texts.json directly in dir
        filepath = empty_dir / "texts.json"
        filepath.write_text('{"sourceLanguage": "en", "screens": {}}')

        result = detect_screenshots_path(empty_dir)
        assert result == filepath

    def test_detect_returns_none_when_not_found(self, empty_dir):
        result = detect_screenshots_path(empty_dir)
        assert result is None


class TestGetDefaultScreenshotsPath:
    def test_default_path(self, empty_dir):
        path = get_default_screenshots_path(empty_dir)
        assert path == empty_dir / "screenshots" / "texts.json"


class TestCreateScreenshotsTemplate:
    def test_create_basic(self, empty_dir):
        filepath = empty_dir / "screenshots" / "texts.json"

        catalog = create_screenshots_template(filepath)

        assert filepath.exists()
        assert catalog.source_language == "en"
        assert catalog.screen_count == 2

    def test_create_custom_source_language(self, empty_dir):
        filepath = empty_dir / "texts.json"

        catalog = create_screenshots_template(filepath, source_language="ru")

        assert catalog.source_language == "ru"

        # Verify file content
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["sourceLanguage"] == "ru"

    def test_create_template_structure(self, empty_dir):
        filepath = empty_dir / "texts.json"

        create_screenshots_template(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify template structure
        assert "screens" in data
        assert "screen_1" in data["screens"]
        assert "headline" in data["screens"]["screen_1"]
        assert "small" in data["screens"]["screen_1"]["headline"]
        assert "large" in data["screens"]["screen_1"]["headline"]


class TestScreenshotsFileExists:
    def test_exists_with_explicit_path(self, sample_screenshots_file):
        assert screenshots_file_exists(sample_screenshots_file)

    def test_not_exists_with_explicit_path(self, empty_dir):
        assert not screenshots_file_exists(empty_dir / "nonexistent.json")

    def test_auto_detect_exists(self, sample_screenshots_file):
        assert screenshots_file_exists() is False  # No auto-detect from cwd


class TestEdgeCases:
    def test_read_empty_screens(self, empty_dir):
        filepath = empty_dir / "texts.json"
        data = {"sourceLanguage": "en", "screens": {}}

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        catalog = read_screenshots(filepath)
        assert catalog.screen_count == 0

    def test_read_unknown_text_type(self, empty_dir):
        """Unknown text types should be skipped."""
        filepath = empty_dir / "texts.json"
        data = {
            "sourceLanguage": "en",
            "screens": {
                "screen_1": {
                    "headline": {"small": "Test"},
                    "unknown_type": {"small": "Should be ignored"},
                },
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        catalog = read_screenshots(filepath)
        screen = catalog.get_source_screen("screen_1")
        assert screen.text_count == 1  # Only headline

    def test_write_adds_trailing_newline(self, empty_dir):
        filepath = empty_dir / "texts.json"

        catalog = ScreenshotsCatalog(source_language="en")
        write_screenshots(catalog, filepath, backup=False)

        content = filepath.read_text()
        assert content.endswith("\n")
