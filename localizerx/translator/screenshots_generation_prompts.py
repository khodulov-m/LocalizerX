"""ASO-optimized prompts for generating App Store screenshot texts."""

from __future__ import annotations

from localizerx.parser.app_context import AppContext
from localizerx.parser.screenshots_model import (
    SCREENSHOT_TEXT_WORD_LIMIT,
    DeviceClass,
    ScreenshotTextType,
)


def build_generation_prompt(
    app_context: AppContext,
    screen_id: str,
    text_type: ScreenshotTextType,
    device_class: DeviceClass,
    user_hint: str | None = None,
) -> str:
    """
    Build an ASO-optimized prompt for generating screenshot text.

    Args:
        app_context: AppContext with app name, subtitle, promo, description
        screen_id: Identifier for the screenshot screen
        text_type: Type of text to generate (headline, subtitle, etc.)
        device_class: Target device class (small or large)
        user_hint: Optional hint describing what this screen shows

    Returns:
        Formatted prompt string for the Gemini API
    """
    type_guidance = _get_text_type_guidance(text_type)
    device_guidance = _get_device_guidance(device_class)

    # Build the prompt
    prompt = f"""You are an ASO (App Store Optimization) expert creating screenshot text for an iOS app.

APP CONTEXT:
{app_context.to_prompt_context()}

TASK: Generate a {text_type.value.upper()} for screenshot "{screen_id}"
"""

    if user_hint:
        prompt += f"""
SCREEN DESCRIPTION: {user_hint}
"""

    prompt += f"""
CRITICAL RULES:
1. MAXIMUM {SCREENSHOT_TEXT_WORD_LIMIT} WORDS - This is a HARD LIMIT, never exceed
2. {device_guidance}
3. Be compelling and marketing-focused
4. Highlight app benefits, not features
5. Use action verbs when appropriate
6. Make it memorable and punchy

TEXT TYPE: {text_type.value.upper()}
{type_guidance}

Output ONLY the text, nothing else (max {SCREENSHOT_TEXT_WORD_LIMIT} words):"""

    return prompt


def _get_text_type_guidance(text_type: ScreenshotTextType) -> str:
    """Get purpose and style guidance for a text type."""
    guidance = {
        ScreenshotTextType.HEADLINE: (
            "PURPOSE: Main attention-grabbing text on the screenshot.\n"
            "STYLE: Bold, impactful, conveys the core value proposition.\n"
            "TIPS: Use action verbs, highlight benefits, create urgency or curiosity."
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
    return guidance.get(text_type, "PURPOSE: Screenshot text element.")


def _get_device_guidance(device_class: DeviceClass) -> str:
    """Get guidance for device class."""
    if device_class == DeviceClass.SMALL:
        return "Device: SMALL screen (iPhone SE) - text must be EXTRA SHORT and punchy"
    return "Device: LARGE screen (iPad/Max) - can be slightly more descriptive but still brief"


def build_batch_generation_prompt(
    app_context: AppContext,
    items: list[tuple[str, ScreenshotTextType, DeviceClass, str | None]],
) -> str:
    """
    Build a batch generation prompt for multiple screenshot texts.

    Args:
        app_context: AppContext with app information
        items: List of (screen_id, text_type, device_class, user_hint) tuples

    Returns:
        Formatted prompt string for the Gemini API
    """
    # Build item descriptions
    items_block = []
    for i, (screen_id, text_type, device_class, hint) in enumerate(items, 1):
        device_note = "SHORT" if device_class == DeviceClass.SMALL else "NORMAL"
        hint_text = f" - {hint}" if hint else ""
        items_block.append(
            f"{i}. [{screen_id}] [{text_type.value}] [{device_note}]{hint_text}"
        )

    items_str = "\n".join(items_block)
    count = len(items)

    prompt = f"""You are an ASO (App Store Optimization) expert creating screenshot texts for an iOS app.

APP CONTEXT:
{app_context.to_prompt_context()}

TASK: Generate {count} screenshot texts for the following:

{items_str}

CRITICAL RULES (MUST FOLLOW FOR ALL):
1. MAXIMUM {SCREENSHOT_TEXT_WORD_LIMIT} WORDS per text - HARD LIMIT
2. Be compelling and marketing-focused
3. Highlight app benefits, not features
4. Use action verbs when appropriate
5. [SHORT] items should be extra concise for small screens
6. Make each text unique and memorable

Provide numbered results. Each must be {SCREENSHOT_TEXT_WORD_LIMIT} words max:"""

    return prompt
