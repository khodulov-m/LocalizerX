"""Tests for Chrome Extension data models."""

from localizerx.parser.extension_model import (
    EXTENSION_FIELD_LIMITS,
    KNOWN_CWS_KEYS,
    ExtensionCatalog,
    ExtensionFieldType,
    ExtensionLocale,
    ExtensionMessage,
)


class TestExtensionMessage:
    def test_basic_message(self):
        msg = ExtensionMessage(key="greeting", message="Hello World")
        assert msg.key == "greeting"
        assert msg.message == "Hello World"
        assert msg.description is None
        assert msg.placeholders is None

    def test_field_type_for_cws_key(self):
        msg = ExtensionMessage(key="appName", message="My Extension")
        assert msg.field_type == ExtensionFieldType.APP_NAME

    def test_field_type_for_regular_key(self):
        msg = ExtensionMessage(key="greeting", message="Hello")
        assert msg.field_type is None

    def test_has_limit_cws(self):
        msg = ExtensionMessage(key="appName", message="My Extension")
        assert msg.has_limit is True
        assert msg.limit == 75

    def test_has_limit_regular(self):
        msg = ExtensionMessage(key="greeting", message="Hello")
        assert msg.has_limit is False
        assert msg.limit is None

    def test_char_count(self):
        msg = ExtensionMessage(key="test", message="Hello World")
        assert msg.char_count == 11

    def test_is_over_limit(self):
        msg = ExtensionMessage(key="shortName", message="This is way too long for short name")
        assert msg.is_over_limit is True

    def test_is_not_over_limit(self):
        msg = ExtensionMessage(key="shortName", message="Short")
        assert msg.is_over_limit is False

    def test_regular_message_not_over_limit(self):
        msg = ExtensionMessage(key="regular", message="x" * 10000)
        assert msg.is_over_limit is False

    def test_description_and_placeholders(self):
        msg = ExtensionMessage(
            key="greeting",
            message="Hello $USER$",
            description="Greeting shown to user",
            placeholders={"user": {"content": "$1", "example": "John"}},
        )
        assert msg.description == "Greeting shown to user"
        assert msg.placeholders is not None
        assert "user" in msg.placeholders


class TestExtensionLocale:
    def test_basic_locale(self):
        locale = ExtensionLocale(locale="en")
        assert locale.locale == "en"
        assert locale.field_count == 0

    def test_set_and_get_message(self):
        locale = ExtensionLocale(locale="en")
        locale.set_message("greeting", "Hello", description="A greeting")
        msg = locale.get_message("greeting")
        assert msg is not None
        assert msg.message == "Hello"
        assert msg.description == "A greeting"

    def test_get_missing_message(self):
        locale = ExtensionLocale(locale="en")
        assert locale.get_message("missing") is None

    def test_field_count(self):
        locale = ExtensionLocale(locale="en")
        locale.set_message("a", "A")
        locale.set_message("b", "B")
        assert locale.field_count == 2

    def test_get_over_limit_fields(self):
        locale = ExtensionLocale(locale="en")
        locale.set_message("shortName", "This is way too long")
        locale.set_message("appName", "OK Name")
        locale.set_message("regular", "x" * 1000)

        over = locale.get_over_limit_fields()
        assert len(over) == 1
        assert over[0].key == "shortName"


class TestExtensionCatalog:
    def _make_catalog(self):
        catalog = ExtensionCatalog(source_locale="en")
        source = catalog.get_or_create_locale("en")
        source.set_message("appName", "My Extension")
        source.set_message("appDesc", "A great extension")
        source.set_message("greeting", "Hello")
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
        fr.set_message("appName", "Mon Extension")

        needs = catalog.get_messages_needing_translation("fr")
        assert len(needs) == 2
        keys = {m.key for m in needs}
        assert "appDesc" in keys
        assert "greeting" in keys

    def test_get_messages_needing_translation_with_filter(self):
        catalog = self._make_catalog()
        needs = catalog.get_messages_needing_translation("fr", keys_filter=["appName"])
        assert len(needs) == 1
        assert needs[0].key == "appName"

    def test_get_messages_needing_translation_empty_target(self):
        catalog = self._make_catalog()
        fr = catalog.get_or_create_locale("fr")
        fr.set_message("greeting", "")

        needs = catalog.get_messages_needing_translation("fr")
        assert len(needs) == 3  # empty message counts as needing translation


class TestConstants:
    def test_known_cws_keys(self):
        assert "appName" in KNOWN_CWS_KEYS
        assert "shortName" in KNOWN_CWS_KEYS
        assert "appDesc" in KNOWN_CWS_KEYS
        assert "shortDesc" in KNOWN_CWS_KEYS
        assert "storeDesc" in KNOWN_CWS_KEYS
        assert "greeting" not in KNOWN_CWS_KEYS

    def test_field_limits(self):
        assert EXTENSION_FIELD_LIMITS[ExtensionFieldType.APP_NAME] == 75
        assert EXTENSION_FIELD_LIMITS[ExtensionFieldType.SHORT_NAME] == 12
        assert EXTENSION_FIELD_LIMITS[ExtensionFieldType.DESCRIPTION] == 132
        assert EXTENSION_FIELD_LIMITS[ExtensionFieldType.SHORT_DESC] == 132
        assert EXTENSION_FIELD_LIMITS[ExtensionFieldType.STORE_DESC] == 16383
