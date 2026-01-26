"""Gemini API adapter for translation."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx

from localizerx.config import DEFAULT_MODEL
from localizerx.utils.locale import get_language_name
from localizerx.utils.placeholders import mask_placeholders, unmask_placeholders

from .base import TranslationRequest, TranslationResult, Translator

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _preserve_whitespace(original: str, translated: str) -> str:
    """Preserve leading/trailing whitespace from original in translated text."""
    # Get leading whitespace from original
    leading = len(original) - len(original.lstrip())
    leading_ws = original[:leading] if leading else ""

    # Get trailing whitespace from original
    trailing = len(original) - len(original.rstrip())
    trailing_ws = original[-trailing:] if trailing else ""

    # Apply to translated text (strip it first to ensure clean result)
    return leading_ws + translated.strip() + trailing_ws


class GeminiTranslator(Translator):
    """Translation adapter using Google's Gemini API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        batch_size: int = 20,
        max_retries: int = 3,
        cache_dir: Path | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=60.0)

        # Setup cache
        self._cache_conn: sqlite3.Connection | None = None
        if cache_dir:
            self._init_cache(cache_dir)

    def _init_cache(self, cache_dir: Path) -> None:
        """Initialize SQLite cache."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "translations.db"
        self._cache_conn = sqlite3.connect(str(cache_path))
        self._cache_conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                hash TEXT PRIMARY KEY,
                src_lang TEXT,
                tgt_lang TEXT,
                original TEXT,
                translated TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._cache_conn.commit()

    def _cache_key(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Generate cache key for a translation."""
        content = f"{src_lang}:{tgt_lang}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cached(self, text: str, src_lang: str, tgt_lang: str) -> str | None:
        """Get cached translation if available."""
        if not self._cache_conn:
            return None
        key = self._cache_key(text, src_lang, tgt_lang)
        cursor = self._cache_conn.execute(
            "SELECT translated FROM translations WHERE hash = ?", (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _set_cached(
        self, text: str, translated: str, src_lang: str, tgt_lang: str
    ) -> None:
        """Cache a translation."""
        if not self._cache_conn:
            return
        key = self._cache_key(text, src_lang, tgt_lang)
        self._cache_conn.execute(
            """INSERT OR REPLACE INTO translations (hash, src_lang, tgt_lang, original, translated)
               VALUES (?, ?, ?, ?, ?)""",
            (key, src_lang, tgt_lang, text, translated),
        )
        self._cache_conn.commit()

    async def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: str | None = None,
    ) -> str:
        """Translate a single piece of text."""
        # Check cache
        cached = self._get_cached(text, source_lang, target_lang)
        if cached:
            return cached

        # Mask placeholders
        masked = mask_placeholders(text)

        # Build prompt
        src_name = get_language_name(source_lang)
        tgt_name = get_language_name(target_lang)

        prompt = self._build_prompt(masked.masked, src_name, tgt_name, context)

        # Call API with retries
        translated_masked = await self._call_api(prompt)

        # Unmask placeholders
        translated = unmask_placeholders(translated_masked, masked.placeholders)

        # Preserve original whitespace
        translated = _preserve_whitespace(text, translated)

        # Cache result
        self._set_cached(text, translated, source_lang, target_lang)

        return translated

    async def translate_batch(
        self,
        requests: list[TranslationRequest],
        source_lang: str,
        target_lang: str,
    ) -> list[TranslationResult]:
        """Translate a batch of texts efficiently."""
        results: list[TranslationResult] = []
        to_translate: list[tuple[int, TranslationRequest, str, dict[str, str]]] = []

        # Check cache and prepare masked texts
        for i, req in enumerate(requests):
            cached = self._get_cached(req.text, source_lang, target_lang)
            if cached:
                results.append(
                    TranslationResult(
                        key=req.key,
                        original=req.text,
                        translated=cached,
                    )
                )
            else:
                masked = mask_placeholders(req.text)
                to_translate.append((i, req, masked.masked, masked.placeholders))
                results.append(TranslationResult(key=req.key, original=req.text, translated=""))

        if not to_translate:
            return results

        # Batch translate
        src_name = get_language_name(source_lang)
        tgt_name = get_language_name(target_lang)

        # Process in batches
        for batch_start in range(0, len(to_translate), self.batch_size):
            batch = to_translate[batch_start : batch_start + self.batch_size]
            batch_results = await self._translate_batch_items(batch, src_name, tgt_name)

            for (idx, req, _, placeholders), translated_masked in zip(
                batch, batch_results
            ):
                translated = unmask_placeholders(translated_masked, placeholders)
                # Preserve original whitespace
                translated = _preserve_whitespace(req.text, translated)
                results[idx] = TranslationResult(
                    key=req.key,
                    original=req.text,
                    translated=translated,
                )
                self._set_cached(req.text, translated, source_lang, target_lang)

        return results

    async def _translate_batch_items(
        self,
        items: list[tuple[int, TranslationRequest, str, dict[str, str]]],
        src_name: str,
        tgt_name: str,
    ) -> list[str]:
        """Translate a batch of items using a single API call."""
        if len(items) == 1:
            _, req, masked_text, _ = items[0]
            prompt = self._build_prompt(masked_text, src_name, tgt_name, req.comment)
            result = await self._call_api(prompt)
            return [result]

        # Build batch prompt
        texts = []
        for i, (_, req, masked_text, _) in enumerate(items):
            entry = f"{i + 1}. {masked_text}"
            if req.comment:
                entry += f" [Context: {req.comment}]"
            texts.append(entry)

        batch_text = "\n".join(texts)
        prompt = self._build_batch_prompt(batch_text, len(items), src_name, tgt_name)

        response = await self._call_api(prompt)
        return self._parse_batch_response(response, len(items))

    def _build_prompt(
        self, text: str, src_name: str, tgt_name: str, context: str | None
    ) -> str:
        """Build translation prompt for single text."""
        prompt = f"""Translate the following text from {src_name} to {tgt_name}.

IMPORTANT RULES:
1. Keep all placeholders exactly as they are (like __PH_1__, __PH_2__, etc.)
2. Preserve any formatting, line breaks, and punctuation style
3. Translate naturally, not word-for-word
4. This is for an iOS/macOS app interface

Text to translate:
{text}"""

        if context:
            prompt += f"\n\nContext/Note: {context}"

        prompt += "\n\nTranslation (only provide the translated text, nothing else):"
        return prompt

    def _build_batch_prompt(
        self, batch_text: str, count: int, src_name: str, tgt_name: str
    ) -> str:
        """Build translation prompt for batch."""
        return f"""Translate the following {count} texts from {src_name} to {tgt_name}.

IMPORTANT RULES:
1. Keep all placeholders exactly as they are (like __PH_1__, __PH_2__, etc.)
2. Preserve any formatting and punctuation style
3. Translate naturally, not word-for-word
4. This is for an iOS/macOS app interface
5. Return ONLY the translations, numbered to match the input

Texts to translate:
{batch_text}

Translations (numbered to match, one per line):"""

    def _parse_batch_response(self, response: str, expected_count: int) -> list[str]:
        """Parse batch translation response."""
        lines = response.strip().split("\n")
        results = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove numbering patterns like "1.", "1)", "1:"
            import re

            cleaned = re.sub(r"^\d+[\.\)\:]\s*", "", line)
            if cleaned:
                results.append(cleaned)

        # Pad with empty strings if we got fewer results
        while len(results) < expected_count:
            results.append("")

        return results[:expected_count]

    async def _call_api(self, prompt: str) -> str:
        """Call Gemini API with retry logic."""
        url = f"{GEMINI_API_URL}/{self.model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.8,
                "maxOutputTokens": 2048,
            },
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    url,
                    params={"key": self.api_key},
                    json=payload,
                )

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** (attempt + 1)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()
                return self._extract_text(data)

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Server error - retry
                    await asyncio.sleep(2**attempt)
                    continue
                raise

            except httpx.RequestError as e:
                last_error = e
                await asyncio.sleep(2**attempt)
                continue

        raise RuntimeError(f"API call failed after {self.max_retries} retries: {last_error}")

    def _extract_text(self, response: dict[str, Any]) -> str:
        """Extract text from Gemini API response."""
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in response")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise ValueError("No parts in response")

            return parts[0].get("text", "").strip()
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected response format: {e}")

    async def close(self) -> None:
        """Clean up resources."""
        await self.client.aclose()
        if self._cache_conn:
            self._cache_conn.close()
