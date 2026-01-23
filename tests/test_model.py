"""Tests for data models."""

from localizerx.parser.model import Entry, StringCatalog, Translation


class TestTranslation:
    def test_basic_translation(self):
        t = Translation(value="Hello")
        assert t.value == "Hello"
        assert t.state == "translated"
        assert t.variations is None

    def test_to_xcstrings_dict(self):
        t = Translation(value="Hello", state="translated")
        result = t.to_xcstrings_dict()
        assert result == {
            "stringUnit": {"state": "translated", "value": "Hello"}
        }


class TestEntry:
    def test_basic_entry(self):
        e = Entry(key="hello", source_text="Hello")
        assert e.key == "hello"
        assert e.source_text == "Hello"
        assert e.comment is None
        assert e.translations == {}

    def test_entry_with_comment(self):
        e = Entry(key="hello", source_text="Hello", comment="Greeting")
        assert e.comment == "Greeting"

    def test_needs_translation_true(self):
        e = Entry(key="hello", source_text="Hello")
        assert e.needs_translation is True

    def test_needs_translation_false_when_disabled(self):
        e = Entry(key="hello", source_text="Hello", should_translate=False)
        assert e.needs_translation is False

    def test_needs_translation_false_when_empty(self):
        e = Entry(key="hello", source_text="")
        assert e.needs_translation is False

    def test_needs_translation_false_when_whitespace(self):
        e = Entry(key="hello", source_text="   ")
        assert e.needs_translation is False


class TestStringCatalog:
    def test_basic_catalog(self):
        catalog = StringCatalog(source_language="en")
        assert catalog.source_language == "en"
        assert catalog.version == "1.0"
        assert catalog.strings == {}

    def test_catalog_with_entries(self):
        entries = {
            "hello": Entry(key="hello", source_text="Hello"),
            "goodbye": Entry(key="goodbye", source_text="Goodbye"),
        }
        catalog = StringCatalog(source_language="en", strings=entries)
        assert len(catalog.strings) == 2

    def test_get_entries_needing_translation(self):
        entries = {
            "hello": Entry(key="hello", source_text="Hello"),
            "goodbye": Entry(
                key="goodbye",
                source_text="Goodbye",
                translations={"fr": Translation(value="Au revoir")},
            ),
        }
        catalog = StringCatalog(source_language="en", strings=entries)

        # French: only hello needs translation
        needing_fr = catalog.get_entries_needing_translation("fr")
        assert len(needing_fr) == 1
        assert needing_fr[0].key == "hello"

        # Spanish: both need translation
        needing_es = catalog.get_entries_needing_translation("es")
        assert len(needing_es) == 2

    def test_get_all_translatable_entries(self):
        entries = {
            "hello": Entry(key="hello", source_text="Hello"),
            "empty": Entry(key="empty", source_text=""),
            "disabled": Entry(
                key="disabled", source_text="Skip me", should_translate=False
            ),
        }
        catalog = StringCatalog(source_language="en", strings=entries)

        translatable = catalog.get_all_translatable_entries()
        assert len(translatable) == 1
        assert translatable[0].key == "hello"

    def test_raw_data_storage(self):
        catalog = StringCatalog(source_language="en")
        raw = {"sourceLanguage": "en", "version": "1.0", "strings": {}}
        catalog.set_raw_data(raw)
        assert catalog.get_raw_data() == raw
