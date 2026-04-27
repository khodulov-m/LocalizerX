"""CLDR plural rules per language.

Provides the list of plural categories required for each language and a
human-readable description of when each category applies (number ranges).
The descriptions are designed to be injected into LLM prompts so the model
can produce correct grammatical forms for languages with non-trivial plural
systems (Slavic, Arabic, Celtic, etc.).

Sources:
- Unicode CLDR Plural Rules: https://cldr.unicode.org/index/cldr-spec/plural-rules
- Apple xcstrings plural categories: zero, one, two, few, many, other
- Android plurals quantities: zero, one, two, few, many, other
"""

from __future__ import annotations

ALL_CATEGORIES: tuple[str, ...] = ("zero", "one", "two", "few", "many", "other")

# Plural categories required per language (base code).
# Languages not listed default to ("one", "other") which matches most languages.
_CATEGORIES: dict[str, tuple[str, ...]] = {
    # Single category — no grammatical plural distinction.
    "ja": ("other",),
    "zh": ("other",),
    "ko": ("other",),
    "vi": ("other",),
    "th": ("other",),
    "id": ("other",),
    "ms": ("other",),
    "my": ("other",),
    "lo": ("other",),
    "km": ("other",),
    # Two categories — one / other.
    "en": ("one", "other"),
    "de": ("one", "other"),
    "es": ("one", "other"),
    "it": ("one", "other"),
    "pt": ("one", "other"),
    "nl": ("one", "other"),
    "sv": ("one", "other"),
    "da": ("one", "other"),
    "no": ("one", "other"),
    "nb": ("one", "other"),
    "nn": ("one", "other"),
    "fi": ("one", "other"),
    "hu": ("one", "other"),
    "tr": ("one", "other"),
    "el": ("one", "other"),
    "bg": ("one", "other"),
    "et": ("one", "other"),
    "ca": ("one", "other"),
    "fa": ("one", "other"),
    "hi": ("one", "other"),
    "bn": ("one", "other"),
    "gu": ("one", "other"),
    "kn": ("one", "other"),
    "ml": ("one", "other"),
    "mr": ("one", "other"),
    "ta": ("one", "other"),
    "te": ("one", "other"),
    "sw": ("one", "other"),
    "af": ("one", "other"),
    "eu": ("one", "other"),
    "fil": ("one", "other"),
    "tl": ("one", "other"),
    # one / many / other (French, Brazilian Portuguese).
    "fr": ("one", "many", "other"),
    "pt-BR": ("one", "many", "other"),
    # one / few / other (Romanian).
    "ro": ("one", "few", "other"),
    # zero / one / other (Latvian).
    "lv": ("zero", "one", "other"),
    # one / two / few / other (Slovenian).
    "sl": ("one", "two", "few", "other"),
    # one / two / many / other (Hebrew per CLDR modern).
    "he": ("one", "two", "many", "other"),
    "iw": ("one", "two", "many", "other"),
    # one / few / many / other (Slavic and Baltic).
    "ru": ("one", "few", "many", "other"),
    "uk": ("one", "few", "many", "other"),
    "be": ("one", "few", "many", "other"),
    "sr": ("one", "few", "many", "other"),
    "hr": ("one", "few", "many", "other"),
    "bs": ("one", "few", "many", "other"),
    "pl": ("one", "few", "many", "other"),
    "cs": ("one", "few", "many", "other"),
    "sk": ("one", "few", "many", "other"),
    "lt": ("one", "few", "many", "other"),
    # All six categories — Arabic, Welsh.
    "ar": ("zero", "one", "two", "few", "many", "other"),
    "cy": ("zero", "one", "two", "few", "many", "other"),
    # Celtic — one / two / few / many / other.
    "ga": ("one", "two", "few", "many", "other"),
    "gd": ("one", "two", "few", "other"),
}

# Human-readable rules per language. Used inside LLM prompts so the model
# knows which numeric values map to each category.
_RULES_DESCRIPTION: dict[str, str] = {
    "en": (
        "- one: n = 1\n"
        "- other: all other numbers (0, 2, 3, 1.5, ...)"
    ),
    "de": (
        "- one: n = 1\n"
        "- other: all other numbers (0, 2, 3, 1.5, ...)"
    ),
    "es": (
        "- one: n = 1\n"
        "- other: all other numbers"
    ),
    "fr": (
        "- one: n = 0 or n = 1\n"
        "- many: very large numbers (1,000,000+) when used with units (de millions)\n"
        "- other: all other numbers (2, 3, 4, ...)"
    ),
    "pt-BR": (
        "- one: n = 0 or n = 1\n"
        "- many: very large numbers (1,000,000+)\n"
        "- other: all other numbers"
    ),
    "ro": (
        "- one: n = 1\n"
        "- few: n = 0 or numbers 2-19 (and 102-119, 202-219, ...)\n"
        "- other: 20+ outside the few ranges"
    ),
    "lv": (
        "- zero: n = 0 or numbers ending in 11-19 (10, 20, 30, ... 100 also map by mod-100)\n"
        "- one: numbers ending in 1, except 11 (1, 21, 31, ...)\n"
        "- other: all other numbers"
    ),
    "sl": (
        "- one: numbers ending in 01 (1, 101, 201, ...)\n"
        "- two: numbers ending in 02 (2, 102, 202, ...)\n"
        "- few: numbers ending in 03 or 04 (3, 4, 103, 104, ...)\n"
        "- other: all other numbers"
    ),
    "he": (
        "- one: n = 1\n"
        "- two: n = 2\n"
        "- many: numbers divisible by 10 (20, 30, 40, ...) excluding 10 itself in some readings\n"
        "- other: all other numbers (0, 3-9, 11-19, ...)"
    ),
    "ru": (
        "- one: numbers ending in 1, EXCEPT those ending in 11 (1, 21, 31, 41, 101, ...)\n"
        "- few: numbers ending in 2, 3, or 4, EXCEPT those ending in 12-14 (2, 3, 4, 22, 23, 24, ...)\n"
        "- many: numbers ending in 0, 5-9, OR ending in 11-14 (0, 5-20, 25-30, ...)\n"
        "- other: fractional / decimal numbers (1.5, 2.7, ...)"
    ),
    "uk": (
        "- one: numbers ending in 1, EXCEPT 11 (1, 21, 31, ...)\n"
        "- few: numbers ending in 2-4, EXCEPT 12-14 (2, 3, 4, 22-24, ...)\n"
        "- many: numbers ending in 0, 5-9, or 11-14 (0, 5-20, 25-30, ...)\n"
        "- other: fractional numbers"
    ),
    "be": (
        "- one: numbers ending in 1, EXCEPT 11\n"
        "- few: numbers ending in 2-4, EXCEPT 12-14\n"
        "- many: numbers ending in 0, 5-9, or 11-14\n"
        "- other: fractional numbers"
    ),
    "sr": (
        "- one: numbers ending in 1, EXCEPT 11 (1, 21, 31, ...)\n"
        "- few: numbers ending in 2-4, EXCEPT 12-14 (2, 3, 4, 22-24, ...)\n"
        "- many: numbers ending in 0, 5-9, or 11-14\n"
        "- other: fractional numbers"
    ),
    "hr": (
        "- one: numbers ending in 1, EXCEPT 11 (1, 21, 31, ...)\n"
        "- few: numbers ending in 2-4, EXCEPT 12-14 (2, 3, 4, 22-24, ...)\n"
        "- many: numbers ending in 0, 5-9, or 11-14\n"
        "- other: fractional numbers"
    ),
    "bs": (
        "- one: numbers ending in 1, EXCEPT 11\n"
        "- few: numbers ending in 2-4, EXCEPT 12-14\n"
        "- many: numbers ending in 0, 5-9, or 11-14\n"
        "- other: fractional numbers"
    ),
    "pl": (
        "- one: n = 1\n"
        "- few: numbers ending in 2-4, EXCEPT 12-14 (2, 3, 4, 22-24, 32-34, ...)\n"
        "- many: 0, numbers ending in 0, 1, 5-9, or 11-14 (excluding the 'one' case)\n"
        "- other: fractional numbers (1.5, 2.7, ...)"
    ),
    "cs": (
        "- one: n = 1\n"
        "- few: 2, 3, 4 (only)\n"
        "- many: fractional numbers (1.5, 2.7, ...)\n"
        "- other: 0, 5+, 11-19, 100, ... (integer numbers outside few)"
    ),
    "sk": (
        "- one: n = 1\n"
        "- few: 2, 3, 4 (only)\n"
        "- many: fractional numbers\n"
        "- other: 0, 5+, ..."
    ),
    "lt": (
        "- one: numbers ending in 1, EXCEPT 11 (1, 21, 31, ...)\n"
        "- few: numbers ending in 2-9, EXCEPT 12-19 (2-9, 22-29, ...)\n"
        "- many: fractional numbers\n"
        "- other: 0, 10-20, 30, 40, ... (numbers ending in 0 or 11-19)"
    ),
    "ar": (
        "- zero: n = 0\n"
        "- one: n = 1\n"
        "- two: n = 2\n"
        "- few: 3-10 (and 103-110, 203-210, ...)\n"
        "- many: 11-99 (and 111-199, 211-299, ...)\n"
        "- other: 100, 101, 102 (and 200, 201, 202, ...) — multiples of 100"
    ),
    "cy": (
        "- zero: n = 0\n"
        "- one: n = 1\n"
        "- two: n = 2\n"
        "- few: n = 3\n"
        "- many: n = 6\n"
        "- other: all other numbers (4, 5, 7+, fractions)"
    ),
    "ga": (
        "- one: n = 1\n"
        "- two: n = 2\n"
        "- few: 3-6\n"
        "- many: 7-10\n"
        "- other: 0, 11+, fractions"
    ),
    "ja": "- other: all numbers (Japanese has no grammatical plural)",
    "zh": "- other: all numbers (Chinese has no grammatical plural)",
    "ko": "- other: all numbers (Korean has no grammatical plural)",
    "vi": "- other: all numbers (Vietnamese has no grammatical plural)",
    "th": "- other: all numbers (Thai has no grammatical plural)",
    "id": "- other: all numbers (Indonesian has no grammatical plural)",
    "ms": "- other: all numbers (Malay has no grammatical plural)",
}


def _normalize_lang(code: str) -> str:
    """Normalize a locale code to look up plural rules.

    Tries the full code first (e.g., ``pt-BR``), then falls back to the base
    language (``pt``).
    """
    if code in _CATEGORIES or code in _RULES_DESCRIPTION:
        return code
    base = code.split("-")[0].lower()
    return base


def get_plural_categories(lang: str) -> list[str]:
    """Return the list of CLDR plural categories used by the given language.

    Falls back to ``("one", "other")`` for unknown languages, which matches
    the most common pattern.
    """
    key = _normalize_lang(lang)
    if key in _CATEGORIES:
        return list(_CATEGORIES[key])
    return ["one", "other"]


def get_plural_rules_text(lang: str) -> str:
    """Return a human-readable description of plural rules for prompts."""
    key = _normalize_lang(lang)
    if key in _RULES_DESCRIPTION:
        return _RULES_DESCRIPTION[key]
    # Generic fallback for unknown languages with one/other.
    cats = get_plural_categories(lang)
    if cats == ["other"]:
        return "- other: all numbers (no grammatical plural distinction)"
    return "- one: n = 1\n- other: all other numbers"


def expand_source_forms(source_forms: dict[str, str]) -> dict[str, str]:
    """Ensure source forms contain at least 'one' and 'other' for prompting.

    If the source only provides one form (e.g., languages with no plural like
    Japanese), duplicate it under both keys so the prompt has examples.
    """
    if not source_forms:
        return source_forms
    if "other" not in source_forms:
        # Pick the most plural-like form as 'other' fallback.
        for fallback in ("many", "few", "two", "one", "zero"):
            if fallback in source_forms:
                source_forms = {**source_forms, "other": source_forms[fallback]}
                break
    return source_forms
