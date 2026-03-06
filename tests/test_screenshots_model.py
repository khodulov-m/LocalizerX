"""Tests for screenshot text data models."""

from localizerx.parser.screenshots_model import (
    SCREENSHOT_TEXT_WORD_LIMIT,
    DeviceClass,
    ScreenshotLocale,
    ScreenshotsCatalog,
    ScreenshotScreen,
    ScreenshotText,
    ScreenshotTextType,
)


class TestScreenshotText:
    def test_basic_creation(self):
        text = ScreenshotText(small="Short", large="Longer text here")
        assert text.small == "Short"
        assert text.large == "Longer text here"

    def test_get_variant(self):
        text = ScreenshotText(small="Small", large="Large")
        assert text.get_variant(DeviceClass.SMALL) == "Small"
        assert text.get_variant(DeviceClass.LARGE) == "Large"

    def test_set_variant(self):
        text = ScreenshotText()
        text.set_variant(DeviceClass.SMALL, "New small")
        text.set_variant(DeviceClass.LARGE, "New large")
        assert text.small == "New small"
        assert text.large == "New large"

    def test_has_small(self):
        assert ScreenshotText(small="Test").has_small
        assert not ScreenshotText(small="").has_small
        assert not ScreenshotText(small="  ").has_small
        assert not ScreenshotText().has_small

    def test_has_large(self):
        assert ScreenshotText(large="Test").has_large
        assert not ScreenshotText(large="").has_large
        assert not ScreenshotText(large="  ").has_large
        assert not ScreenshotText().has_large

    def test_is_empty(self):
        assert ScreenshotText().is_empty
        assert ScreenshotText(small="", large="").is_empty
        assert not ScreenshotText(small="Test").is_empty
        assert not ScreenshotText(large="Test").is_empty
        assert not ScreenshotText(small="A", large="B").is_empty

    def test_word_count(self):
        text = ScreenshotText(small="One two", large="One two three four")
        assert text.word_count(DeviceClass.SMALL) == 2
        assert text.word_count(DeviceClass.LARGE) == 4

    def test_word_count_empty(self):
        text = ScreenshotText()
        assert text.word_count(DeviceClass.SMALL) == 0
        assert text.word_count(DeviceClass.LARGE) == 0

    def test_is_over_word_limit(self):
        within_limit = ScreenshotText(small="One two three")
        assert not within_limit.is_over_word_limit(DeviceClass.SMALL)

        over_limit = ScreenshotText(small="One two three four five six seven")
        assert over_limit.is_over_word_limit(DeviceClass.SMALL)

    def test_to_dict(self):
        text = ScreenshotText(small="A", large="B")
        d = text.to_dict()
        assert d == {"small": "A", "large": "B"}

    def test_to_dict_excludes_none(self):
        text = ScreenshotText(small="Only small")
        d = text.to_dict()
        assert d == {"small": "Only small"}
        assert "large" not in d


class TestScreenshotScreen:
    def test_basic_creation(self):
        screen = ScreenshotScreen()
        assert screen.text_count == 0
        assert screen.is_empty

    def test_set_text(self):
        screen = ScreenshotScreen()
        text = ScreenshotText(small="Headline", large="Full Headline")
        screen.set_text(ScreenshotTextType.HEADLINE, text)

        assert screen.text_count == 1
        assert not screen.is_empty
        retrieved = screen.get_text(ScreenshotTextType.HEADLINE)
        assert retrieved is not None
        assert retrieved.small == "Headline"

    def test_set_text_variant(self):
        screen = ScreenshotScreen()
        screen.set_text_variant(
            ScreenshotTextType.HEADLINE,
            DeviceClass.SMALL,
            "Short headline",
        )

        text = screen.get_text(ScreenshotTextType.HEADLINE)
        assert text is not None
        assert text.small == "Short headline"
        assert text.large is None

    def test_get_over_limit_texts(self):
        screen = ScreenshotScreen()
        screen.set_text_variant(
            ScreenshotTextType.HEADLINE,
            DeviceClass.SMALL,
            "One two three four five six seven eight",  # Over 5 words
        )
        screen.set_text_variant(
            ScreenshotTextType.SUBTITLE,
            DeviceClass.SMALL,
            "Short text",  # Within limit
        )

        over_limit = screen.get_over_limit_texts()
        assert len(over_limit) == 1
        assert over_limit[0] == (ScreenshotTextType.HEADLINE, DeviceClass.SMALL)

    def test_to_dict(self):
        screen = ScreenshotScreen()
        screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="H", large="Headline"),
        )

        d = screen.to_dict()
        assert "headline" in d
        assert d["headline"]["small"] == "H"
        assert d["headline"]["large"] == "Headline"


class TestScreenshotLocale:
    def test_basic_creation(self):
        locale = ScreenshotLocale(locale="de")
        assert locale.locale == "de"
        assert locale.screen_count == 0

    def test_get_or_create_screen(self):
        locale = ScreenshotLocale(locale="de")

        screen1 = locale.get_or_create_screen("screen_1")
        assert screen1 is not None
        assert locale.screen_count == 1

        screen1_again = locale.get_or_create_screen("screen_1")
        assert screen1_again is screen1
        assert locale.screen_count == 1

    def test_get_all_texts(self):
        locale = ScreenshotLocale(locale="de")

        screen = locale.get_or_create_screen("screen_1")
        screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="H"))
        screen.set_text(ScreenshotTextType.SUBTITLE, ScreenshotText(small="S"))

        all_texts = locale.get_all_texts()
        assert len(all_texts) == 2
        assert all(t[0] == "screen_1" for t in all_texts)

    def test_to_dict(self):
        locale = ScreenshotLocale(locale="de")
        screen = locale.get_or_create_screen("screen_1")
        screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Test"))

        d = locale.to_dict()
        assert "screen_1" in d
        assert "headline" in d["screen_1"]


class TestScreenshotsCatalog:
    def test_basic_creation(self):
        catalog = ScreenshotsCatalog(source_language="en")
        assert catalog.source_language == "en"
        assert catalog.screen_count == 0
        assert catalog.locale_count == 0

    def test_source_screens(self):
        catalog = ScreenshotsCatalog(source_language="en")

        screen = catalog.get_or_create_source_screen("screen_1")
        screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="Hello", large="Hello World"),
        )

        assert catalog.screen_count == 1
        retrieved = catalog.get_source_screen("screen_1")
        assert retrieved is not None

    def test_localizations(self):
        catalog = ScreenshotsCatalog(source_language="en")
        de = catalog.get_or_create_locale("de")
        de_screen = de.get_or_create_screen("screen_1")
        de_screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="Hallo"),
        )

        assert catalog.locale_count == 1
        assert "de" in catalog.get_target_locales()

    def test_get_all_locales(self):
        catalog = ScreenshotsCatalog(source_language="en")
        catalog.get_or_create_locale("de")
        catalog.get_or_create_locale("fr")

        all_locales = catalog.get_all_locales()
        assert "en" in all_locales
        assert "de" in all_locales
        assert "fr" in all_locales
        assert all_locales[0] == "en"  # Source first

    def test_get_source_texts(self):
        catalog = ScreenshotsCatalog(source_language="en")

        screen1 = catalog.get_or_create_source_screen("screen_1")
        screen1.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="H1"))

        screen2 = catalog.get_or_create_source_screen("screen_2")
        screen2.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="H2"))

        texts = catalog.get_source_texts()
        assert len(texts) == 2

    def test_get_texts_needing_translation(self):
        catalog = ScreenshotsCatalog(source_language="en")

        # Add source texts
        screen = catalog.get_or_create_source_screen("screen_1")
        screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="Hello", large="Hello World"),
        )

        # No translations yet
        needs = catalog.get_texts_needing_translation("de")
        assert len(needs) == 2  # Both small and large variants

    def test_get_texts_needing_translation_partial(self):
        catalog = ScreenshotsCatalog(source_language="en")

        # Add source texts
        screen = catalog.get_or_create_source_screen("screen_1")
        screen.set_text(
            ScreenshotTextType.HEADLINE,
            ScreenshotText(small="Hello", large="Hello World"),
        )

        # Add partial translation
        de = catalog.get_or_create_locale("de")
        de_screen = de.get_or_create_screen("screen_1")
        de_screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Hallo"))

        needs = catalog.get_texts_needing_translation("de")
        assert len(needs) == 1  # Only large variant missing
        assert needs[0][2] == DeviceClass.LARGE

    def test_get_texts_needing_translation_with_overwrite(self):
        catalog = ScreenshotsCatalog(source_language="en")

        screen = catalog.get_or_create_source_screen("screen_1")
        screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Hello"))

        # Add complete translation
        de = catalog.get_or_create_locale("de")
        de_screen = de.get_or_create_screen("screen_1")
        de_screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Hallo"))

        # Without overwrite - nothing needed
        needs = catalog.get_texts_needing_translation("de", overwrite=False)
        assert len(needs) == 0

        # With overwrite - everything needed
        needs = catalog.get_texts_needing_translation("de", overwrite=True)
        assert len(needs) == 1

    def test_raw_data(self):
        catalog = ScreenshotsCatalog(source_language="en")
        raw = {"sourceLanguage": "en", "screens": {}}

        catalog.set_raw_data(raw)
        assert catalog.get_raw_data() == raw

    def test_to_dict(self):
        catalog = ScreenshotsCatalog(source_language="en")

        screen = catalog.get_or_create_source_screen("screen_1")
        screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Hello"))

        de = catalog.get_or_create_locale("de")
        de_screen = de.get_or_create_screen("screen_1")
        de_screen.set_text(ScreenshotTextType.HEADLINE, ScreenshotText(small="Hallo"))

        d = catalog.to_dict()
        assert d["sourceLanguage"] == "en"
        assert "screens" in d
        assert "screen_1" in d["screens"]
        assert "localizations" in d
        assert "de" in d["localizations"]


class TestScreenshotTextWordLimit:
    def test_word_limit_constant(self):
        # Verify the constant is set correctly
        assert SCREENSHOT_TEXT_WORD_LIMIT == 5

    def test_exactly_at_limit(self):
        text = ScreenshotText(small="One two three four five")
        assert text.word_count(DeviceClass.SMALL) == 5
        assert not text.is_over_word_limit(DeviceClass.SMALL)

    def test_one_over_limit(self):
        text = ScreenshotText(small="One two three four five six")
        assert text.word_count(DeviceClass.SMALL) == 6
        assert text.is_over_word_limit(DeviceClass.SMALL)
