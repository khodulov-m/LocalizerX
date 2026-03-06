"""Data models for xcstrings representation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Translation(BaseModel):
    """A single translation with optional plural/gender variations."""

    value: str
    state: str = "translated"
    variations: dict[str, Any] | None = None

    def to_xcstrings_dict(self) -> dict[str, Any]:
        """Convert to xcstrings format."""
        result: dict[str, Any] = {"stringUnit": {"state": self.state, "value": self.value}}
        if self.variations:
            result["variations"] = self.variations
        return result


class PluralVariation(BaseModel):
    """Plural variations for a translation."""

    zero: str | None = None
    one: str | None = None
    two: str | None = None
    few: str | None = None
    many: str | None = None
    other: str

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Convert to xcstrings plural format."""
        result: dict[str, dict[str, Any]] = {}
        for key in ["zero", "one", "two", "few", "many", "other"]:
            value = getattr(self, key)
            if value is not None:
                result[key] = {"stringUnit": {"state": "translated", "value": value}}
        return result


class Entry(BaseModel):
    """A localization entry with source text and translations."""

    key: str
    source_text: str
    comment: str | None = None
    translations: dict[str, Translation] = Field(default_factory=dict)
    extraction_state: str | None = None
    should_translate: bool = True
    source_variations: dict[str, Any] | None = None  # For plural/gender forms in source language

    @property
    def needs_translation(self) -> bool:
        """Check if this entry should be translated."""
        return self.should_translate and (
            bool(self.source_text.strip()) or self.source_variations is not None
        )

    @property
    def has_plurals(self) -> bool:
        """Check if this entry has plural variations."""
        return self.source_variations is not None and "plural" in self.source_variations


class StringCatalog(BaseModel):
    """Representation of a .xcstrings file."""

    source_language: str
    strings: dict[str, Entry] = Field(default_factory=dict)
    version: str = "1.0"

    # Preserve original JSON structure for lossless round-trip
    _raw_data: dict[str, Any] | None = None
    _indent: int | str = 2
    _separators: tuple[str, str] = (",", ": ")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_raw_data(self, data: dict[str, Any]) -> None:
        """Store original JSON data for lossless writes."""
        object.__setattr__(self, "_raw_data", data)

    def get_raw_data(self) -> dict[str, Any] | None:
        """Get original JSON data."""
        return getattr(self, "_raw_data", None)

    def set_formatting(self, indent: int | str, separators: tuple[str, str]) -> None:
        """Set the formatting to use when writing back."""
        object.__setattr__(self, "_indent", indent)
        object.__setattr__(self, "_separators", separators)

    def get_formatting(self) -> tuple[int | str, tuple[str, str]]:
        """Get the formatting to use when writing back."""
        return getattr(self, "_indent", 2), getattr(self, "_separators", (",", ": "))

    def get_entries_needing_translation(self, target_lang: str) -> list[Entry]:
        """Get entries that need translation for a target language."""
        entries = []
        for entry in self.strings.values():
            if not entry.needs_translation:
                continue
            if target_lang not in entry.translations:
                entries.append(entry)
        return entries

    def get_all_translatable_entries(self) -> list[Entry]:
        """Get all entries that can be translated."""
        return [e for e in self.strings.values() if e.needs_translation]
