"""ASO-optimized prompts for App Store screenshot text translation."""

from __future__ import annotations

import re

from localizerx.parser.screenshots_model import (
    SCREENSHOT_TEXT_WORD_LIMIT,
    DeviceClass,
    ScreenshotTextType,
)
from localizerx.utils.locale import get_language_name


def build_screenshot_prompt(
    text: str,
    text_type: ScreenshotTextType,
    device_class: DeviceClass,
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build an ASO-optimized translation prompt for screenshot text.

    The prompt enforces:
    - Maximum 5 words (hard limit)
    - Marketing-oriented language adaptation (not literal translation)
    - Local market optimization
    - Device-size awareness (small = shorter, large = can be slightly longer)

    Args:
        text: The text to translate
        text_type: Type of screenshot text (headline, subtitle, etc.)
        device_class: Target device class (small or large)
        src_lang: Source language code
        tgt_lang: Target language code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_language_name(src_lang)
    tgt_name = get_language_name(tgt_lang)

    text_context = _get_text_type_context(text_type)
    device_context = _get_device_context(device_class)

    word_count = len(text.split())
    type_name = text_type.value.upper()

    prompt = f"""Adapt this App Store screenshot {type_name} from {src_name} to {tgt_name}.

CRITICAL RULES (MUST FOLLOW):
1. MAXIMUM {SCREENSHOT_TEXT_WORD_LIMIT} WORDS - This is a HARD LIMIT, never exceed
2. Do NOT translate literally - ADAPT for the {tgt_name} market
3. Use natural, marketing-oriented language that resonates locally
4. Optimize for ASO (App Store Optimization) - make it compelling
5. {device_context}

TEXT TYPE: {text_type.value}
{text_context}

WORD COUNT: Original has {word_count} words. Max {SCREENSHOT_TEXT_WORD_LIMIT} words allowed.

Original text:
{text}

Provide ONLY the adapted text, nothing else. Max {SCREENSHOT_TEXT_WORD_LIMIT} words:"""

    return prompt


def _get_text_type_context(text_type: ScreenshotTextType) -> str:
    """Get context description for a text type."""
    contexts = {
        ScreenshotTextType.HEADLINE: (
            "PURPOSE: Main attention-grabbing text on the screenshot.\n"
            "STYLE: Bold, impactful, conveys the core value proposition.\n"
            "TIPS: Use action verbs, highlight benefits, create urgency."
        ),
        ScreenshotTextType.SUBTITLE: (
            "PURPOSE: Supporting text that elaborates on the headline.\n"
            "STYLE: Complementary, adds context without repeating the headline.\n"
            "TIPS: Explain the 'how' or 'why', add emotional appeal."
        ),
        ScreenshotTextType.BUTTON: (
            "PURPOSE: Call-to-action button text.\n"
            "STYLE: Action-oriented, compelling, creates sense of value.\n"
            "TIPS: Use imperative verbs, suggest immediate benefit."
        ),
        ScreenshotTextType.CAPTION: (
            "PURPOSE: Descriptive text explaining a feature or element.\n"
            "STYLE: Clear, informative, highlights functionality.\n"
            "TIPS: Focus on user benefits, not technical features."
        ),
        ScreenshotTextType.CALLOUT: (
            "PURPOSE: Attention-drawing annotation or highlight.\n"
            "STYLE: Brief, punchy, draws eye to important element.\n"
            "TIPS: Use exclamation sparingly, highlight uniqueness."
        ),
    }
    return contexts.get(text_type, "PURPOSE: Screenshot text element.")


def _get_device_context(device_class: DeviceClass) -> str:
    """Get context for device class."""
    if device_class == DeviceClass.SMALL:
        return "DEVICE: Small screen (iPhone SE). Text must be EXTRA SHORT and concise."
    return "DEVICE: Large screen (iPad/Max). Can be slightly more descriptive but still brief."


def build_batch_screenshot_prompt(
    items: list[tuple[str, ScreenshotTextType, DeviceClass, str]],
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build a batch translation prompt for multiple screenshot texts.

    Args:
        items: List of (screen_id, text_type, device_class, text) tuples
        src_lang: Source language code
        tgt_lang: Target language code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_language_name(src_lang)
    tgt_name = get_language_name(tgt_lang)

    texts_block = []
    for i, (screen_id, text_type, device_class, text) in enumerate(items, 1):
        device_note = "SHORT" if device_class == DeviceClass.SMALL else "NORMAL"
        texts_block.append(f"{i}. [{screen_id}] [{text_type.value}] [{device_note}]: {text}")

    texts_str = "\n".join(texts_block)
    count = len(items)

    prompt = f"""Adapt these {count} App Store screenshot texts from {src_name} to {tgt_name}.

CRITICAL RULES (MUST FOLLOW FOR ALL):
1. MAXIMUM {SCREENSHOT_TEXT_WORD_LIMIT} WORDS per text - HARD LIMIT
2. Do NOT translate literally - ADAPT for {tgt_name} market
3. Use natural, marketing-oriented language
4. Optimize for ASO (App Store Optimization)
5. [SHORT] items should be extra concise

Texts to adapt:

{texts_str}

Provide numbered translations. Each must be {SCREENSHOT_TEXT_WORD_LIMIT} words max:"""

    return prompt


def parse_batch_screenshot_response(response: str, expected_count: int) -> list[str]:
    """Parse numbered translations from a batch screenshot prompt response.

    Handles common model response formats:
    - "1. Text" / "1) Text"
    - "1. [screen_1] [headline] [SHORT]: Text" (echoed input markers)
    - "1. **Text**" (markdown bold)

    Args:
        response: Raw text response from the API
        expected_count: Number of translations expected

    Returns:
        List of parsed translations, padded with empty strings if missing
    """
    results: list[str] = []
    for i in range(1, expected_count + 1):
        pattern = rf"^\s*{i}[\.\)]\s*(.+)"
        match = re.search(pattern, response, re.MULTILINE)
        if match:
            text = match.group(1).strip()
            # Strip markdown bold markers first — they may wrap echoed input markers,
            # blocking the bracket regex if left in place
            text = text.replace("**", "")
            # Strip echoed input markers like [screen_1] [headline] [SHORT]:
            text = re.sub(r"^(?:\[[^\]]*\]\s*)+:?\s*", "", text)
            results.append(text.strip())
        else:
            results.append("")
    return results
