"""Data models for fastlane frameit representation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FrameitString(BaseModel):
    """A single string from a .strings file."""

    key: str
    value: str


class FrameitLocale(BaseModel):
    """Collection of strings for a locale (title and keyword)."""

    locale: str
    title_strings: dict[str, FrameitString] = Field(default_factory=dict)
    keyword_strings: dict[str, FrameitString] = Field(default_factory=dict)

    def set_title(self, key: str, value: str) -> None:
        """Set a title string."""
        self.title_strings[key] = FrameitString(key=key, value=value)

    def set_keyword(self, key: str, value: str) -> None:
        """Set a keyword string."""
        self.keyword_strings[key] = FrameitString(key=key, value=value)


class FrameitCatalog(BaseModel):
    """Collection of frameit metadata for all locales."""

    source_locale: str
    locales: dict[str, FrameitLocale] = Field(default_factory=dict)

    def get_locale(self, locale: str) -> FrameitLocale | None:
        """Get frameit metadata for a locale."""
        return self.locales.get(locale)

    def get_or_create_locale(self, locale: str) -> FrameitLocale:
        """Get or create frameit metadata for a locale."""
        if locale not in self.locales:
            self.locales[locale] = FrameitLocale(locale=locale)
        return self.locales[locale]

    def get_source_metadata(self) -> FrameitLocale | None:
        """Get the source locale metadata."""
        return self.locales.get(self.source_locale)
