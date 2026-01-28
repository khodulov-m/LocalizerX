"""Tests for Android data models."""

from localizerx.parser.android_model import (
    AndroidCatalog,
    AndroidLocale,
    AndroidPlural,
    AndroidString,
    AndroidStringArray,
)


class TestAndroidString:
    def test_basic_string(self):
        s = AndroidString(name="app_name", value="My App")
        assert s.name == "app_name"
        assert s.value == "My App"
        assert s.translatable is True
        assert s.comment is None

    def test_needs_translation(self):
        s = AndroidString(name="app_name", value="My App")
        assert s.needs_translation is True

    def test_needs_translation_empty(self):
        s = AndroidString(name="empty", value="")
        assert s.needs_translation is False

    def test_needs_translation_not_translatable(self):
        s = AndroidString(name="key", value="Some Value", translatable=False)
        assert s.needs_translation is False


class TestAndroidStringArray:
    def test_basic_array(self):
        arr = AndroidStringArray(name="colors", items=["Red", "Green", "Blue"])
        assert arr.name == "colors"
        assert len(arr.items) == 3
        assert arr.translatable is True


class TestAndroidPlural:
    def test_basic_plural(self):
        p = AndroidPlural(
            name="items_count",
            items={"one": "%d item", "other": "%d items"},
        )
        assert p.name == "items_count"
        assert len(p.items) == 2
        assert p.items["one"] == "%d item"


class TestAndroidLocale:
    def test_basic_locale(self):
        locale = AndroidLocale(locale="en")
        assert locale.locale == "en"
        assert locale.string_count == 0

    def test_translatable_strings(self):
        locale = AndroidLocale(locale="en")
        locale.strings["app_name"] = AndroidString(name="app_name", value="My App")
        locale.strings["api_key"] = AndroidString(
            name="api_key", value="abc123", translatable=False
        )
        locale.strings["greeting"] = AndroidString(name="greeting", value="Hello")

        translatable = locale.translatable_strings
        assert len(translatable) == 2
        names = {s.name for s in translatable}
        assert "app_name" in names
        assert "greeting" in names


class TestAndroidCatalog:
    def _make_catalog(self):
        catalog = AndroidCatalog(source_locale="en")
        source = catalog.get_or_create_locale("en")
        source.strings["app_name"] = AndroidString(name="app_name", value="My App")
        source.strings["greeting"] = AndroidString(name="greeting", value="Hello")
        source.strings["api_key"] = AndroidString(
            name="api_key", value="abc123", translatable=False
        )
        source.string_arrays["colors"] = AndroidStringArray(name="colors", items=["Red", "Green"])
        source.plurals["items"] = AndroidPlural(
            name="items", items={"one": "%d item", "other": "%d items"}
        )
        return catalog

    def test_basic_catalog(self):
        catalog = self._make_catalog()
        assert catalog.source_locale == "en"
        assert catalog.locale_count == 1

    def test_get_strings_needing_translation_all(self):
        catalog = self._make_catalog()
        needs = catalog.get_strings_needing_translation("fr")
        assert len(needs) == 2  # api_key is not translatable

    def test_get_strings_needing_translation_partial(self):
        catalog = self._make_catalog()
        fr = catalog.get_or_create_locale("fr")
        fr.strings["app_name"] = AndroidString(name="app_name", value="Mon App")

        needs = catalog.get_strings_needing_translation("fr")
        assert len(needs) == 1
        assert needs[0].name == "greeting"

    def test_get_arrays_needing_translation(self):
        catalog = self._make_catalog()
        needs = catalog.get_arrays_needing_translation("fr")
        assert len(needs) == 1
        assert needs[0].name == "colors"

    def test_get_plurals_needing_translation(self):
        catalog = self._make_catalog()
        needs = catalog.get_plurals_needing_translation("fr")
        assert len(needs) == 1
        assert needs[0].name == "items"

    def test_get_strings_not_translatable_skipped(self):
        catalog = self._make_catalog()
        source = catalog.get_source_locale()
        source.string_arrays["colors"].translatable = False
        source.plurals["items"].translatable = False

        assert catalog.get_arrays_needing_translation("fr") == []
        assert catalog.get_plurals_needing_translation("fr") == []
