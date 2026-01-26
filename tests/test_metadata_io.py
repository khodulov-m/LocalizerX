"""Tests for metadata I/O."""

import tempfile
from pathlib import Path

import pytest

from localizerx.io.metadata import (
    detect_metadata_path,
    get_available_locales,
    get_locale_fields,
    read_metadata,
    write_metadata,
)
from localizerx.parser.metadata_model import MetadataFieldType


@pytest.fixture
def sample_metadata_dir():
    """Create a temporary metadata directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create en-US locale
        en_dir = tmpdir / "en-US"
        en_dir.mkdir()
        (en_dir / "name.txt").write_text("My Awesome App\n")
        (en_dir / "subtitle.txt").write_text("The best app ever\n")
        (en_dir / "keywords.txt").write_text("app,awesome,productivity\n")
        (en_dir / "description.txt").write_text("This is my awesome app.\n")
        (en_dir / "promotional_text.txt").write_text("Check out our new feature!\n")
        (en_dir / "release_notes.txt").write_text("- Bug fixes\n- New feature\n")

        # Create de-DE locale with partial content
        de_dir = tmpdir / "de-DE"
        de_dir.mkdir()
        (de_dir / "name.txt").write_text("Meine tolle App\n")

        yield tmpdir


@pytest.fixture
def empty_metadata_dir():
    """Create an empty temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestReadMetadata:
    def test_read_basic(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)
        assert catalog.source_locale == "en-US"
        assert catalog.locale_count == 2
        assert "en-US" in catalog.locales
        assert "de-DE" in catalog.locales

    def test_read_fields(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)
        source = catalog.get_source_metadata()

        assert source is not None
        assert source.field_count == 6

        name_field = source.get_field(MetadataFieldType.NAME)
        assert name_field is not None
        assert name_field.content == "My Awesome App"

        keywords = source.get_field(MetadataFieldType.KEYWORDS)
        assert keywords is not None
        assert "productivity" in keywords.content

    def test_read_partial_locale(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)
        de = catalog.get_locale("de-DE")

        assert de is not None
        assert de.field_count == 1
        assert de.has_field(MetadataFieldType.NAME)
        assert not de.has_field(MetadataFieldType.SUBTITLE)

    def test_read_custom_source_locale(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir, source_locale="de-DE")
        assert catalog.source_locale == "de-DE"

    def test_read_nonexistent_directory(self, empty_metadata_dir):
        nonexistent = empty_metadata_dir / "doesnt_exist"
        with pytest.raises(FileNotFoundError):
            read_metadata(nonexistent)

    def test_read_file_instead_of_directory(self, sample_metadata_dir):
        file_path = sample_metadata_dir / "en-US" / "name.txt"
        with pytest.raises(ValueError):
            read_metadata(file_path)


class TestWriteMetadata:
    def test_write_basic(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)

        # Add a new field to German
        de = catalog.get_or_create_locale("de-DE")
        de.set_field(MetadataFieldType.SUBTITLE, "Die beste App")

        # Write back
        write_metadata(catalog, sample_metadata_dir, backup=False)

        # Verify
        subtitle_file = sample_metadata_dir / "de-DE" / "subtitle.txt"
        assert subtitle_file.exists()
        assert subtitle_file.read_text().strip() == "Die beste App"

    def test_write_creates_locale_dir(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)

        # Add new locale
        fr = catalog.get_or_create_locale("fr-FR")
        fr.set_field(MetadataFieldType.NAME, "Mon Application")

        write_metadata(catalog, sample_metadata_dir, backup=False, locales=["fr-FR"])

        # Verify
        fr_dir = sample_metadata_dir / "fr-FR"
        assert fr_dir.exists()
        assert (fr_dir / "name.txt").read_text().strip() == "Mon Application"

    def test_write_creates_backup(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)
        de = catalog.get_locale("de-DE")
        de.set_field(MetadataFieldType.NAME, "Updated Name")

        write_metadata(catalog, sample_metadata_dir, backup=True, locales=["de-DE"])

        backup_file = sample_metadata_dir / "de-DE" / "name.txt.backup"
        assert backup_file.exists()
        assert backup_file.read_text().strip() == "Meine tolle App"

    def test_write_specific_locales(self, sample_metadata_dir):
        catalog = read_metadata(sample_metadata_dir)

        # Add new locale
        fr = catalog.get_or_create_locale("fr-FR")
        fr.set_field(MetadataFieldType.NAME, "Mon App")

        ja = catalog.get_or_create_locale("ja")
        ja.set_field(MetadataFieldType.NAME, "私のアプリ")

        # Only write fr-FR
        write_metadata(catalog, sample_metadata_dir, backup=False, locales=["fr-FR"])

        assert (sample_metadata_dir / "fr-FR" / "name.txt").exists()
        assert not (sample_metadata_dir / "ja").exists()


class TestRoundTrip:
    def test_lossless_round_trip(self, sample_metadata_dir):
        """Read and write should preserve content."""
        # Read original
        original_content = (sample_metadata_dir / "en-US" / "name.txt").read_text()

        # Round trip
        catalog = read_metadata(sample_metadata_dir)
        write_metadata(catalog, sample_metadata_dir, backup=False)

        # Compare
        after_content = (sample_metadata_dir / "en-US" / "name.txt").read_text()
        assert after_content.strip() == original_content.strip()


class TestDetectMetadataPath:
    def test_detect_in_fastlane(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            metadata_dir = tmpdir / "fastlane" / "metadata"
            metadata_dir.mkdir(parents=True)

            # Create minimal structure
            en_dir = metadata_dir / "en-US"
            en_dir.mkdir()
            (en_dir / "name.txt").write_text("Test")

            result = detect_metadata_path(tmpdir)
            assert result == metadata_dir

    def test_detect_in_current_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            metadata_dir = tmpdir / "metadata"
            metadata_dir.mkdir()

            # Create minimal structure
            en_dir = metadata_dir / "en-US"
            en_dir.mkdir()
            (en_dir / "name.txt").write_text("Test")

            result = detect_metadata_path(tmpdir)
            assert result == metadata_dir

    def test_detect_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_metadata_path(Path(tmpdir))
            assert result is None


class TestGetAvailableLocales:
    def test_get_locales(self, sample_metadata_dir):
        locales = get_available_locales(sample_metadata_dir)
        assert "en-US" in locales
        assert "de-DE" in locales

    def test_get_locales_empty_dir(self, empty_metadata_dir):
        locales = get_available_locales(empty_metadata_dir)
        assert locales == []

    def test_get_locales_nonexistent(self):
        locales = get_available_locales(Path("/nonexistent"))
        assert locales == []


class TestGetLocaleFields:
    def test_get_fields(self, sample_metadata_dir):
        fields = get_locale_fields(sample_metadata_dir, "en-US")
        assert MetadataFieldType.NAME in fields
        assert MetadataFieldType.SUBTITLE in fields
        assert MetadataFieldType.KEYWORDS in fields
        assert len(fields) == 6

    def test_get_fields_partial(self, sample_metadata_dir):
        fields = get_locale_fields(sample_metadata_dir, "de-DE")
        assert MetadataFieldType.NAME in fields
        assert len(fields) == 1

    def test_get_fields_nonexistent_locale(self, sample_metadata_dir):
        fields = get_locale_fields(sample_metadata_dir, "fr-FR")
        assert fields == []
