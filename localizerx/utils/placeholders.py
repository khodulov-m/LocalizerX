"""Placeholder masking and unmasking for safe translation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MaskedText:
    """Text with placeholders masked for translation."""

    masked: str
    placeholders: dict[str, str] = field(default_factory=dict)


# Format specifier patterns (order matters - more specific patterns first)
PRINTF_PATTERNS = [
    # Positional specifiers: %1$@, %2$d, etc.
    r"%\d+\$[@dDuUxXoOfeEgGcCsSpaAn]",
    r"%\d+\$[\.\d]*[dDuUxXoOfeEgGcCsSpaAn]",
    # Long specifiers: %ld, %lld, %lu, etc.
    r"%l{1,2}[dDuUxXoOi]",
    # Float specifiers: %.2f, %5.2f, etc.
    r"%[\d]*\.[\d]+[feEgG]",
    r"%[\d]+[feEgG]",
    # Basic specifiers: %@, %d, %s, etc.
    r"%[@dDuUxXoOfeEgGcCsSpaAni%]",
]

# Named placeholder patterns: {name}, {count}, etc.
NAMED_PLACEHOLDER_PATTERN = r"\{[a-zA-Z_][a-zA-Z0-9_]*\}"

# Chrome Extension placeholder patterns
# $PLACEHOLDER_NAME$ syntax (e.g., $APP_NAME$, $userName$)
CHROME_NAMED_PLACEHOLDER_PATTERN = r"\$[a-zA-Z_][a-zA-Z0-9_]*\$"
# $1-style positional placeholders (e.g., $1, $2)
CHROME_POSITIONAL_PLACEHOLDER_PATTERN = r"\$\d+"

# Combine all patterns
ALL_PATTERNS = PRINTF_PATTERNS + [
    NAMED_PLACEHOLDER_PATTERN,
    CHROME_NAMED_PLACEHOLDER_PATTERN,
    CHROME_POSITIONAL_PLACEHOLDER_PATTERN,
]
COMBINED_PATTERN = re.compile("|".join(f"({p})" for p in ALL_PATTERNS))


def mask_placeholders(text: str) -> MaskedText:
    """
    Mask all placeholders in text to protect them during translation.

    Replaces placeholders with tokens like __PH_1__, __PH_2__, etc.
    Returns the masked text and a mapping to restore original placeholders.

    Examples:
        >>> result = mask_placeholders("Hello %@, you have %d messages")
        >>> result.masked
        'Hello __PH_1__, you have __PH_2__ messages'
        >>> result.placeholders
        {'__PH_1__': '%@', '__PH_2__': '%d'}
    """
    placeholders: dict[str, str] = {}
    counter = [0]  # Use list to allow mutation in closure

    def replacer(match: re.Match[str]) -> str:
        counter[0] += 1
        token = f"__PH_{counter[0]}__"
        placeholders[token] = match.group(0)
        return token

    masked = COMBINED_PATTERN.sub(replacer, text)
    return MaskedText(masked=masked, placeholders=placeholders)


def unmask_placeholders(masked_text: str, placeholders: dict[str, str]) -> str:
    """
    Restore original placeholders in translated text.

    Examples:
        >>> unmask_placeholders("Hola __PH_1__, tienes __PH_2__ mensajes",
        ...                     {'__PH_1__': '%@', '__PH_2__': '%d'})
        'Hola %@, tienes %d mensajes'
    """
    result = masked_text
    for token, original in placeholders.items():
        result = result.replace(token, original)
    return result


def count_placeholders(text: str) -> int:
    """Count the number of placeholders in text."""
    return len(COMBINED_PATTERN.findall(text))


def validate_placeholders(original: str, translated: str) -> bool:
    """
    Check if translated text has the same placeholders as original.

    Returns True if all placeholders are preserved correctly.
    """
    original_matches = set(COMBINED_PATTERN.findall(original))
    translated_matches = set(COMBINED_PATTERN.findall(translated))

    # Flatten tuples from capturing groups
    original_phs = {m for group in original_matches for m in group if m}
    translated_phs = {m for group in translated_matches for m in group if m}

    return original_phs == translated_phs


def extract_placeholders(text: str) -> list[str]:
    """Extract all placeholders from text in order of appearance."""
    matches = COMBINED_PATTERN.findall(text)
    # Flatten tuples and filter empty strings
    return [m for group in matches for m in group if m]
