"""Tests for Android strings.xml I/O."""

import tempfile
from pathlib import Path

import pytest

from localizerx.io.android import detect_android_path, read_android, write_android
from localizerx.utils.locale import android_to_standard_locale, standard_to_android_locale


@pytest.fixture
def sample_res_dir():
    """Create a temporary Android res/ directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        res_dir = Path(tmpdir) / "res"
        res_dir.mkdir()

        # Create default values/ (source locale)
        values_dir = res_dir / "values"
        values_dir.mkdir()
        strings_xml = """\
<?xml version='1.0' encoding='utf-8'?>
<resources>
    <string name="app_name">My App</string>
    <string name="greeting">Hello</string>
    <string name="api_key" translatable="false">abc123</string>
    <string-array name="colors">
        <item>Red</item>
        <item>Green</item>
        <item>Blue</item>
    </string-array>
    <plurals name="items_count">
        <item quantity="one">%d item</item>
        <item quantity="other">%d items</item>
    </plurals>
</resources>
"""
        (values_dir / "strings.xml").write_text(strings_xml, encoding="utf-8")

        # Create fr locale
        fr_dir = res_dir / "values-fr"
        fr_dir.mkdir()
        fr_xml = """\
<?xml version='1.0' encoding='utf-8'?>
<resources>
    <string name="app_name">Mon App</string>
</resources>
"""
        (fr_dir / "strings.xml").write_text(fr_xml, encoding="utf-8")

        yield res_dir


@pytest.fixture
def empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestReadAndroid:
    def test_read_basic(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        assert catalog.source_locale == "en"
        assert catalog.locale_count == 2
        assert "en" in catalog.locales
        assert "fr" in catalog.locales

    def test_read_strings(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        source = catalog.get_source_locale()

        assert source is not None
        assert source.string_count == 3
        assert source.strings["app_name"].value == "My App"
        assert source.strings["greeting"].value == "Hello"

    def test_read_translatable_false(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        source = catalog.get_source_locale()

        api_key = source.strings["api_key"]
        assert api_key.translatable is False
        assert api_key.needs_translation is False

    def test_read_string_array(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        source = catalog.get_source_locale()

        assert "colors" in source.string_arrays
        colors = source.string_arrays["colors"]
        assert len(colors.items) == 3
        assert colors.items[0] == "Red"

    def test_read_plurals(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        source = catalog.get_source_locale()

        assert "items_count" in source.plurals
        plural = source.plurals["items_count"]
        assert plural.items["one"] == "%d item"
        assert plural.items["other"] == "%d items"

    def test_read_partial_locale(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        fr = catalog.get_locale("fr")

        assert fr is not None
        assert fr.string_count == 1
        assert fr.strings["app_name"].value == "Mon App"

    def test_read_nonexistent(self, empty_dir):
        nonexistent = empty_dir / "doesnt_exist"
        with pytest.raises(FileNotFoundError):
            read_android(nonexistent)

    def test_read_file_instead_of_dir(self, sample_res_dir):
        file_path = sample_res_dir / "values" / "strings.xml"
        with pytest.raises(ValueError):
            read_android(file_path)


class TestWriteAndroid:
    def test_write_new_locale(self, sample_res_dir):
        catalog = read_android(sample_res_dir)

        from localizerx.parser.android_model import AndroidString

        de = catalog.get_or_create_locale("de")
        de.strings["app_name"] = AndroidString(name="app_name", value="Meine App")
        de.strings["greeting"] = AndroidString(name="greeting", value="Hallo")

        write_android(catalog, sample_res_dir, backup=False, locales=["de"])

        de_dir = sample_res_dir / "values-de"
        assert de_dir.exists()
        assert (de_dir / "strings.xml").exists()

        # Re-read and verify
        catalog2 = read_android(sample_res_dir)
        de2 = catalog2.get_locale("de")
        assert de2 is not None
        assert de2.strings["app_name"].value == "Meine App"
        assert de2.strings["greeting"].value == "Hallo"

    def test_write_regional_locale(self, sample_res_dir):
        from localizerx.parser.android_model import AndroidString

        catalog = read_android(sample_res_dir)

        pt_br = catalog.get_or_create_locale("pt-BR")
        pt_br.strings["app_name"] = AndroidString(name="app_name", value="Meu App")

        write_android(catalog, sample_res_dir, backup=False, locales=["pt-BR"])

        pt_br_dir = sample_res_dir / "values-pt-rBR"
        assert pt_br_dir.exists()

    def test_write_creates_backup(self, sample_res_dir):
        catalog = read_android(sample_res_dir)
        fr = catalog.get_locale("fr")

        from localizerx.parser.android_model import AndroidString

        fr.strings["app_name"] = AndroidString(name="app_name", value="Updated")

        write_android(catalog, sample_res_dir, backup=True, locales=["fr"])

        backup_file = sample_res_dir / "values-fr" / "strings.xml.backup"
        assert backup_file.exists()

    def test_write_string_array(self, sample_res_dir):
        from localizerx.parser.android_model import AndroidStringArray

        catalog = read_android(sample_res_dir)
        de = catalog.get_or_create_locale("de")
        de.string_arrays["colors"] = AndroidStringArray(
            name="colors", items=["Rot", "Grün", "Blau"]
        )

        write_android(catalog, sample_res_dir, backup=False, locales=["de"])

        catalog2 = read_android(sample_res_dir)
        de2 = catalog2.get_locale("de")
        assert "colors" in de2.string_arrays
        assert de2.string_arrays["colors"].items == ["Rot", "Grün", "Blau"]

    def test_write_plurals(self, sample_res_dir):
        from localizerx.parser.android_model import AndroidPlural

        catalog = read_android(sample_res_dir)
        de = catalog.get_or_create_locale("de")
        de.plurals["items_count"] = AndroidPlural(
            name="items_count",
            items={"one": "%d Element", "other": "%d Elemente"},
        )

        write_android(catalog, sample_res_dir, backup=False, locales=["de"])

        catalog2 = read_android(sample_res_dir)
        de2 = catalog2.get_locale("de")
        assert "items_count" in de2.plurals
        assert de2.plurals["items_count"].items["one"] == "%d Element"


class TestRoundTrip:
    def test_strings_round_trip(self, sample_res_dir):
        """Read and write should preserve string content."""
        catalog = read_android(sample_res_dir)
        source = catalog.get_source_locale()

        # Write source locale
        write_android(catalog, sample_res_dir, backup=False, locales=["en"])

        catalog2 = read_android(sample_res_dir)
        source2 = catalog2.get_source_locale()

        assert source2.strings["app_name"].value == source.strings["app_name"].value
        assert source2.strings["greeting"].value == source.strings["greeting"].value


class TestLocaleDirNaming:
    def test_standard_to_android_simple(self):
        assert standard_to_android_locale("fr") == "fr"

    def test_standard_to_android_region(self):
        assert standard_to_android_locale("pt-BR") == "pt-rBR"

    def test_standard_to_android_script(self):
        assert standard_to_android_locale("zh-Hans") == "b+zh+Hans"

    def test_standard_to_android_script_region(self):
        assert standard_to_android_locale("zh-Hant-TW") == "b+zh+Hant+TW"

    def test_android_to_standard_simple(self):
        assert android_to_standard_locale("fr") == "fr"

    def test_android_to_standard_region(self):
        assert android_to_standard_locale("pt-rBR") == "pt-BR"

    def test_android_to_standard_script(self):
        assert android_to_standard_locale("b+zh+Hans") == "zh-Hans"


class TestDetectAndroidPath:
    def test_detect_res_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            res_dir = tmpdir / "res"
            res_dir.mkdir()
            values_dir = res_dir / "values"
            values_dir.mkdir()
            (values_dir / "strings.xml").write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
                '    <string name="app_name">Test</string>\n</resources>\n'
            )

            result = detect_android_path(tmpdir)
            assert result == res_dir

    def test_detect_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_android_path(Path(tmpdir))
            assert result is None

    def test_detect_app_src_main_res(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            res_dir = tmpdir / "app" / "src" / "main" / "res"
            res_dir.mkdir(parents=True)
            values_dir = res_dir / "values"
            values_dir.mkdir()
            (values_dir / "strings.xml").write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
                '    <string name="app_name">Test</string>\n</resources>\n'
            )

            result = detect_android_path(tmpdir)
            assert result == res_dir


class TestXmlEscaping:
    def test_apostrophe_escaping(self, sample_res_dir):
        """Strings with apostrophes should be escaped properly."""
        from localizerx.parser.android_model import AndroidString

        catalog = read_android(sample_res_dir)
        de = catalog.get_or_create_locale("de")
        de.strings["test"] = AndroidString(name="test", value="It's a test")

        write_android(catalog, sample_res_dir, backup=False, locales=["de"])

        # Re-read and verify value is preserved
        catalog2 = read_android(sample_res_dir)
        de2 = catalog2.get_locale("de")
        assert de2.strings["test"].value == "It's a test"
