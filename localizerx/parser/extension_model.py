"""Data models for Chrome Extension localization."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExtensionFieldType(str, Enum):
    """Types of Chrome Web Store metadata fields."""

    APP_NAME = "appName"
    SHORT_NAME = "shortName"
    DESCRIPTION = "appDesc"
    SHORT_DESC = "shortDesc"
    STORE_DESC = "storeDesc"


# Chrome Web Store character limits
EXTENSION_FIELD_LIMITS: dict[ExtensionFieldType, int] = {
    ExtensionFieldType.APP_NAME: 75,
    ExtensionFieldType.SHORT_NAME: 12,
    ExtensionFieldType.DESCRIPTION: 132,
    ExtensionFieldType.SHORT_DESC: 132,
    ExtensionFieldType.STORE_DESC: 16383,
}

# Known CWS message keys for special handling
KNOWN_CWS_KEYS: set[str] = {ft.value for ft in ExtensionFieldType}


class ExtensionMessage(BaseModel):
    """A single message in a Chrome Extension locale file."""

    key: str
    message: str
    description: str | None = None
    placeholders: dict[str, Any] | None = None

    @property
    def field_type(self) -> ExtensionFieldType | None:
        """Get the CWS field type if this is a known CWS key."""
        if self.key in KNOWN_CWS_KEYS:
            return ExtensionFieldType(self.key)
        return None

    @property
    def has_limit(self) -> bool:
        """Check if this message has a character limit."""
        return self.field_type is not None

    @property
    def limit(self) -> int | None:
        """Get the character limit for this message, if any."""
        ft = self.field_type
        if ft is not None:
            return EXTENSION_FIELD_LIMITS[ft]
        return None

    @property
    def char_count(self) -> int:
        """Get the character count of the message."""
        return len(self.message)

    @property
    def is_over_limit(self) -> bool:
        """Check if message exceeds its character limit."""
        lim = self.limit
        if lim is None:
            return False
        return self.char_count > lim


class ExtensionLocale(BaseModel):
    """All messages for a single Chrome Extension locale."""

    locale: str
    messages: dict[str, ExtensionMessage] = Field(default_factory=dict)

    def get_message(self, key: str) -> ExtensionMessage | None:
        """Get a specific message by key."""
        return self.messages.get(key)

    def set_message(
        self,
        key: str,
        message: str,
        description: str | None = None,
        placeholders: dict[str, Any] | None = None,
    ) -> None:
        """Set a message's content."""
        self.messages[key] = ExtensionMessage(
            key=key,
            message=message,
            description=description,
            placeholders=placeholders,
        )

    @property
    def field_count(self) -> int:
        """Get the number of messages."""
        return len(self.messages)

    def get_over_limit_fields(self) -> list[ExtensionMessage]:
        """Get all CWS messages that exceed their character limits."""
        return [m for m in self.messages.values() if m.is_over_limit]


class ExtensionCatalog(BaseModel):
    """Collection of Chrome Extension locale data."""

    source_locale: str
    locales: dict[str, ExtensionLocale] = Field(default_factory=dict)

    def get_locale(self, locale: str) -> ExtensionLocale | None:
        """Get data for a specific locale."""
        return self.locales.get(locale)

    def get_or_create_locale(self, locale: str) -> ExtensionLocale:
        """Get or create data for a locale."""
        if locale not in self.locales:
            self.locales[locale] = ExtensionLocale(locale=locale)
        return self.locales[locale]

    def get_source_locale(self) -> ExtensionLocale | None:
        """Get the source locale data."""
        return self.locales.get(self.source_locale)

    @property
    def locale_count(self) -> int:
        """Get the number of locales."""
        return len(self.locales)

    def get_messages_needing_translation(
        self,
        target_locale: str,
        keys_filter: list[str] | None = None,
    ) -> list[ExtensionMessage]:
        """Get source messages that need translation for a target locale.

        Returns source ExtensionMessage objects for keys that are missing
        or empty in the target locale.
        """
        source = self.get_source_locale()
        if not source:
            return []

        target = self.get_locale(target_locale)
        keys_to_check = keys_filter or list(source.messages.keys())

        needs_translation = []
        for key in keys_to_check:
            src_msg = source.get_message(key)
            if not src_msg or not src_msg.message.strip():
                continue
            if target is None or target.get_message(key) is None:
                needs_translation.append(src_msg)
            elif target.get_message(key).message.strip() == "":
                needs_translation.append(src_msg)

        return needs_translation
