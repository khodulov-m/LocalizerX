"""Character limit validation utilities for App Store and Chrome Web Store metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from localizerx.parser.extension_model import EXTENSION_FIELD_LIMITS, ExtensionFieldType
from localizerx.parser.metadata_model import FIELD_LIMITS, MetadataFieldType

# Union type for all field types with limits
FieldType = Union[MetadataFieldType, ExtensionFieldType]


class LimitAction(str, Enum):
    """Action to take when a field exceeds its character limit."""

    WARN = "warn"  # Show warning but continue
    TRUNCATE = "truncate"  # Auto-truncate to fit limit
    ERROR = "error"  # Stop on limit exceeded


def _get_limit(field_type: FieldType) -> int:
    """Get the character limit for a field type."""
    if isinstance(field_type, MetadataFieldType):
        return FIELD_LIMITS[field_type]
    return EXTENSION_FIELD_LIMITS[field_type]


@dataclass
class LimitValidationResult:
    """Result of validating a field against its character limit."""

    field_type: FieldType
    content: str
    char_count: int
    limit: int
    is_valid: bool
    chars_over: int

    @property
    def message(self) -> str:
        """Get a human-readable validation message."""
        if self.is_valid:
            return f"{self.field_type.value}: OK ({self.char_count}/{self.limit})"
        return (
            f"{self.field_type.value}: OVER LIMIT by {self.chars_over} chars "
            f"({self.char_count}/{self.limit})"
        )


def validate_limit(content: str, field_type: FieldType) -> LimitValidationResult:
    """
    Validate content against the character limit for a field type.

    Args:
        content: The text content to validate
        field_type: The metadata or extension field type

    Returns:
        LimitValidationResult with validation details
    """
    limit = _get_limit(field_type)
    char_count = len(content)
    chars_over = max(0, char_count - limit)
    is_valid = char_count <= limit

    return LimitValidationResult(
        field_type=field_type,
        content=content,
        char_count=char_count,
        limit=limit,
        is_valid=is_valid,
        chars_over=chars_over,
    )


def truncate_to_limit(content: str, field_type: FieldType) -> str:
    """
    Truncate content to fit within the character limit for a field type.

    For keywords, truncates at comma boundaries to preserve whole keywords.
    For other fields, simply truncates at the limit.

    Args:
        content: The text content to truncate
        field_type: The metadata or extension field type

    Returns:
        Truncated content that fits within the limit
    """
    limit = _get_limit(field_type)

    if len(content) <= limit:
        return content

    if isinstance(field_type, MetadataFieldType) and field_type == MetadataFieldType.KEYWORDS:
        return _truncate_keywords(content, limit)

    return content[:limit]


def _truncate_keywords(content: str, limit: int) -> str:
    """
    Truncate keywords at comma boundary to preserve whole keywords.

    Args:
        content: Comma-separated keywords string
        limit: Character limit

    Returns:
        Truncated keywords string
    """
    if len(content) <= limit:
        return content

    # Find the last comma before the limit
    truncated = content[:limit]
    last_comma = truncated.rfind(",")

    if last_comma > 0:
        return truncated[:last_comma].strip()

    # No comma found, just truncate
    return truncated.strip()


def get_limit_for_field(field_type: FieldType) -> int:
    """
    Get the character limit for a field type.

    Args:
        field_type: The metadata or extension field type

    Returns:
        Character limit
    """
    return _get_limit(field_type)


def format_limit_warning(result: LimitValidationResult, locale: str) -> str:
    """
    Format a warning message for a field that exceeds its limit.

    Args:
        result: The validation result
        locale: The locale code

    Returns:
        Formatted warning message
    """
    return (
        f"[{locale}] {result.field_type.value}: "
        f"{result.char_count} chars (limit: {result.limit}, over by {result.chars_over})"
    )
