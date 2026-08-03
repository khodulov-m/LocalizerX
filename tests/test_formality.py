"""Tests for form-of-address (T–V distinction) handling."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from localizerx.config import ScreenshotsConfig, TranslatorConfig, _parse_config
from localizerx.core.use_cases.translate_metadata import (
    TranslateMetadataRequest,
    TranslateMetadataUseCase,
)
from localizerx.parser.extension_model import ExtensionFieldType
from localizerx.parser.metadata_model import LocaleMetadata, MetadataCatalog, MetadataFieldType
from localizerx.parser.screenshots_model import DeviceClass, ScreenshotTextType
from localizerx.translator.extension_prompts import build_extension_field_prompt
from localizerx.translator.frameit_prompts import build_frameit_prompt
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.translator.metadata_prompts import (
    build_batch_metadata_prompt,
    build_metadata_prompt,
)
from localizerx.translator.screenshots_prompts import (
    build_batch_screenshot_prompt,
    build_screenshot_prompt,
)
from localizerx.utils.formality import (
    FORMALITY_AUTO,
    FORMALITY_FORMAL,
    FORMALITY_INFORMAL,
    build_formality_directive,
    normalize_formality,
    resolve_translator_formality,
    supports_formality,
)


class TestNormalizeFormality:
    def test_canonical_values(self):
        assert normalize_formality("auto") == FORMALITY_AUTO
        assert normalize_formality("formal") == FORMALITY_FORMAL
        assert normalize_formality("informal") == FORMALITY_INFORMAL

    def test_none_and_empty_mean_auto(self):
        assert normalize_formality(None) == FORMALITY_AUTO
        assert normalize_formality("") == FORMALITY_AUTO

    def test_pronoun_aliases(self):
        assert normalize_formality("du") == FORMALITY_INFORMAL
        assert normalize_formality("TU") == FORMALITY_INFORMAL
        assert normalize_formality("Sie") == FORMALITY_FORMAL
        assert normalize_formality(" vous ") == FORMALITY_FORMAL

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError, match="Invalid formality"):
            normalize_formality("polite-ish")


class TestBuildFormalityDirective:
    def test_auto_produces_no_directive(self):
        assert build_formality_directive("de", FORMALITY_AUTO) == ""
        assert build_formality_directive("de", None) == ""

    def test_german_informal_asks_for_du_and_forbids_sie(self):
        directive = build_formality_directive("de", FORMALITY_INFORMAL)
        assert '"du"' in directive
        assert 'Never use the polite "Sie"' in directive

    def test_german_formal_asks_for_sie(self):
        directive = build_formality_directive("de", FORMALITY_FORMAL)
        assert '"Sie"' in directive
        assert 'Never use "du"' in directive

    def test_region_variants_inherit_base_language(self):
        assert build_formality_directive("de-DE", FORMALITY_INFORMAL) == (
            build_formality_directive("de", FORMALITY_INFORMAL)
        )

    def test_european_portuguese_informal_is_tu(self):
        directive = build_formality_directive("pt-PT", FORMALITY_INFORMAL)
        assert '"tu"' in directive
        assert 'Never use "você"' in directive

    def test_brazilian_portuguese_informal_is_voce_not_tu(self):
        """pt-BR must not inherit the European "tu" — "você" is the casual register there."""
        directive = build_formality_directive("pt-BR", FORMALITY_INFORMAL)
        assert '"você"' in directive
        assert '"o(a) senhor(a)"' in directive

    def test_underscore_locale_codes_are_accepted(self):
        """Chrome-style codes (pt_BR) resolve like their hyphenated form."""
        assert build_formality_directive("pt_BR", FORMALITY_INFORMAL) == (
            build_formality_directive("pt-BR", FORMALITY_INFORMAL)
        )

    def test_language_without_tv_distinction_gets_tone_guidance(self):
        directive = build_formality_directive("he", FORMALITY_INFORMAL)
        assert directive != ""
        assert "casual" in directive

    def test_supports_formality(self):
        assert supports_formality("de")
        assert supports_formality("fr-CA")
        assert not supports_formality("he")


class TestResolveTranslatorFormality:
    def test_reads_attribute(self):
        class Stub:
            formality = FORMALITY_INFORMAL

        assert resolve_translator_formality(Stub()) == FORMALITY_INFORMAL

    def test_missing_or_invalid_attribute_falls_back_to_auto(self):
        class Missing:
            pass

        class Broken:
            formality = object()

        assert resolve_translator_formality(Missing()) == FORMALITY_AUTO
        assert resolve_translator_formality(Broken()) == FORMALITY_AUTO


class TestGeminiTranslatorPrompts:
    def _translator(self, formality):
        return GeminiTranslator(api_key="test-key", formality=formality)

    def test_single_prompt_carries_directive(self):
        translator = self._translator(FORMALITY_INFORMAL)
        prompt = translator._build_prompt("Hello", "English", "German", None, target_lang="de")
        assert "FORM OF ADDRESS" in prompt
        assert '"du"' in prompt

    def test_batch_prompt_carries_directive(self):
        translator = self._translator(FORMALITY_INFORMAL)
        prompt = translator._build_batch_prompt(
            "<<ITEM_1>>\nHello\n<</ITEM_1>>", 1, "English", "German", target_lang="de"
        )
        assert '"du"' in prompt

    def test_plural_prompt_carries_directive(self):
        translator = self._translator(FORMALITY_INFORMAL)
        prompt = translator._build_plural_prompt(
            {"one": "%d file", "other": "%d files"},
            "en",
            "de",
            ["one", "other"],
            None,
        )
        assert '"du"' in prompt

    def test_auto_leaves_prompts_untouched(self):
        translator = self._translator(FORMALITY_AUTO)
        prompt = translator._build_prompt("Hello", "English", "German", None, target_lang="de")
        assert "FORM OF ADDRESS" not in prompt

    def test_invalid_formality_rejected_at_construction(self):
        with pytest.raises(ValueError, match="Invalid formality"):
            GeminiTranslator(api_key="test-key", formality="somewhat-polite")


class TestCacheKeys:
    """Changing the register must not return the previously cached wording."""

    def test_cache_key_depends_on_formality(self):
        informal = GeminiTranslator(api_key="k", formality=FORMALITY_INFORMAL)
        formal = GeminiTranslator(api_key="k", formality=FORMALITY_FORMAL)

        assert informal._cache_key("Save", "en", "de") != formal._cache_key("Save", "en", "de")

    def test_cache_key_depends_on_custom_instructions(self):
        plain = GeminiTranslator(api_key="k")
        instructed = GeminiTranslator(api_key="k", custom_instructions="Keep it short")

        assert plain._cache_key("Save", "en", "de") != instructed._cache_key("Save", "en", "de")

    def test_plural_cache_key_depends_on_formality(self):
        informal = GeminiTranslator(api_key="k", formality=FORMALITY_INFORMAL)
        formal = GeminiTranslator(api_key="k", formality=FORMALITY_FORMAL)
        forms = {"one": "%d file", "other": "%d files"}

        assert informal._plural_cache_key(forms, ["one", "other"], None) != (
            formal._plural_cache_key(forms, ["one", "other"], None)
        )


class TestSpecializedPrompts:
    def test_metadata_prompt(self):
        prompt = build_metadata_prompt(
            "Track your water",
            MetadataFieldType.SUBTITLE,
            "en-US",
            "de-DE",
            formality=FORMALITY_INFORMAL,
        )
        assert '"du"' in prompt

    def test_metadata_prompt_auto_keeps_original_layout(self):
        with_auto = build_metadata_prompt(
            "Track your water", MetadataFieldType.SUBTITLE, "en-US", "de-DE"
        )
        assert "FORM OF ADDRESS" not in with_auto

    def test_batch_metadata_prompt(self):
        prompt = build_batch_metadata_prompt(
            [(MetadataFieldType.NAME, "Water"), (MetadataFieldType.SUBTITLE, "Drink up")],
            "en-US",
            "fr-FR",
            formality=FORMALITY_INFORMAL,
        )
        assert '"tu"' in prompt

    def test_extension_field_prompt_uses_chrome_locale(self):
        prompt = build_extension_field_prompt(
            text="Save pages",
            key="description",
            description=None,
            field_type=ExtensionFieldType.DESCRIPTION,
            src_lang="en",
            tgt_lang="pt_BR",
            formality=FORMALITY_INFORMAL,
        )
        assert '"você"' in prompt

    def test_screenshot_prompts(self):
        single = build_screenshot_prompt(
            "Drink more water",
            ScreenshotTextType.HEADLINE,
            DeviceClass.SMALL,
            "en",
            "de",
            formality=FORMALITY_INFORMAL,
        )
        batch = build_batch_screenshot_prompt(
            [("screen_1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Drink more water")],
            "en",
            "de",
            formality=FORMALITY_INFORMAL,
        )
        assert '"du"' in single
        assert '"du"' in batch

    def test_frameit_prompt(self):
        prompt = build_frameit_prompt(
            {"screenshot_1": "Drink more water"},
            "en-US",
            "de-DE",
            formality=FORMALITY_INFORMAL,
        )
        assert '"du"' in prompt


class TestUseCaseWiring:
    """The setting must reach the prompts a use case builds on its own."""

    @pytest.mark.asyncio
    async def test_metadata_use_case_passes_formality_to_prompts(self):
        catalog = MetadataCatalog(source_locale="en-US")
        source = LocaleMetadata(locale="en-US")
        source.set_field(MetadataFieldType.NAME, "Water")
        source.set_field(MetadataFieldType.SUBTITLE, "Track your water")
        catalog.locales["en-US"] = source

        repo = MagicMock()
        repo.read.return_value = catalog

        prompts = []

        async def capture(prompt):
            prompts.append(prompt)
            return "<<ITEM_1>>Wasser<</ITEM_1>>\n<<ITEM_2>>Trink mehr<</ITEM_2>>"

        translator = MagicMock()
        translator.formality = FORMALITY_INFORMAL
        translator._call_api = AsyncMock(side_effect=capture)

        use_case = TranslateMetadataUseCase(repository=repo, translator=translator)

        with tempfile.TemporaryDirectory() as tmpdir:
            await use_case.execute(
                TranslateMetadataRequest(
                    path=Path(tmpdir),
                    source_locale="en-US",
                    target_locales=["de-DE"],
                )
            )

        assert prompts
        assert all('"du"' in prompt for prompt in prompts)


class TestConfig:
    def test_default_is_auto(self):
        assert TranslatorConfig().formality == FORMALITY_AUTO
        assert ScreenshotsConfig().formality == FORMALITY_AUTO

    def test_config_value_is_normalized(self):
        assert TranslatorConfig(formality="du").formality == FORMALITY_INFORMAL

    def test_invalid_config_value_rejected(self):
        with pytest.raises(ValueError):
            TranslatorConfig(formality="somewhat-polite")

    def test_command_sections_inherit_base_formality(self):
        config = _parse_config(
            {
                "translator": {"formality": "informal"},
                "metadata": {"formality": "formal"},
            }
        )

        assert config.translate.formality == FORMALITY_INFORMAL
        assert config.i18n.formality == FORMALITY_INFORMAL
        assert config.metadata.formality == FORMALITY_FORMAL
