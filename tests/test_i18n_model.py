"""Tests for i18n data models."""

from localizerx.parser.i18n_model import I18nCatalog, I18nLocale, I18nMessage


class TestI18nMessage:
    def test_basic_message(self):
        msg = I18nMessage(key="greeting", value="Hello")
        assert msg.key == "greeting"
        assert msg.value == "Hello"

    def test_dotted_key(self):
        msg = I18nMessage(key="common.greeting", value="Hello")
        assert msg.key == "common.greeting"

    def test_needs_translation(self):
        msg = I18nMessage(key="greeting", value="Hello")
        assert msg.needs_translation is True

    def test_needs_translation_empty(self):
        msg = I18nMessage(key="greeting", value="")
        assert msg.needs_translation is False

    def test_needs_translation_whitespace(self):
        msg = I18nMessage(key="greeting", value="   ")
        assert msg.needs_translation is False


class TestI18nLocale:
    def test_basic_locale(self):
        locale = I18nLocale(locale="en")
        assert locale.locale == "en"
        assert locale.message_count == 0

    def test_set_and_get_message(self):
        locale = I18nLocale(locale="en")
        locale.set_message("greeting", "Hello")
        msg = locale.get_message("greeting")
        assert msg is not None
        assert msg.value == "Hello"

    def test_get_missing_message(self):
        locale = I18nLocale(locale="en")
        assert locale.get_message("missing") is None

    def test_message_count(self):
        locale = I18nLocale(locale="en")
        locale.set_message("a", "A")
        locale.set_message("b", "B")
        assert locale.message_count == 2

    def test_raw_data_roundtrip(self):
        locale = I18nLocale(locale="en")
        data = {"greeting": "Hello", "nested": {"key": "Value"}}
        locale.set_raw_data(data)
        assert locale.get_raw_data() == data


class TestI18nCatalog:
    def _make_catalog(self):
        catalog = I18nCatalog(source_locale="en")
        source = catalog.get_or_create_locale("en")
        source.set_message("greeting", "Hello")
        source.set_message("farewell", "Goodbye")
        source.set_message("common.ok", "OK")
        return catalog

    def test_basic_catalog(self):
        catalog = self._make_catalog()
        assert catalog.source_locale == "en"
        assert catalog.locale_count == 1

    def test_get_source_locale(self):
        catalog = self._make_catalog()
        source = catalog.get_source_locale()
        assert source is not None
        assert source.locale == "en"

    def test_get_or_create_locale(self):
        catalog = self._make_catalog()
        fr = catalog.get_or_create_locale("fr")
        assert fr.locale == "fr"
        assert catalog.locale_count == 2

    def test_get_messages_needing_translation_all(self):
        catalog = self._make_catalog()
        needs = catalog.get_messages_needing_translation("fr")
        assert len(needs) == 3

    def test_get_messages_needing_translation_partial(self):
        catalog = self._make_catalog()
        fr = catalog.get_or_create_locale("fr")
        fr.set_message("greeting", "Bonjour")

        needs = catalog.get_messages_needing_translation("fr")
        assert len(needs) == 2
        keys = {m.key for m in needs}
        assert "farewell" in keys
        assert "common.ok" in keys

    def test_get_messages_needing_translation_empty_value(self):
        catalog = self._make_catalog()
        fr = catalog.get_or_create_locale("fr")
        fr.set_message("greeting", "")

        needs = catalog.get_messages_needing_translation("fr")
        assert len(needs) == 3  # empty counts as needing translation
