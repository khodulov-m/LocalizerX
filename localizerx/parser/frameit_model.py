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

    def get_strings_needing_translation(
        self,
        target_locale: str,
        overwrite: bool = False,
    ) -> tuple[list[FrameitString], list[FrameitString]]:
        """
        Get source strings that need translation for a target locale.
        Returns (titles, keywords) tuple.
        """
        source = self.get_source_metadata()
        if not source:
            return [], []

        target = self.get_locale(target_locale)
        
        needs_titles = []
        for key, src_str in source.title_strings.items():
            if not src_str.value.strip():
                continue
            if overwrite:
                needs_titles.append(src_str)
                continue
            if target is None or key not in target.title_strings:
                needs_titles.append(src_str)
            elif not target.title_strings[key].value.strip():
                needs_titles.append(src_str)

        needs_keywords = []
        for key, src_str in source.keyword_strings.items():
            if not src_str.value.strip():
                continue
            if overwrite:
                needs_keywords.append(src_str)
                continue
            if target is None or key not in target.keyword_strings:
                needs_keywords.append(src_str)
            elif not target.keyword_strings[key].value.strip():
                needs_keywords.append(src_str)

        return needs_titles, needs_keywords
