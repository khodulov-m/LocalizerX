"""Data models for frontend i18n JSON localization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class I18nMessage(BaseModel):
    """A single i18n key-value entry with dotted key path."""

    key: str  # Dotted path, e.g. "common.hello"
    value: str

    @property
    def needs_translation(self) -> bool:
        """Check if this message has translatable content."""
        return bool(self.value.strip())


class I18nLocale(BaseModel):
    """All messages for one locale."""

    locale: str
    messages: dict[str, I18nMessage] = Field(default_factory=dict)

    # Preserve original JSON structure for lossless round-trip
    _raw_data: dict[str, Any] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_raw_data(self, data: dict[str, Any]) -> None:
        """Store original JSON data for lossless writes."""
        object.__setattr__(self, "_raw_data", data)

    def get_raw_data(self) -> dict[str, Any] | None:
        """Get original JSON data."""
        return getattr(self, "_raw_data", None)

    @property
    def message_count(self) -> int:
        """Get the number of messages."""
        return len(self.messages)

    def get_message(self, key: str) -> I18nMessage | None:
        """Get a specific message by dotted key."""
        return self.messages.get(key)

    def set_message(self, key: str, value: str) -> None:
        """Set a message's content."""
        self.messages[key] = I18nMessage(key=key, value=value)


class I18nCatalog(BaseModel):
    """Collection of i18n locales."""

    source_locale: str
    locales: dict[str, I18nLocale] = Field(default_factory=dict)

    def get_locale(self, locale: str) -> I18nLocale | None:
        """Get data for a specific locale."""
        return self.locales.get(locale)

    def get_or_create_locale(self, locale: str) -> I18nLocale:
        """Get or create data for a locale."""
        if locale not in self.locales:
            self.locales[locale] = I18nLocale(locale=locale)
        return self.locales[locale]

    def get_source_locale(self) -> I18nLocale | None:
        """Get the source locale data."""
        return self.locales.get(self.source_locale)

    @property
    def locale_count(self) -> int:
        """Get the number of locales."""
        return len(self.locales)

    def get_messages_needing_translation(
        self,
        target_locale: str,
    ) -> list[I18nMessage]:
        """Get source messages that need translation for a target locale.

        Returns source I18nMessage objects for keys that are missing
        or empty in the target locale.
        """
        source = self.get_source_locale()
        if not source:
            return []

        target = self.get_locale(target_locale)

        needs_translation = []
        for key, src_msg in source.messages.items():
            if not src_msg.needs_translation:
                continue
            if target is None or target.get_message(key) is None:
                needs_translation.append(src_msg)
            elif target.get_message(key).value.strip() == "":
                needs_translation.append(src_msg)

        return needs_translation
