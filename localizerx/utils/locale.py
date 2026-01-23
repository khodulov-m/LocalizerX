"""Language and locale utilities."""

from __future__ import annotations

# Common iOS/macOS locale codes and their display names
LANGUAGE_NAMES: dict[str, str] = {
    # Common languages
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "pt-BR": "Portuguese (Brazil)",
    "pt-PT": "Portuguese (Portugal)",
    "zh": "Chinese",
    "zh-Hans": "Chinese (Simplified)",
    "zh-Hant": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "hi": "Hindi",
    "bn": "Bengali",
    "uk": "Ukrainian",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "hu": "Hungarian",
    "ro": "Romanian",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "nb": "Norwegian Bokmål",
    "no": "Norwegian",
    "sk": "Slovak",
    "ca": "Catalan",
    "hr": "Croatian",
    "bg": "Bulgarian",
    "sr": "Serbian",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "fa": "Persian",
    "sw": "Swahili",
    "fil": "Filipino",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "mr": "Marathi",
    "gu": "Gujarati",
    # Regional variants
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "en-AU": "English (Australia)",
    "en-CA": "English (Canada)",
    "es-ES": "Spanish (Spain)",
    "es-MX": "Spanish (Mexico)",
    "es-419": "Spanish (Latin America)",
    "fr-FR": "French (France)",
    "fr-CA": "French (Canada)",
    "de-DE": "German (Germany)",
    "de-AT": "German (Austria)",
    "de-CH": "German (Switzerland)",
}

# Valid language codes (ISO 639-1 and common variants)
VALID_CODES = set(LANGUAGE_NAMES.keys())


def validate_language_code(code: str) -> bool:
    """
    Check if a language code is valid.

    Accepts ISO 639-1 codes and common variants (e.g., 'en', 'zh-Hans', 'pt-BR').
    """
    # Check exact match
    if code in VALID_CODES:
        return True

    # Check base language code
    base = code.split("-")[0]
    if base in VALID_CODES:
        return True

    # Allow any two-letter code as potentially valid
    if len(base) == 2 and base.isalpha():
        return True

    return False


def get_language_name(code: str) -> str:
    """
    Get the display name for a language code.

    Returns the code itself if no name is found.
    """
    if code in LANGUAGE_NAMES:
        return LANGUAGE_NAMES[code]

    # Try base language
    base = code.split("-")[0]
    if base in LANGUAGE_NAMES:
        return LANGUAGE_NAMES[base]

    return code


def normalize_language_code(code: str) -> str:
    """
    Normalize a language code to standard format.

    Examples:
        >>> normalize_language_code("EN")
        'en'
        >>> normalize_language_code("zh_hans")
        'zh-Hans'
    """
    # Replace underscores with hyphens
    code = code.replace("_", "-")

    # Split into parts
    parts = code.split("-")

    if len(parts) == 1:
        return parts[0].lower()

    # Lowercase language, proper case script/region
    result = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4:  # Script (e.g., Hans, Hant)
            result.append(part.capitalize())
        else:  # Region (e.g., US, BR)
            result.append(part.upper())

    return "-".join(result)


def parse_language_list(value: str) -> list[str]:
    """
    Parse a comma-separated list of language codes.

    Examples:
        >>> parse_language_list("fr,es,de")
        ['fr', 'es', 'de']
        >>> parse_language_list("zh-Hans, ja, ko")
        ['zh-Hans', 'ja', 'ko']
    """
    codes = [normalize_language_code(c.strip()) for c in value.split(",")]
    return [c for c in codes if c]
