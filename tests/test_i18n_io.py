"""Tests for i18n JSON I/O."""

import json
import tempfile
from pathlib import Path

import pytest

from localizerx.io.i18n import detect_i18n_path, read_i18n, write_i18n


@pytest.fixture
def flat_locales_dir():
    """Create a temporary flat i18n directory: locales/en.json, locales/fr.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        locales_dir = Path(tmpdir) / "locales"
        locales_dir.mkdir()

        en_data = {
            "greeting": "Hello",
            "farewell": "Goodbye",
            "common": {
                "ok": "OK",
                "cancel": "Cancel",
            },
        }
        (locales_dir / "en.json").write_text(json.dumps(en_data, indent=2, ensure_ascii=False))

        fr_data = {
            "greeting": "Bonjour",
            "common": {
                "ok": "OK",
            },
        }
        (locales_dir / "fr.json").write_text(json.dumps(fr_data, indent=2, ensure_ascii=False))

        yield locales_dir


@pytest.fixture
def dir_per_locale():
    """Create a temporary dir-per-locale structure: locales/en/translation.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        locales_dir = Path(tmpdir) / "locales"
        locales_dir.mkdir()

        en_dir = locales_dir / "en"
        en_dir.mkdir()
        en_data = {
            "greeting": "Hello",
            "nested": {
                "key": "Value",
                "deep": {
                    "item": "Deep Item",
                },
            },
        }
        (en_dir / "translation.json").write_text(json.dumps(en_data, indent=2, ensure_ascii=False))

        fr_dir = locales_dir / "fr"
        fr_dir.mkdir()
        fr_data = {
            "greeting": "Bonjour",
        }
        (fr_dir / "translation.json").write_text(json.dumps(fr_data, indent=2, ensure_ascii=False))

        yield locales_dir


@pytest.fixture
def empty_dir():
    """Create an empty temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestReadI18nFlat:
    def test_read_flat_basic(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)
        assert catalog.source_locale == "en"
        assert catalog.locale_count == 2
        assert "en" in catalog.locales
        assert "fr" in catalog.locales

    def test_read_flat_messages(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)
        source = catalog.get_source_locale()

        assert source is not None
        assert source.message_count == 4  # greeting, farewell, common.ok, common.cancel

        greeting = source.get_message("greeting")
        assert greeting is not None
        assert greeting.value == "Hello"

    def test_read_flat_nested_keys(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)
        source = catalog.get_source_locale()

        ok_msg = source.get_message("common.ok")
        assert ok_msg is not None
        assert ok_msg.value == "OK"

        cancel_msg = source.get_message("common.cancel")
        assert cancel_msg is not None
        assert cancel_msg.value == "Cancel"

    def test_read_flat_partial_locale(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)
        fr = catalog.get_locale("fr")

        assert fr is not None
        assert fr.get_message("greeting") is not None
        assert fr.get_message("farewell") is None


class TestReadI18nDir:
    def test_read_dir_basic(self, dir_per_locale):
        catalog = read_i18n(dir_per_locale)
        assert catalog.locale_count == 2
        assert "en" in catalog.locales
        assert "fr" in catalog.locales

    def test_read_dir_messages(self, dir_per_locale):
        catalog = read_i18n(dir_per_locale)
        source = catalog.get_source_locale()

        assert source is not None
        assert source.message_count == 3  # greeting, nested.key, nested.deep.item

        deep = source.get_message("nested.deep.item")
        assert deep is not None
        assert deep.value == "Deep Item"


class TestWriteI18n:
    def test_write_flat(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)

        # Add a translation to French
        fr = catalog.get_or_create_locale("fr")
        fr.set_message("farewell", "Au revoir")

        write_i18n(catalog, flat_locales_dir, backup=False, locales=["fr"])

        # Verify
        data = json.loads((flat_locales_dir / "fr.json").read_text())
        # Since fr has raw_data from the read, it uses the template approach
        assert data["greeting"] == "Bonjour"

    def test_write_new_locale_flat(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)

        de = catalog.get_or_create_locale("de")
        de.set_message("greeting", "Hallo")
        de.set_message("farewell", "Auf Wiedersehen")
        de.set_message("common.ok", "OK")
        de.set_message("common.cancel", "Abbrechen")

        write_i18n(catalog, flat_locales_dir, backup=False, locales=["de"])

        de_file = flat_locales_dir / "de.json"
        assert de_file.exists()
        data = json.loads(de_file.read_text())
        # Source template preserves nesting
        assert data["greeting"] == "Hallo"
        assert data["common"]["ok"] == "OK"
        assert data["common"]["cancel"] == "Abbrechen"

    def test_write_dir_layout(self, dir_per_locale):
        catalog = read_i18n(dir_per_locale)

        de = catalog.get_or_create_locale("de")
        de.set_message("greeting", "Hallo")
        de.set_message("nested.key", "Wert")
        de.set_message("nested.deep.item", "Tiefes Element")

        write_i18n(catalog, dir_per_locale, backup=False, locales=["de"])

        de_file = dir_per_locale / "de" / "translation.json"
        assert de_file.exists()
        data = json.loads(de_file.read_text())
        assert data["greeting"] == "Hallo"
        assert data["nested"]["key"] == "Wert"
        assert data["nested"]["deep"]["item"] == "Tiefes Element"

    def test_write_creates_backup(self, flat_locales_dir):
        catalog = read_i18n(flat_locales_dir)
        fr = catalog.get_locale("fr")
        fr.set_message("greeting", "Salut")

        write_i18n(catalog, flat_locales_dir, backup=True, locales=["fr"])

        backup_file = flat_locales_dir / "fr.json.backup"
        assert backup_file.exists()
        backup_data = json.loads(backup_file.read_text())
        assert backup_data["greeting"] == "Bonjour"


class TestRoundTrip:
    def test_lossless_round_trip_flat(self, flat_locales_dir):
        """Read and write should preserve structure."""
        original_data = json.loads((flat_locales_dir / "en.json").read_text())

        catalog = read_i18n(flat_locales_dir)
        write_i18n(catalog, flat_locales_dir, backup=False, locales=["en"])

        after_data = json.loads((flat_locales_dir / "en.json").read_text())
        assert after_data == original_data

    def test_lossless_round_trip_dir(self, dir_per_locale):
        """Read and write should preserve structure for dir layout."""
        original_data = json.loads((dir_per_locale / "en" / "translation.json").read_text())

        catalog = read_i18n(dir_per_locale)
        write_i18n(catalog, dir_per_locale, backup=False, locales=["en"])

        after_data = json.loads((dir_per_locale / "en" / "translation.json").read_text())
        assert after_data == original_data


class TestDetectI18nPath:
    def test_detect_flat_locales(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            locales_dir = tmpdir / "locales"
            locales_dir.mkdir()
            (locales_dir / "en.json").write_text('{"hello": "Hello"}')

            result = detect_i18n_path(tmpdir)
            assert result == locales_dir

    def test_detect_dir_locales(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            locales_dir = tmpdir / "locales"
            locales_dir.mkdir()
            en_dir = locales_dir / "en"
            en_dir.mkdir()
            (en_dir / "translation.json").write_text('{"hello": "Hello"}')

            result = detect_i18n_path(tmpdir)
            assert result == locales_dir

    def test_detect_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_i18n_path(Path(tmpdir))
            assert result is None

    def test_detect_src_locales(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            locales_dir = tmpdir / "src" / "locales"
            locales_dir.mkdir(parents=True)
            (locales_dir / "en.json").write_text('{"hello": "Hello"}')

            result = detect_i18n_path(tmpdir)
            assert result == locales_dir

    def test_read_nonexistent(self, empty_dir):
        nonexistent = empty_dir / "doesnt_exist"
        with pytest.raises(FileNotFoundError):
            read_i18n(nonexistent)

    def test_read_file_instead_of_dir(self, flat_locales_dir):
        file_path = flat_locales_dir / "en.json"
        with pytest.raises(ValueError):
            read_i18n(file_path)

    def test_detect_deep_locales(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            locales_dir = tmpdir / "apps" / "web" / "src" / "i18n" / "locales"
            locales_dir.mkdir(parents=True)
            (locales_dir / "en.json").write_text('{"hello": "Hello"}')

            result = detect_i18n_path(tmpdir)
            assert result == locales_dir


class TestIndexTsGeneration:
    def test_index_ts_flat(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            locales_dir = Path(tmpdir) / "locales"
            locales_dir.mkdir()
            (locales_dir / "en.json").write_text('{"h": "H"}')
            (locales_dir / "fr.json").write_text('{"h": "B"}')

            catalog = read_i18n(locales_dir)
            write_i18n(catalog, locales_dir)

            index_ts = locales_dir / "index.ts"
            assert index_ts.exists()
            content = index_ts.read_text()
            assert 'import en from "./en.json";' in content
            assert 'import fr from "./fr.json";' in content
            assert '"en": en,' in content

    def test_index_ts_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            locales_dir = Path(tmpdir) / "locales"
            locales_dir.mkdir()
            en_dir = locales_dir / "en"
            en_dir.mkdir()
            (en_dir / "translation.json").write_text('{"h": "H"}')
            fr_dir = locales_dir / "fr"
            fr_dir.mkdir()
            (fr_dir / "translation.json").write_text('{"h": "B"}')

            catalog = read_i18n(locales_dir)
            write_i18n(catalog, locales_dir)

            index_ts = locales_dir / "index.ts"
            assert index_ts.exists()
            content = index_ts.read_text()
            assert 'import en from "./en/translation.json";' in content
            assert 'import fr from "./fr/translation.json";' in content
            assert '"en": en,' in content

    def test_index_ts_sanitized_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            locales_dir = Path(tmpdir) / "locales"
            locales_dir.mkdir()
            (locales_dir / "en-US.json").write_text('{"h": "H"}')
            (locales_dir / "pt-BR.json").write_text('{"h": "B"}')

            catalog = read_i18n(locales_dir)
            write_i18n(catalog, locales_dir)

            index_ts = locales_dir / "index.ts"
            content = index_ts.read_text()
            assert 'import enUS from "./en-US.json";' in content
            assert 'import ptBR from "./pt-BR.json";' in content
            assert '"en-US": enUS,' in content
            assert '"pt-BR": ptBR,' in content
