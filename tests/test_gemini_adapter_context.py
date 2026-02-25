"""Tests for app context injection in GeminiTranslator prompts."""

from unittest.mock import AsyncMock, patch

import pytest

from localizerx.translator.gemini_adapter import GeminiTranslator


class TestGeminiAdapterAppContext:
    """Test app context inclusion in translation prompts."""

    def test_single_translation_prompt_with_app_context(self):
        """Test that app context is added to single text translation prompt."""
        translator = GeminiTranslator(api_key="fake-key", app_context="- App Name: TestApp\n- Description: A test app")

        prompt = translator._build_prompt("Hello", "English", "Russian", context=None)

        assert "App Context:" in prompt
        assert "- App Name: TestApp" in prompt
        assert "- Description: A test app" in prompt
        assert "Text to translate:\nHello" in prompt

    def test_single_translation_prompt_without_app_context(self):
        """Test that prompt works correctly without app context."""
        translator = GeminiTranslator(api_key="fake-key", app_context=None)

        prompt = translator._build_prompt("Hello", "English", "Russian", context=None)

        assert "App Context:" not in prompt
        assert "Text to translate:\nHello" in prompt

    def test_batch_translation_prompt_with_app_context(self):
        """Test that app context is added to batch translation prompt."""
        translator = GeminiTranslator(api_key="fake-key", app_context="- App Name: TestApp")

        batch_text = "<<ITEM_1>>\nHello\n<</ITEM_1>>"
        prompt = translator._build_batch_prompt(batch_text, 1, "English", "Russian", contexts=None)

        assert "App Context:" in prompt
        assert "- App Name: TestApp" in prompt
        assert "Texts to translate:\n<<ITEM_1>>" in prompt

    def test_batch_translation_prompt_without_app_context(self):
        """Test batch prompt without app context."""
        translator = GeminiTranslator(api_key="fake-key", app_context=None)

        batch_text = "<<ITEM_1>>\nHello\n<</ITEM_1>>"
        prompt = translator._build_batch_prompt(batch_text, 1, "English", "Russian", contexts=None)

        assert "App Context:" not in prompt
        assert "Texts to translate:\n<<ITEM_1>>" in prompt

    @pytest.mark.asyncio
    async def test_plural_translation_prompt_with_app_context(self):
        """Test that app context is added to plural translation prompt."""
        translator = GeminiTranslator(api_key="fake-key", app_context="- App Name: PluralApp")

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Hola"

            plural_forms = {"other": "%d items"}
            await translator._translate_plural_forms(plural_forms, "en", "es")

            # Get the prompt that was sent to the API
            mock_api.assert_called_once()
            prompt = mock_api.call_args[0][0]

            assert "App Context:" in prompt
            assert "- App Name: PluralApp" in prompt
            assert "Text to translate (other form):\n__PH_1__ items" in prompt

    @pytest.mark.asyncio
    async def test_plural_translation_prompt_without_app_context(self):
        """Test plural prompt without app context."""
        translator = GeminiTranslator(api_key="fake-key", app_context=None)

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Hola"

            plural_forms = {"other": "%d items"}
            await translator._translate_plural_forms(plural_forms, "en", "es")

            mock_api.assert_called_once()
            prompt = mock_api.call_args[0][0]

            assert "App Context:" not in prompt
            assert "Text to translate (other form):\n__PH_1__ items" in prompt
