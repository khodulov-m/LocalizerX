"""Data models for fastlane metadata representation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MetadataFieldType(str, Enum):
    """Types of App Store metadata fields."""

    NAME = "name"
    SUBTITLE = "subtitle"
    KEYWORDS = "keywords"
    DESCRIPTION = "description"
    PROMOTIONAL_TEXT = "promotional_text"
    RELEASE_NOTES = "release_notes"


# App Store Connect character limits
FIELD_LIMITS: dict[MetadataFieldType, int] = {
    MetadataFieldType.NAME: 30,
    MetadataFieldType.SUBTITLE: 30,
    MetadataFieldType.KEYWORDS: 100,
    MetadataFieldType.DESCRIPTION: 4000,
    MetadataFieldType.PROMOTIONAL_TEXT: 170,
    MetadataFieldType.RELEASE_NOTES: 4000,
}

# Mapping from filename to field type
FILENAME_TO_FIELD: dict[str, MetadataFieldType] = {
    "name.txt": MetadataFieldType.NAME,
    "subtitle.txt": MetadataFieldType.SUBTITLE,
    "keywords.txt": MetadataFieldType.KEYWORDS,
    "description.txt": MetadataFieldType.DESCRIPTION,
    "promotional_text.txt": MetadataFieldType.PROMOTIONAL_TEXT,
    "release_notes.txt": MetadataFieldType.RELEASE_NOTES,
}

# Reverse mapping
FIELD_TO_FILENAME: dict[MetadataFieldType, str] = {v: k for k, v in FILENAME_TO_FIELD.items()}


class MetadataField(BaseModel):
    """A single metadata field with content and limit tracking."""

    field_type: MetadataFieldType
    content: str

    @property
    def char_count(self) -> int:
        """Get the character count of the content."""
        return len(self.content)

    @property
    def limit(self) -> int:
        """Get the character limit for this field type."""
        return FIELD_LIMITS[self.field_type]

    @property
    def is_over_limit(self) -> bool:
        """Check if content exceeds the character limit."""
        return self.char_count > self.limit

    @property
    def chars_over(self) -> int:
        """Get how many characters over the limit."""
        return max(0, self.char_count - self.limit)

    def truncate(self) -> MetadataField:
        """Return a new field with content truncated to the limit."""
        if not self.is_over_limit:
            return self

        # For keywords, try to truncate at a comma boundary
        if self.field_type == MetadataFieldType.KEYWORDS:
            truncated = self._truncate_keywords()
        else:
            truncated = self.content[: self.limit]

        return MetadataField(field_type=self.field_type, content=truncated)

    def _truncate_keywords(self) -> str:
        """Truncate keywords at comma boundary to preserve whole keywords."""
        limit = self.limit
        if len(self.content) <= limit:
            return self.content

        # Find the last comma before the limit
        truncated = self.content[:limit]
        last_comma = truncated.rfind(",")

        if last_comma > 0:
            return truncated[:last_comma].strip()
        return truncated.strip()


class LocaleMetadata(BaseModel):
    """Metadata for a single locale."""

    locale: str
    fields: dict[MetadataFieldType, MetadataField] = Field(default_factory=dict)

    def get_field(self, field_type: MetadataFieldType) -> MetadataField | None:
        """Get a specific field."""
        return self.fields.get(field_type)

    def set_field(self, field_type: MetadataFieldType, content: str) -> None:
        """Set a field's content."""
        self.fields[field_type] = MetadataField(field_type=field_type, content=content)

    def has_field(self, field_type: MetadataFieldType) -> bool:
        """Check if a field exists."""
        return field_type in self.fields

    @property
    def field_count(self) -> int:
        """Get the number of fields."""
        return len(self.fields)

    def get_over_limit_fields(self) -> list[MetadataField]:
        """Get all fields that exceed their character limits."""
        return [f for f in self.fields.values() if f.is_over_limit]


class MetadataCatalog(BaseModel):
    """Collection of metadata for all locales."""

    source_locale: str
    locales: dict[str, LocaleMetadata] = Field(default_factory=dict)

    def get_locale(self, locale: str) -> LocaleMetadata | None:
        """Get metadata for a specific locale."""
        return self.locales.get(locale)

    def get_or_create_locale(self, locale: str) -> LocaleMetadata:
        """Get or create metadata for a locale."""
        if locale not in self.locales:
            self.locales[locale] = LocaleMetadata(locale=locale)
        return self.locales[locale]

    def get_source_metadata(self) -> LocaleMetadata | None:
        """Get the source locale metadata."""
        return self.locales.get(self.source_locale)

    @property
    def locale_count(self) -> int:
        """Get the number of locales."""
        return len(self.locales)

    def get_target_locales(self) -> list[str]:
        """Get all locales except the source."""
        return [loc for loc in self.locales if loc != self.source_locale]

    def get_fields_needing_translation(
        self,
        target_locale: str,
        field_types: list[MetadataFieldType] | None = None,
        overwrite: bool = False,
    ) -> list[MetadataFieldType]:
        """Get field types that need translation for a target locale."""
        source = self.get_source_metadata()
        if not source:
            return []

        target = self.get_locale(target_locale)
        fields_to_check = field_types or list(MetadataFieldType)

        needs_translation = []
        for field_type in fields_to_check:
            # Source must have the field
            if not source.has_field(field_type):
                continue
            
            if overwrite:
                needs_translation.append(field_type)
                continue
                
            # Target must not have the field or be empty
            if target is None or not target.has_field(field_type):
                needs_translation.append(field_type)
            elif target.get_field(field_type).content.strip() == "":
                needs_translation.append(field_type)

        return needs_translation

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary representation."""
        return {
            "source_locale": self.source_locale,
            "locales": {
                locale: {
                    field_type.value: field.content for field_type, field in meta.fields.items()
                }
                for locale, meta in self.locales.items()
            },
        }
