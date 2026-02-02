"""Data models for App Store screenshot text localization."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScreenshotTextType(str, Enum):
    """Types of text elements on App Store screenshots."""

    HEADLINE = "headline"
    SUBTITLE = "subtitle"
    BUTTON = "button"
    CAPTION = "caption"
    CALLOUT = "callout"


class DeviceClass(str, Enum):
    """Device size classes for screenshot text variants."""

    SMALL = "small"  # iPhone SE, compact displays
    LARGE = "large"  # iPhone Pro Max, iPad


# Word limit for screenshot texts (ASO best practice)
SCREENSHOT_TEXT_WORD_LIMIT = 5


class ScreenshotText(BaseModel):
    """A text element with variants for different device sizes."""

    small: str | None = None
    large: str | None = None

    def get_variant(self, device_class: DeviceClass) -> str | None:
        """Get text for a specific device class."""
        if device_class == DeviceClass.SMALL:
            return self.small
        return self.large

    def set_variant(self, device_class: DeviceClass, value: str) -> None:
        """Set text for a specific device class."""
        if device_class == DeviceClass.SMALL:
            self.small = value
        else:
            self.large = value

    @property
    def has_small(self) -> bool:
        """Check if small variant exists."""
        return self.small is not None and self.small.strip() != ""

    @property
    def has_large(self) -> bool:
        """Check if large variant exists."""
        return self.large is not None and self.large.strip() != ""

    @property
    def is_empty(self) -> bool:
        """Check if both variants are empty."""
        return not self.has_small and not self.has_large

    def word_count(self, device_class: DeviceClass) -> int:
        """Get word count for a specific variant."""
        text = self.get_variant(device_class)
        if not text:
            return 0
        return len(text.split())

    def is_over_word_limit(self, device_class: DeviceClass) -> bool:
        """Check if a variant exceeds the word limit."""
        return self.word_count(device_class) > SCREENSHOT_TEXT_WORD_LIMIT

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary, excluding None values."""
        result = {}
        if self.small is not None:
            result["small"] = self.small
        if self.large is not None:
            result["large"] = self.large
        return result


class ScreenshotScreen(BaseModel):
    """All text elements for a single screenshot screen."""

    texts: dict[ScreenshotTextType, ScreenshotText] = Field(default_factory=dict)

    def get_text(self, text_type: ScreenshotTextType) -> ScreenshotText | None:
        """Get a specific text element."""
        return self.texts.get(text_type)

    def set_text(self, text_type: ScreenshotTextType, text: ScreenshotText) -> None:
        """Set a text element."""
        self.texts[text_type] = text

    def set_text_variant(
        self,
        text_type: ScreenshotTextType,
        device_class: DeviceClass,
        value: str,
    ) -> None:
        """Set a specific variant for a text element."""
        if text_type not in self.texts:
            self.texts[text_type] = ScreenshotText()
        self.texts[text_type].set_variant(device_class, value)

    @property
    def text_count(self) -> int:
        """Get number of text elements."""
        return len(self.texts)

    @property
    def is_empty(self) -> bool:
        """Check if screen has no texts."""
        return all(t.is_empty for t in self.texts.values())

    def get_over_limit_texts(self) -> list[tuple[ScreenshotTextType, DeviceClass]]:
        """Get all text/device combinations that exceed word limit."""
        over_limit = []
        for text_type, text in self.texts.items():
            for device_class in DeviceClass:
                if text.get_variant(device_class) and text.is_over_word_limit(device_class):
                    over_limit.append((text_type, device_class))
        return over_limit

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Convert to dictionary."""
        return {
            text_type.value: text.to_dict()
            for text_type, text in self.texts.items()
            if not text.is_empty
        }


class ScreenshotLocale(BaseModel):
    """All screens for a single locale."""

    locale: str
    screens: dict[str, ScreenshotScreen] = Field(default_factory=dict)

    def get_screen(self, screen_id: str) -> ScreenshotScreen | None:
        """Get a specific screen."""
        return self.screens.get(screen_id)

    def get_or_create_screen(self, screen_id: str) -> ScreenshotScreen:
        """Get or create a screen."""
        if screen_id not in self.screens:
            self.screens[screen_id] = ScreenshotScreen()
        return self.screens[screen_id]

    @property
    def screen_count(self) -> int:
        """Get number of screens."""
        return len(self.screens)

    def get_all_texts(self) -> list[tuple[str, ScreenshotTextType, ScreenshotText]]:
        """Get all texts across all screens as (screen_id, text_type, text) tuples."""
        result = []
        for screen_id, screen in self.screens.items():
            for text_type, text in screen.texts.items():
                result.append((screen_id, text_type, text))
        return result

    def to_dict(self) -> dict[str, dict[str, dict[str, str]]]:
        """Convert to dictionary."""
        return {
            screen_id: screen.to_dict()
            for screen_id, screen in self.screens.items()
            if not screen.is_empty
        }


class ScreenshotsCatalog(BaseModel):
    """Main container for screenshot texts across all locales."""

    source_language: str
    screens: dict[str, ScreenshotScreen] = Field(default_factory=dict)
    localizations: dict[str, ScreenshotLocale] = Field(default_factory=dict)
    raw_data: dict[str, Any] | None = Field(default=None, exclude=True)

    def get_source_screen(self, screen_id: str) -> ScreenshotScreen | None:
        """Get a source screen."""
        return self.screens.get(screen_id)

    def get_or_create_source_screen(self, screen_id: str) -> ScreenshotScreen:
        """Get or create a source screen."""
        if screen_id not in self.screens:
            self.screens[screen_id] = ScreenshotScreen()
        return self.screens[screen_id]

    def get_locale(self, locale: str) -> ScreenshotLocale | None:
        """Get a specific locale."""
        return self.localizations.get(locale)

    def get_or_create_locale(self, locale: str) -> ScreenshotLocale:
        """Get or create a locale."""
        if locale not in self.localizations:
            self.localizations[locale] = ScreenshotLocale(locale=locale)
        return self.localizations[locale]

    @property
    def screen_count(self) -> int:
        """Get number of source screens."""
        return len(self.screens)

    @property
    def locale_count(self) -> int:
        """Get number of localized locales (excluding source)."""
        return len(self.localizations)

    def get_all_locales(self) -> list[str]:
        """Get all locale codes including source."""
        locales = [self.source_language]
        locales.extend(sorted(self.localizations.keys()))
        return locales

    def get_target_locales(self) -> list[str]:
        """Get all locale codes except source."""
        return sorted(self.localizations.keys())

    def get_source_texts(self) -> list[tuple[str, ScreenshotTextType, ScreenshotText]]:
        """Get all source texts as (screen_id, text_type, text) tuples."""
        result = []
        for screen_id, screen in self.screens.items():
            for text_type, text in screen.texts.items():
                result.append((screen_id, text_type, text))
        return result

    def get_texts_needing_translation(
        self,
        target_locale: str,
        overwrite: bool = False,
    ) -> list[tuple[str, ScreenshotTextType, DeviceClass]]:
        """
        Get source texts that need translation for a target locale.

        Returns list of (screen_id, text_type, device_class) tuples.
        """
        target = self.get_locale(target_locale)
        needs_translation = []

        for screen_id, screen in self.screens.items():
            for text_type, source_text in screen.texts.items():
                for device_class in DeviceClass:
                    source_value = source_text.get_variant(device_class)
                    if not source_value or not source_value.strip():
                        continue

                    if overwrite:
                        needs_translation.append((screen_id, text_type, device_class))
                        continue

                    # Check if target has this text
                    if target is None:
                        needs_translation.append((screen_id, text_type, device_class))
                        continue

                    target_screen = target.get_screen(screen_id)
                    if target_screen is None:
                        needs_translation.append((screen_id, text_type, device_class))
                        continue

                    target_text = target_screen.get_text(text_type)
                    if target_text is None:
                        needs_translation.append((screen_id, text_type, device_class))
                        continue

                    target_value = target_text.get_variant(device_class)
                    if not target_value or not target_value.strip():
                        needs_translation.append((screen_id, text_type, device_class))

        return needs_translation

    def set_raw_data(self, data: dict[str, Any]) -> None:
        """Store the raw JSON data for lossless round-trip."""
        self.raw_data = data

    def get_raw_data(self) -> dict[str, Any] | None:
        """Get the stored raw JSON data."""
        return self.raw_data

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result: dict[str, Any] = {
            "sourceLanguage": self.source_language,
            "screens": {},
        }

        # Add source screens
        for screen_id, screen in self.screens.items():
            screen_dict = screen.to_dict()
            if screen_dict:
                result["screens"][screen_id] = screen_dict

        # Add localizations
        if self.localizations:
            result["localizations"] = {}
            for locale, locale_data in self.localizations.items():
                locale_dict = locale_data.to_dict()
                if locale_dict:
                    result["localizations"][locale] = locale_dict

        return result
