"""Tests for locale utilities."""

from localizerx.utils.locale import (
    get_language_name,
    normalize_language_code,
    parse_language_list,
    validate_language_code,
)


class TestValidateLanguageCode:
    def test_valid_two_letter_codes(self):
        assert validate_language_code("en") is True
        assert validate_language_code("es") is True
        assert validate_language_code("fr") is True
        assert validate_language_code("de") is True

    def test_valid_regional_codes(self):
        assert validate_language_code("en-US") is True
        assert validate_language_code("pt-BR") is True
        assert validate_language_code("zh-Hans") is True

    def test_unknown_but_valid_format(self):
        # Two-letter codes should be accepted even if unknown
        assert validate_language_code("xy") is True

    def test_invalid_codes(self):
        assert validate_language_code("") is False
        assert validate_language_code("english") is False
        assert validate_language_code("123") is False


class TestGetLanguageName:
    def test_known_languages(self):
        assert get_language_name("en") == "English"
        assert get_language_name("es") == "Spanish"
        assert get_language_name("fr") == "French"
        assert get_language_name("zh-Hans") == "Chinese (Simplified)"

    def test_regional_fallback(self):
        # Should fall back to base language if regional not found
        assert "English" in get_language_name("en-ZZ")

    def test_unknown_returns_code(self):
        assert get_language_name("xy") == "xy"


class TestNormalizeLanguageCode:
    def test_lowercase(self):
        assert normalize_language_code("EN") == "en"
        assert normalize_language_code("Es") == "es"

    def test_underscore_to_hyphen(self):
        assert normalize_language_code("pt_BR") == "pt-BR"
        assert normalize_language_code("zh_hans") == "zh-Hans"

    def test_script_capitalization(self):
        assert normalize_language_code("zh-hans") == "zh-Hans"
        assert normalize_language_code("zh-HANT") == "zh-Hant"

    def test_region_uppercase(self):
        assert normalize_language_code("en-us") == "en-US"
        assert normalize_language_code("pt-br") == "pt-BR"


class TestParseLanguageList:
    def test_comma_separated(self):
        result = parse_language_list("fr,es,de")
        assert result == ["fr", "es", "de"]

    def test_with_spaces(self):
        result = parse_language_list("fr, es, de")
        assert result == ["fr", "es", "de"]

    def test_regional_codes(self):
        result = parse_language_list("zh-Hans, ja, ko")
        assert result == ["zh-Hans", "ja", "ko"]

    def test_normalizes_codes(self):
        result = parse_language_list("EN, pt_br, ZH_HANS")
        assert result == ["en", "pt-BR", "zh-Hans"]

    def test_empty_entries_filtered(self):
        result = parse_language_list("fr,,es,")
        assert result == ["fr", "es"]
