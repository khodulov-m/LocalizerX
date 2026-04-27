"""Tests for CLDR plural rules helpers."""

from localizerx.utils.plural_rules import (
    expand_source_forms,
    get_plural_categories,
    get_plural_rules_text,
)


class TestPluralCategories:
    def test_english_two_categories(self):
        assert get_plural_categories("en") == ["one", "other"]

    def test_russian_four_categories(self):
        assert get_plural_categories("ru") == ["one", "few", "many", "other"]

    def test_arabic_six_categories(self):
        assert get_plural_categories("ar") == [
            "zero", "one", "two", "few", "many", "other",
        ]

    def test_japanese_single_category(self):
        assert get_plural_categories("ja") == ["other"]

    def test_chinese_single_category(self):
        assert get_plural_categories("zh") == ["other"]
        assert get_plural_categories("zh-Hans") == ["other"]
        assert get_plural_categories("zh-Hant") == ["other"]

    def test_french_three_categories(self):
        assert get_plural_categories("fr") == ["one", "many", "other"]

    def test_polish_four_categories(self):
        assert get_plural_categories("pl") == ["one", "few", "many", "other"]

    def test_pt_br_distinct_from_pt(self):
        assert get_plural_categories("pt-BR") == ["one", "many", "other"]
        assert get_plural_categories("pt") == ["one", "other"]

    def test_unknown_language_falls_back(self):
        assert get_plural_categories("xx") == ["one", "other"]

    def test_locale_with_region_falls_back_to_base(self):
        # de-CH is not explicitly listed but should follow German rules.
        assert get_plural_categories("de-CH") == ["one", "other"]


class TestPluralRulesText:
    def test_russian_rules_mention_endings(self):
        text = get_plural_rules_text("ru")
        assert "ending in 1" in text
        assert "EXCEPT" in text
        assert "few" in text and "many" in text

    def test_arabic_rules_cover_all_six(self):
        text = get_plural_rules_text("ar")
        for cat in ("zero", "one", "two", "few", "many", "other"):
            assert cat in text

    def test_japanese_rules_explain_no_plural(self):
        text = get_plural_rules_text("ja")
        assert "no grammatical plural" in text.lower()

    def test_unknown_language_returns_generic(self):
        text = get_plural_rules_text("xx")
        assert "one" in text and "other" in text


class TestExpandSourceForms:
    def test_other_present_returns_unchanged(self):
        forms = {"one": "1 item", "other": "N items"}
        assert expand_source_forms(forms) == forms

    def test_other_missing_falls_back_to_many(self):
        forms = {"many": "many items"}
        result = expand_source_forms(forms)
        assert result["other"] == "many items"

    def test_empty_returns_empty(self):
        assert expand_source_forms({}) == {}
