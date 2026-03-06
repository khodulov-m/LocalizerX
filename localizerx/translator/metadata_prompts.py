"""Specialized prompts for App Store metadata translation."""

from __future__ import annotations

import re

from localizerx.parser.metadata_model import FIELD_LIMITS, MetadataFieldType
from localizerx.utils.locale import get_fastlane_locale_name


def build_metadata_prompt(
    text: str,
    field_type: MetadataFieldType,
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build a context-aware translation prompt for App Store metadata.

    Args:
        text: The text to translate
        field_type: The type of metadata field
        src_lang: Source language code
        tgt_lang: Target language code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_fastlane_locale_name(src_lang)
    tgt_name = get_fastlane_locale_name(tgt_lang)
    limit = FIELD_LIMITS[field_type]

    field_context = _get_field_context(field_type)
    field_rules = _get_field_rules(field_type)

    field_name = field_type.value.replace("_", " ")
    prompt = f"""Translate the following App Store {field_name} from {src_name} to {tgt_name}.

CHARACTER LIMIT: {limit} characters maximum. The translation MUST fit within this limit.

FIELD PURPOSE: {field_context}

TRANSLATION RULES:
1. Translate naturally, adapting to {tgt_name} conventions
2. Keep the translation within {limit} characters - this is a HARD requirement
3. Preserve the tone and marketing appeal of the original
4. This is for the Apple App Store
{field_rules}

Original text ({len(text)} chars):
{text}

Translation (max {limit} chars, only provide the translated text):"""

    return prompt


def _get_field_context(field_type: MetadataFieldType) -> str:
    """Get context description for a field type."""
    contexts = {
        MetadataFieldType.NAME: (
            "The app name displayed on the App Store. Should be memorable, "
            "clear, and convey the app's purpose."
        ),
        MetadataFieldType.SUBTITLE: (
            "A brief tagline that appears below the app name. Should complement "
            "the name and highlight a key feature or benefit."
        ),
        MetadataFieldType.KEYWORDS: (
            "Comma-separated search keywords for App Store optimization. "
            "Keywords help users find the app through search."
        ),
        MetadataFieldType.DESCRIPTION: (
            "The full app description shown on the App Store product page. "
            "Should explain features, benefits, and use cases."
        ),
        MetadataFieldType.PROMOTIONAL_TEXT: (
            "Short promotional text that appears above the description. "
            "Often used for announcements, new features, or special offers."
        ),
        MetadataFieldType.RELEASE_NOTES: (
            "What's new in this version. Lists new features, improvements, "
            "and bug fixes for users."
        ),
    }
    return contexts.get(field_type, "App Store metadata field")


def _get_field_rules(field_type: MetadataFieldType) -> str:
    """Get specific rules for a field type."""
    rules = {
        MetadataFieldType.NAME: (
            "5. Keep it short and impactful\n" "6. Do not add punctuation unless in original"
        ),
        MetadataFieldType.SUBTITLE: (
            "5. Be concise and descriptive\n" "6. Avoid repeating words from the app name"
        ),
        MetadataFieldType.KEYWORDS: (
            "5. CRITICAL: Keep the comma-separated format exactly\n"
            "6. Translate each keyword individually\n"
            "7. Do NOT add new keywords or remove any\n"
            "8. Keep commas as separators (no spaces after commas)"
        ),
        MetadataFieldType.DESCRIPTION: (
            "5. Maintain paragraph structure and formatting\n"
            "6. Preserve any bullet points or lists\n"
            "7. Keep feature names if they are product names"
        ),
        MetadataFieldType.PROMOTIONAL_TEXT: (
            "5. Keep the promotional/marketing tone\n" "6. Be engaging and action-oriented"
        ),
        MetadataFieldType.RELEASE_NOTES: (
            "5. Maintain bullet points or numbered lists\n"
            "6. Keep version numbers and technical terms unchanged\n"
            "7. Preserve emoji if present"
        ),
    }
    return rules.get(field_type, "")


def build_keywords_prompt(
    keywords: str,
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build a specialized prompt for translating App Store keywords.

    Keywords require special handling to preserve the comma-separated format
    and ensure each keyword is translated individually.

    Args:
        keywords: Comma-separated keywords string
        src_lang: Source language code
        tgt_lang: Target language code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_fastlane_locale_name(src_lang)
    tgt_name = get_fastlane_locale_name(tgt_lang)
    limit = FIELD_LIMITS[MetadataFieldType.KEYWORDS]

    # Split keywords for clarity
    keyword_list = [k.strip() for k in keywords.split(",")]
    keyword_count = len(keyword_list)

    prompt = f"""Translate these {keyword_count} App Store keywords from {src_name} to {tgt_name}.

CHARACTER LIMIT: {limit} characters total for all keywords combined.

CURRENT KEYWORDS (separated by commas):
{keywords}

TRANSLATION RULES:
1. Translate each keyword individually
2. Keep the same comma-separated format
3. Do NOT add or remove keywords
4. Total length must be under {limit} characters
5. No spaces after commas
6. Keywords should be relevant search terms in {tgt_name}

Example format: keyword1,keyword2,keyword3

Translated keywords (comma-separated, max {limit} chars):"""

    return prompt


def build_batch_metadata_prompt(
    items: list[tuple[MetadataFieldType, str]],
    src_lang: str,
    tgt_lang: str,
) -> str:
    """
    Build a batch translation prompt for multiple metadata fields.

    Uses <<ITEM_N>> markers for reliable response parsing.

    Args:
        items: List of (field_type, text) tuples
        src_lang: Source language code
        tgt_lang: Target language code

    Returns:
        Formatted prompt string for the Gemini API
    """
    src_name = get_fastlane_locale_name(src_lang)
    tgt_name = get_fastlane_locale_name(tgt_lang)

    fields_text = []
    for i, (field_type, text) in enumerate(items, 1):
        limit = FIELD_LIMITS[field_type]
        field_name = field_type.value.replace("_", " ").upper()
        fields_text.append(
            f"<<ITEM_{i}>>\n[{field_name}] (max {limit} chars):\n{text}\n<</ITEM_{i}>>"
        )

    batch_text = "\n\n".join(fields_text)
    count = len(items)

    prompt = f"""Translate the following {count} App Store metadata fields from {src_name} to {tgt_name}.

IMPORTANT RULES:
- Each field has a CHARACTER LIMIT that MUST be respected
- Translate naturally, preserving the marketing tone
- For KEYWORDS: Keep comma-separated format exactly, same number of keywords, no spaces after commas
- Return translations using the EXACT SAME <<ITEM_N>> markers
- Do NOT include field labels like [NAME] in your response — only the translated text inside each marker

Fields to translate:

{batch_text}

Translations (output exactly {count} items using <<ITEM_1>> through <<ITEM_{count}>> markers, only the translated text inside each marker):"""

    return prompt


def parse_batch_metadata_response(response: str, count: int) -> list[str]:
    """
    Parse batch metadata response using <<ITEM_N>> markers.

    Args:
        response: Raw API response string
        count: Expected number of translations

    Returns:
        List of translated texts in order, empty string for missing items
    """
    results: list[str] = []
    for i in range(1, count + 1):
        pattern = rf"<<ITEM_{i}>>\s*(.*?)\s*<</ITEM_{i}>>"
        match = re.search(pattern, response, re.DOTALL)
        results.append(match.group(1).strip() if match else "")

    return results
