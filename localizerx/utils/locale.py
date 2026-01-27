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


# Fastlane locale codes used in App Store Connect metadata
# Format: "locale-code" -> "Display Name"
FASTLANE_LOCALES: dict[str, str] = {
    "ar-SA": "Arabic",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de-DE": "German (Germany)",
    "el": "Greek",
    "en-AU": "English (Australia)",
    "en-CA": "English (Canada)",
    "en-GB": "English (UK)",
    "en-US": "English (US)",
    "es-ES": "Spanish (Spain)",
    "es-MX": "Spanish (Mexico)",
    "fi": "Finnish",
    "fr-CA": "French (Canada)",
    "fr-FR": "French (France)",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl-NL": "Dutch (Netherlands)",
    "no": "Norwegian",
    "pl": "Polish",
    "pt-BR": "Portuguese (Brazil)",
    "pt-PT": "Portuguese (Portugal)",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh-Hans": "Chinese (Simplified)",
    "zh-Hant": "Chinese (Traditional)",
}

# Mapping from fastlane locale codes to xcstrings locale codes
FASTLANE_TO_XCSTRINGS: dict[str, str] = {
    "ar-SA": "ar",
    "de-DE": "de",
    "en-AU": "en-AU",
    "en-CA": "en-CA",
    "en-GB": "en-GB",
    "en-US": "en",
    "es-ES": "es",
    "es-MX": "es-MX",
    "fr-CA": "fr-CA",
    "fr-FR": "fr",
    "nl-NL": "nl",
    "pt-BR": "pt-BR",
    "pt-PT": "pt-PT",
    "zh-Hans": "zh-Hans",
    "zh-Hant": "zh-Hant",
}

# Reverse mapping from xcstrings to fastlane
XCSTRINGS_TO_FASTLANE: dict[str, str] = {
    "ar": "ar-SA",
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "nl": "nl-NL",
}


def fastlane_to_xcstrings(code: str) -> str:
    """
    Convert a fastlane locale code to an xcstrings locale code.

    Examples:
        >>> fastlane_to_xcstrings("en-US")
        'en'
        >>> fastlane_to_xcstrings("de-DE")
        'de'
        >>> fastlane_to_xcstrings("ja")
        'ja'
    """
    # Check explicit mapping
    if code in FASTLANE_TO_XCSTRINGS:
        return FASTLANE_TO_XCSTRINGS[code]

    # If no mapping, return as-is (many codes are the same)
    return code


def xcstrings_to_fastlane(code: str) -> str:
    """
    Convert an xcstrings locale code to a fastlane locale code.

    Examples:
        >>> xcstrings_to_fastlane("en")
        'en-US'
        >>> xcstrings_to_fastlane("de")
        'de-DE'
        >>> xcstrings_to_fastlane("ja")
        'ja'
    """
    # Check explicit mapping
    if code in XCSTRINGS_TO_FASTLANE:
        return XCSTRINGS_TO_FASTLANE[code]

    # If no mapping, return as-is
    return code


def validate_fastlane_locale(code: str) -> bool:
    """
    Check if a locale code is valid for fastlane/App Store Connect.

    Examples:
        >>> validate_fastlane_locale("en-US")
        True
        >>> validate_fastlane_locale("ja")
        True
        >>> validate_fastlane_locale("invalid")
        False
    """
    return code in FASTLANE_LOCALES


def get_fastlane_locale_name(code: str) -> str:
    """
    Get the display name for a fastlane locale code.

    Returns the code itself if no name is found.
    """
    if code in FASTLANE_LOCALES:
        return FASTLANE_LOCALES[code]

    # Try to get from general language names
    return get_language_name(code)


def parse_fastlane_locale_list(value: str) -> list[str]:
    """
    Parse a comma-separated list of fastlane locale codes.

    Unlike parse_language_list, this preserves the exact case
    since fastlane locales are case-sensitive.

    Examples:
        >>> parse_fastlane_locale_list("de-DE,fr-FR,es-ES")
        ['de-DE', 'fr-FR', 'es-ES']
    """
    codes = [c.strip() for c in value.split(",")]
    return [c for c in codes if c]


# Chrome Extension locale codes (underscore notation) and their display names
# See https://developer.chrome.com/docs/extensions/reference/api/i18n
CHROME_LOCALES: dict[str, str] = {
    "ar": "Arabic",
    "am": "Amharic",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "en_AU": "English (Australia)",
    "en_GB": "English (UK)",
    "en_US": "English (US)",
    "es": "Spanish",
    "es_419": "Spanish (Latin America)",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fil": "Filipino",
    "fr": "French",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "kn": "Kannada",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "ml": "Malayalam",
    "mr": "Marathi",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt_BR": "Portuguese (Brazil)",
    "pt_PT": "Portuguese (Portugal)",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh_CN": "Chinese (Simplified)",
    "zh_TW": "Chinese (Traditional)",
}


def validate_chrome_locale(code: str) -> bool:
    """
    Check if a locale code is valid for Chrome Extensions.

    Accepts underscore notation (pt_BR) as used by Chrome.

    Examples:
        >>> validate_chrome_locale("en")
        True
        >>> validate_chrome_locale("pt_BR")
        True
        >>> validate_chrome_locale("invalid")
        False
    """
    return code in CHROME_LOCALES


def get_chrome_locale_name(code: str) -> str:
    """
    Get the display name for a Chrome locale code.

    Returns the code itself if no name is found.
    """
    if code in CHROME_LOCALES:
        return CHROME_LOCALES[code]
    return get_language_name(chrome_to_standard_locale(code))


def parse_chrome_locale_list(value: str) -> list[str]:
    """
    Parse a comma-separated list of Chrome locale codes.

    Accepts hyphens and auto-converts to Chrome underscore format.

    Examples:
        >>> parse_chrome_locale_list("fr,pt-BR,zh-CN")
        ['fr', 'pt_BR', 'zh_CN']
        >>> parse_chrome_locale_list("de, es, ja")
        ['de', 'es', 'ja']
    """
    codes = [standard_to_chrome_locale(c.strip()) for c in value.split(",")]
    return [c for c in codes if c]


def chrome_to_standard_locale(code: str) -> str:
    """
    Convert Chrome underscore locale to standard hyphen format.

    Examples:
        >>> chrome_to_standard_locale("pt_BR")
        'pt-BR'
        >>> chrome_to_standard_locale("en")
        'en'
    """
    return code.replace("_", "-")


def standard_to_chrome_locale(code: str) -> str:
    """
    Convert standard hyphen locale to Chrome underscore format.

    Examples:
        >>> standard_to_chrome_locale("pt-BR")
        'pt_BR'
        >>> standard_to_chrome_locale("en")
        'en'
    """
    return code.replace("-", "_")
