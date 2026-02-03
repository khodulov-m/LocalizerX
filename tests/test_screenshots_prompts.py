"""Tests for screenshot text translation prompts and batch response parsing."""

import pytest

from localizerx.config import ScreenshotsConfig
from localizerx.parser.screenshots_model import (
    SCREENSHOT_TEXT_WORD_LIMIT,
    DeviceClass,
    ScreenshotTextType,
)
from localizerx.translator.screenshots_prompts import (
    build_batch_screenshot_prompt,
    build_screenshot_prompt,
    parse_batch_screenshot_response,
)


class TestBuildScreenshotPrompt:
    def test_contains_source_and_target_languages(self):
        prompt = build_screenshot_prompt(
            "Hello", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "en", "fr"
        )
        assert "English" in prompt
        assert "French" in prompt

    def test_contains_original_text(self):
        prompt = build_screenshot_prompt(
            "Hello World", ScreenshotTextType.HEADLINE, DeviceClass.LARGE, "en", "de"
        )
        assert "Hello World" in prompt

    def test_contains_word_limit(self):
        prompt = build_screenshot_prompt(
            "Test", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "en", "es"
        )
        assert str(SCREENSHOT_TEXT_WORD_LIMIT) in prompt

    def test_headline_type_name(self):
        prompt = build_screenshot_prompt(
            "Test", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "en", "fr"
        )
        assert "HEADLINE" in prompt

    def test_subtitle_type_name(self):
        prompt = build_screenshot_prompt(
            "Test", ScreenshotTextType.SUBTITLE, DeviceClass.SMALL, "en", "fr"
        )
        assert "SUBTITLE" in prompt

    def test_button_type_name(self):
        prompt = build_screenshot_prompt(
            "Test", ScreenshotTextType.BUTTON, DeviceClass.SMALL, "en", "fr"
        )
        assert "BUTTON" in prompt

    def test_small_device_extra_short(self):
        prompt = build_screenshot_prompt(
            "Test", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "en", "fr"
        )
        assert "EXTRA SHORT" in prompt

    def test_large_device_context(self):
        prompt = build_screenshot_prompt(
            "Test", ScreenshotTextType.HEADLINE, DeviceClass.LARGE, "en", "fr"
        )
        assert "Large screen" in prompt

    def test_word_count_reported(self):
        prompt = build_screenshot_prompt(
            "One two three", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "en", "fr"
        )
        assert "3 words" in prompt


class TestBuildBatchScreenshotPrompt:
    def test_contains_all_source_texts(self):
        items = [
            ("screen_1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Hello"),
            ("screen_1", ScreenshotTextType.SUBTITLE, DeviceClass.LARGE, "Welcome"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "fr")
        assert "Hello" in prompt
        assert "Welcome" in prompt

    def test_contains_screen_ids(self):
        items = [
            ("screen_1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "A"),
            ("screen_2", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "B"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "de")
        assert "screen_1" in prompt
        assert "screen_2" in prompt

    def test_contains_item_count(self):
        items = [
            ("s1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "A"),
            ("s2", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "B"),
            ("s3", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "C"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "de")
        assert "3" in prompt

    def test_device_notes_short_and_normal(self):
        items = [
            ("s1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Short"),
            ("s2", ScreenshotTextType.HEADLINE, DeviceClass.LARGE, "Longer"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "fr")
        assert "SHORT" in prompt
        assert "NORMAL" in prompt

    def test_contains_languages(self):
        items = [("s1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Test")]
        prompt = build_batch_screenshot_prompt(items, "en", "ja")
        assert "English" in prompt
        assert "Japanese" in prompt

    def test_sequential_numbering(self):
        items = [
            ("s1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "First"),
            ("s2", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Second"),
            ("s3", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Third"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "fr")
        assert "1." in prompt
        assert "2." in prompt
        assert "3." in prompt

    def test_word_limit_in_prompt(self):
        items = [("s1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Test")]
        prompt = build_batch_screenshot_prompt(items, "en", "fr")
        assert str(SCREENSHOT_TEXT_WORD_LIMIT) in prompt

    def test_text_type_values_in_prompt(self):
        items = [
            ("s1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "H"),
            ("s1", ScreenshotTextType.BUTTON, DeviceClass.SMALL, "B"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "fr")
        assert "headline" in prompt
        assert "button" in prompt


class TestParseBatchScreenshotResponse:
    def test_clean_numbered_response(self):
        response = "1. Bonjour\n2. Le monde\n3. Cliquez"
        result = parse_batch_screenshot_response(response, 3)
        assert result == ["Bonjour", "Le monde", "Cliquez"]

    def test_strips_whitespace(self):
        response = "1.  Bonjour  \n2.  Le monde  "
        result = parse_batch_screenshot_response(response, 2)
        assert result == ["Bonjour", "Le monde"]

    def test_echoed_markers_stripped(self):
        response = (
            "1. [screen_1] [headline] [SHORT]: Bonjour\n"
            "2. [screen_1] [subtitle] [NORMAL]: Le monde"
        )
        result = parse_batch_screenshot_response(response, 2)
        assert result == ["Bonjour", "Le monde"]

    def test_parenthesis_numbering(self):
        response = "1) Bonjour\n2) Le monde"
        result = parse_batch_screenshot_response(response, 2)
        assert result == ["Bonjour", "Le monde"]

    def test_partial_response_pads_empty(self):
        response = "1. Bonjour"
        result = parse_batch_screenshot_response(response, 3)
        assert result == ["Bonjour", "", ""]

    def test_empty_response(self):
        result = parse_batch_screenshot_response("", 2)
        assert result == ["", ""]

    def test_markdown_bold_stripped(self):
        response = "1. **Bonjour**\n2. **Le monde**"
        result = parse_batch_screenshot_response(response, 2)
        assert result == ["Bonjour", "Le monde"]

    def test_single_item(self):
        response = "1. Единственный текст"
        result = parse_batch_screenshot_response(response, 1)
        assert result == ["Единственный текст"]

    def test_leading_whitespace_on_lines(self):
        response = "  1. Bonjour\n  2. Le monde"
        result = parse_batch_screenshot_response(response, 2)
        assert result == ["Bonjour", "Le monde"]

    def test_preamble_text_ignored(self):
        response = "Here are the translations:\n\n1. Bonjour\n2. Le monde"
        result = parse_batch_screenshot_response(response, 2)
        assert result == ["Bonjour", "Le monde"]

    def test_double_digit_numbering(self):
        lines = [f"{i}. Item {i}" for i in range(1, 13)]
        response = "\n".join(lines)
        result = parse_batch_screenshot_response(response, 12)
        assert len(result) == 12
        assert result[0] == "Item 1"
        assert result[9] == "Item 10"
        assert result[11] == "Item 12"

    def test_number_in_content_not_confused(self):
        # "2x" inside item 1 must not be parsed as item 2
        response = "1. Use 2x zoom\n2. Fast speed"
        result = parse_batch_screenshot_response(response, 2)
        assert result[0] == "Use 2x zoom"
        assert result[1] == "Fast speed"

    def test_single_bracket_group_stripped(self):
        response = "1. [headline]: Bold move"
        result = parse_batch_screenshot_response(response, 1)
        assert result == ["Bold move"]

    def test_echoed_markers_without_colon(self):
        response = "1. [screen_1] [headline] [SHORT] Bonjour"
        result = parse_batch_screenshot_response(response, 1)
        assert result == ["Bonjour"]


class TestBatchRoundTrip:
    """Verify prompt/parse contract with simulated model responses."""

    def test_three_items(self):
        items = [
            ("screen_1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Hello"),
            ("screen_2", ScreenshotTextType.SUBTITLE, DeviceClass.LARGE, "Features"),
            ("screen_3", ScreenshotTextType.BUTTON, DeviceClass.SMALL, "Start"),
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "fr")
        assert prompt

        simulated = "1. Bonjour\n2. Fonctionnalités\n3. Démarrer"
        parsed = parse_batch_screenshot_response(simulated, len(items))
        assert parsed == ["Bonjour", "Fonctionnalités", "Démarrer"]

    def test_twelve_items(self):
        items = [
            (f"screen_{i}", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, f"Text {i}")
            for i in range(1, 13)
        ]
        prompt = build_batch_screenshot_prompt(items, "en", "de")
        assert "12" in prompt

        simulated = "\n".join(f"{i}. Translation {i}" for i in range(1, 13))
        parsed = parse_batch_screenshot_response(simulated, 12)

        assert len(parsed) == 12
        for i in range(12):
            assert parsed[i] == f"Translation {i + 1}"

    def test_echoed_markers_response(self):
        items = [
            ("screen_1", ScreenshotTextType.HEADLINE, DeviceClass.SMALL, "Hello"),
            ("screen_2", ScreenshotTextType.SUBTITLE, DeviceClass.LARGE, "Discover"),
        ]
        build_batch_screenshot_prompt(items, "en", "de")

        # Model echoes back input markers — common LLM behaviour
        simulated = (
            "1. [screen_1] [headline] [SHORT]: Hallo\n"
            "2. [screen_2] [subtitle] [NORMAL]: Entdecken"
        )
        parsed = parse_batch_screenshot_response(simulated, 2)
        assert parsed == ["Hallo", "Entdecken"]


class TestScreenshotsConfigBatchSize:
    def test_default_batch_size(self):
        cfg = ScreenshotsConfig()
        assert cfg.batch_size == 10

    def test_custom_batch_size(self):
        cfg = ScreenshotsConfig(batch_size=25)
        assert cfg.batch_size == 25

    def test_batch_size_minimum_boundary(self):
        cfg = ScreenshotsConfig(batch_size=1)
        assert cfg.batch_size == 1

    def test_batch_size_maximum_boundary(self):
        cfg = ScreenshotsConfig(batch_size=50)
        assert cfg.batch_size == 50

    def test_batch_size_below_minimum_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScreenshotsConfig(batch_size=0)

    def test_batch_size_above_maximum_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScreenshotsConfig(batch_size=51)
