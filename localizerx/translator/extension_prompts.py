"""Specialized prompts for Chrome Extension localization."""

from __future__ import annotations

from localizerx.parser.extension_model import EXTENSION_FIELD_LIMITS, ExtensionFieldType
from localizerx.utils.locale import get_chrome_locale_name


def build_extension_field_prompt(
    text: str,
    key: str,
    description: str | None,
    field_type: ExtensionFieldType,
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build a context-aware translation prompt for a Chrome Web Store field.

    Args:
        text: The text to translate
        key: The message key
        description: The message description from messages.json
        field_type: The CWS field type
        src_lang: Source Chrome locale code
        tgt_lang: Target Chrome locale code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_chrome_locale_name(src_lang)
    tgt_name = get_chrome_locale_name(tgt_lang)
    limit = EXTENSION_FIELD_LIMITS[field_type]

    field_context = _get_extension_field_context(field_type)
    field_rules = _get_extension_field_rules(field_type)

    desc_line = ""
    if description:
        desc_line = f"\nDEVELOPER NOTE: {description}"

    field_label = field_type.value
    header = f"Translate the following Chrome Web Store {field_label}"
    prompt = f"""{header} from {src_name} to {tgt_name}.

CHARACTER LIMIT: {limit} characters maximum. The translation MUST fit within this limit.

FIELD PURPOSE: {field_context}
{desc_line}
TRANSLATION RULES:
1. Translate naturally, adapting to {tgt_name} conventions
2. Keep the translation within {limit} characters - this is a HARD requirement
3. Preserve the tone and marketing appeal of the original
4. This is for a Chrome Web Store listing - optimize for discoverability
{field_rules}

Original text ({len(text)} chars):
{text}

Translation (max {limit} chars, only provide the translated text):"""

    return prompt


def _get_extension_field_context(field_type: ExtensionFieldType) -> str:
    """Get context description for a CWS field type."""
    contexts = {
        ExtensionFieldType.APP_NAME: (
            "The extension name displayed on the Chrome Web Store. "
            "Should be memorable, clear, and convey the extension's purpose. "
            "This is the primary identifier users see when browsing the store."
        ),
        ExtensionFieldType.SHORT_NAME: (
            "A very short name used when space is limited (e.g., app launcher). "
            "Must be extremely concise while still recognizable."
        ),
        ExtensionFieldType.DESCRIPTION: (
            "A brief description shown on the Chrome Web Store listing. "
            "Should clearly communicate the extension's value proposition "
            "and key features in a single compelling sentence."
        ),
    }
    return contexts.get(field_type, "Chrome Web Store metadata field")


def _get_extension_field_rules(field_type: ExtensionFieldType) -> str:
    """Get specific rules for a CWS field type."""
    rules = {
        ExtensionFieldType.APP_NAME: (
            "5. Keep it short and impactful\n"
            "6. Do not add punctuation unless in original\n"
            "7. Preserve brand names or technical terms"
        ),
        ExtensionFieldType.SHORT_NAME: (
            "5. Maximum brevity is critical - only 12 characters\n"
            "6. Use abbreviations if needed in the target language\n"
            "7. This may be a truncated form of the full name"
        ),
        ExtensionFieldType.DESCRIPTION: (
            "5. Write a compelling, SEO-friendly description\n"
            "6. Include relevant keywords naturally\n"
            "7. Maintain the same information density as the original"
        ),
    }
    return rules.get(field_type, "")


def build_extension_batch_prompt(
    items: list[tuple[str, str, str | None]],
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build a batch translation prompt for regular extension messages.

    Args:
        items: List of (key, message, description) tuples
        src_lang: Source Chrome locale code
        tgt_lang: Target Chrome locale code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_chrome_locale_name(src_lang)
    tgt_name = get_chrome_locale_name(tgt_lang)

    texts = []
    for i, (key, message, description) in enumerate(items, 1):
        entry = f"{i}. {message}"
        if description:
            entry += f" [Context: {description}]"
        texts.append(entry)

    batch_text = "\n".join(texts)
    count = len(items)

    header = f"Translate the following {count} Chrome Extension messages"
    prompt = f"""{header} from {src_name} to {tgt_name}.

IMPORTANT RULES:
1. Keep all placeholders exactly as they are (like __PH_1__, __PH_2__, $PLACEHOLDER$, $1, etc.)
2. Preserve any formatting and punctuation style
3. Translate naturally, not word-for-word
4. This is for a Chrome browser extension
5. Return ONLY the translations, numbered to match the input
6. Use the [Context] hints to improve translation quality

Messages to translate:
{batch_text}

Translations (numbered to match, one per line):"""

    return prompt
