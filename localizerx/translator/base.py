"""Abstract translator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class TranslationRequest:
    """A single translation request."""

    key: str
    text: str
    comment: str | None = None
    plural_forms: dict[str, str] | None = (
        None  # For plural variations: {"one": "text", "other": "texts"}
    )


@dataclass
class TranslationResult:
    """Result of a translation."""

    key: str
    original: str
    translated: str
    success: bool = True
    error: str | None = None
    translated_plurals: dict[str, str] | None = (
        None  # For plural translations: {"one": "translation", "other": "translations"}
    )


class Translator(ABC):
    """Abstract base class for translation providers."""

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: str | None = None,
    ) -> str:
        """
        Translate a single piece of text.

        Args:
            text: The text to translate
            source_lang: Source language code
            target_lang: Target language code
            context: Optional context/comment for better translation

        Returns:
            The translated text
        """
        ...

    @abstractmethod
    async def translate_batch(
        self,
        requests: list[TranslationRequest],
        source_lang: str,
        target_lang: str,
    ) -> list[TranslationResult]:
        """
        Translate a batch of texts.

        Args:
            requests: List of translation requests
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of translation results in the same order as requests
        """
        ...

    async def translate_batch_stream(
        self,
        requests: list[TranslationRequest],
        source_lang: str,
        target_lang: str,
    ) -> AsyncIterator[TranslationResult]:
        """
        Translate a batch of texts with streaming results.

        Default implementation calls translate_batch and yields results.
        Override for true streaming behavior.
        """
        results = await self.translate_batch(requests, source_lang, target_lang)
        for result in results:
            yield result

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        ...

    async def __aenter__(self) -> "Translator":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
