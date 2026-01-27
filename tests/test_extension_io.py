"""Tests for Chrome Extension I/O."""

import json
import tempfile
from pathlib import Path

import pytest

from localizerx.io.extension import (
    detect_extension_path,
    read_extension,
    write_extension,
)


@pytest.fixture
def sample_locales_dir():
    """Create a temporary _locales/ directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        locales_dir = tmpdir / "_locales"
        locales_dir.mkdir()

        # Create en locale
        en_dir = locales_dir / "en"
        en_dir.mkdir()
        en_messages = {
            "appName": {
                "message": "My Extension",
                "description": "The name of the extension",
            },
            "appDesc": {
                "message": "A great Chrome extension for productivity",
                "description": "Description for Chrome Web Store",
            },
            "shortName": {
                "message": "MyExt",
            },
            "greeting": {
                "message": "Hello $USER$!",
                "description": "Greeting shown to user",
                "placeholders": {
                    "user": {
                        "content": "$1",
                        "example": "John",
                    }
                },
            },
        }
        (en_dir / "messages.json").write_text(json.dumps(en_messages, indent=2, ensure_ascii=False))

        # Create fr locale with partial content
        fr_dir = locales_dir / "fr"
        fr_dir.mkdir()
        fr_messages = {
            "appName": {
                "message": "Mon Extension",
                "description": "The name of the extension",
            },
        }
        (fr_dir / "messages.json").write_text(json.dumps(fr_messages, indent=2, ensure_ascii=False))

        yield locales_dir


@pytest.fixture
def empty_dir():
    """Create an empty temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestReadExtension:
    def test_read_basic(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)
        assert catalog.source_locale == "en"
        assert catalog.locale_count == 2
        assert "en" in catalog.locales
        assert "fr" in catalog.locales

    def test_read_messages(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)
        source = catalog.get_source_locale()

        assert source is not None
        assert source.field_count == 4

        app_name = source.get_message("appName")
        assert app_name is not None
        assert app_name.message == "My Extension"
        assert app_name.description == "The name of the extension"

    def test_read_placeholders(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)
        source = catalog.get_source_locale()

        greeting = source.get_message("greeting")
        assert greeting is not None
        assert greeting.placeholders is not None
        assert "user" in greeting.placeholders
        assert greeting.placeholders["user"]["content"] == "$1"

    def test_read_partial_locale(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)
        fr = catalog.get_locale("fr")

        assert fr is not None
        assert fr.field_count == 1
        assert fr.get_message("appName") is not None
        assert fr.get_message("greeting") is None

    def test_read_custom_source_locale(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir, source_locale="fr")
        assert catalog.source_locale == "fr"

    def test_read_nonexistent_directory(self, empty_dir):
        nonexistent = empty_dir / "doesnt_exist"
        with pytest.raises(FileNotFoundError):
            read_extension(nonexistent)

    def test_read_file_instead_of_directory(self, sample_locales_dir):
        file_path = sample_locales_dir / "en" / "messages.json"
        with pytest.raises(ValueError):
            read_extension(file_path)


class TestWriteExtension:
    def test_write_basic(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)

        # Add a new message to French
        fr = catalog.get_or_create_locale("fr")
        fr.set_message("greeting", "Bonjour $USER$!", description="Greeting shown to user")

        write_extension(catalog, sample_locales_dir, backup=False)

        # Verify
        fr_file = sample_locales_dir / "fr" / "messages.json"
        assert fr_file.exists()
        data = json.loads(fr_file.read_text())
        assert data["greeting"]["message"] == "Bonjour $USER$!"
        assert data["greeting"]["description"] == "Greeting shown to user"

    def test_write_creates_locale_dir(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)

        # Add new locale
        de = catalog.get_or_create_locale("de")
        de.set_message("appName", "Meine Erweiterung")

        write_extension(catalog, sample_locales_dir, backup=False, locales=["de"])

        # Verify
        de_dir = sample_locales_dir / "de"
        assert de_dir.exists()
        data = json.loads((de_dir / "messages.json").read_text())
        assert data["appName"]["message"] == "Meine Erweiterung"

    def test_write_creates_backup(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)
        fr = catalog.get_locale("fr")
        fr.set_message("appName", "Updated Name")

        write_extension(catalog, sample_locales_dir, backup=True, locales=["fr"])

        backup_file = sample_locales_dir / "fr" / "messages.json.backup"
        assert backup_file.exists()
        backup_data = json.loads(backup_file.read_text())
        assert backup_data["appName"]["message"] == "Mon Extension"

    def test_write_specific_locales(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)

        de = catalog.get_or_create_locale("de")
        de.set_message("appName", "Meine App")

        ja = catalog.get_or_create_locale("ja")
        ja.set_message("appName", "私の拡張機能")

        # Only write de
        write_extension(catalog, sample_locales_dir, backup=False, locales=["de"])

        assert (sample_locales_dir / "de" / "messages.json").exists()
        assert not (sample_locales_dir / "ja").exists()

    def test_write_preserves_placeholders(self, sample_locales_dir):
        catalog = read_extension(sample_locales_dir)

        de = catalog.get_or_create_locale("de")
        source = catalog.get_source_locale()
        src_greeting = source.get_message("greeting")

        de.set_message(
            "greeting",
            "Hallo $USER$!",
            description=src_greeting.description,
            placeholders=src_greeting.placeholders,
        )

        write_extension(catalog, sample_locales_dir, backup=False, locales=["de"])

        data = json.loads((sample_locales_dir / "de" / "messages.json").read_text())
        assert data["greeting"]["placeholders"]["user"]["content"] == "$1"
        assert data["greeting"]["placeholders"]["user"]["example"] == "John"


class TestRoundTrip:
    def test_lossless_round_trip(self, sample_locales_dir):
        """Read and write should preserve content."""
        original_data = json.loads((sample_locales_dir / "en" / "messages.json").read_text())

        catalog = read_extension(sample_locales_dir)
        write_extension(catalog, sample_locales_dir, backup=False)

        after_data = json.loads((sample_locales_dir / "en" / "messages.json").read_text())
        assert after_data == original_data


class TestDetectExtensionPath:
    def test_detect_locales_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            locales_dir = tmpdir / "_locales"
            locales_dir.mkdir()

            en_dir = locales_dir / "en"
            en_dir.mkdir()
            (en_dir / "messages.json").write_text('{"test": {"message": "hello"}}')

            result = detect_extension_path(tmpdir)
            assert result == locales_dir

    def test_detect_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_extension_path(Path(tmpdir))
            assert result is None
