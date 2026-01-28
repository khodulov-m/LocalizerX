"""Data models for Android strings.xml localization."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AndroidString(BaseModel):
    """A single <string> element."""

    name: str
    value: str
    translatable: bool = True
    comment: str | None = None

    @property
    def needs_translation(self) -> bool:
        """Check if this string should be translated."""
        return self.translatable and bool(self.value.strip())


class AndroidStringArray(BaseModel):
    """A <string-array> element with list of items."""

    name: str
    items: list[str] = Field(default_factory=list)
    translatable: bool = True
    comment: str | None = None


class AndroidPlural(BaseModel):
    """A <plurals> element with quantity→value mapping."""

    name: str
    items: dict[str, str] = Field(default_factory=dict)
    translatable: bool = True
    comment: str | None = None


class AndroidLocale(BaseModel):
    """All resources for one locale."""

    locale: str
    strings: dict[str, AndroidString] = Field(default_factory=dict)
    string_arrays: dict[str, AndroidStringArray] = Field(default_factory=dict)
    plurals: dict[str, AndroidPlural] = Field(default_factory=dict)

    @property
    def string_count(self) -> int:
        return len(self.strings)

    @property
    def translatable_strings(self) -> list[AndroidString]:
        """Get all translatable strings."""
        return [s for s in self.strings.values() if s.needs_translation]


class AndroidCatalog(BaseModel):
    """Collection of Android locale data."""

    source_locale: str
    locales: dict[str, AndroidLocale] = Field(default_factory=dict)

    def get_locale(self, locale: str) -> AndroidLocale | None:
        return self.locales.get(locale)

    def get_or_create_locale(self, locale: str) -> AndroidLocale:
        if locale not in self.locales:
            self.locales[locale] = AndroidLocale(locale=locale)
        return self.locales[locale]

    def get_source_locale(self) -> AndroidLocale | None:
        return self.locales.get(self.source_locale)

    @property
    def locale_count(self) -> int:
        return len(self.locales)

    def get_strings_needing_translation(
        self,
        target_locale: str,
    ) -> list[AndroidString]:
        """Get source strings that need translation for a target locale."""
        source = self.get_source_locale()
        if not source:
            return []

        target = self.get_locale(target_locale)
        needs = []
        for name, src_str in source.strings.items():
            if not src_str.needs_translation:
                continue
            if target is None or name not in target.strings:
                needs.append(src_str)
            elif not target.strings[name].value.strip():
                needs.append(src_str)
        return needs

    def get_arrays_needing_translation(
        self,
        target_locale: str,
    ) -> list[AndroidStringArray]:
        """Get source string-arrays that need translation."""
        source = self.get_source_locale()
        if not source:
            return []

        target = self.get_locale(target_locale)
        needs = []
        for name, src_arr in source.string_arrays.items():
            if not src_arr.translatable:
                continue
            if target is None or name not in target.string_arrays:
                needs.append(src_arr)
        return needs

    def get_plurals_needing_translation(
        self,
        target_locale: str,
    ) -> list[AndroidPlural]:
        """Get source plurals that need translation."""
        source = self.get_source_locale()
        if not source:
            return []

        target = self.get_locale(target_locale)
        needs = []
        for name, src_plural in source.plurals.items():
            if not src_plural.translatable:
                continue
            if target is None or name not in target.plurals:
                needs.append(src_plural)
        return needs
