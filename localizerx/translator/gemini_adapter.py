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
        batch_size: int = 100,
        max_retries: int = 3,
        cache_dir: Path | None = None,
        temperature: float = 0.3,
        thinking_config: dict[str, str] | None = None,
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
        self.temperature = temperature
        self.thinking_config = thinking_config
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

        # Build batch prompt with unique markers to avoid confusion with numbered lists in content
        texts = []
        contexts = []
        for i, (_, req, masked_text, _) in enumerate(items):
            # Use unique markers that won't appear in normal content
            entry = f"<<ITEM_{i + 1}>>\n{masked_text}\n<</ITEM_{i + 1}>>"
            texts.append(entry)
            if req.comment:
                contexts.append(f"Item {i + 1}: {req.comment}")

        batch_text = "\n\n".join(texts)
        prompt = self._build_batch_prompt(batch_text, len(items), src_name, tgt_name, contexts)

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
        self, batch_text: str, count: int, src_name: str, tgt_name: str,
        contexts: list[str] | None = None
    ) -> str:
        """Build translation prompt for batch."""
        prompt = f"""Translate the following {count} texts from {src_name} to {tgt_name}.

CRITICAL RULES:
1. Keep all placeholders exactly as they are (like __PH_1__, __PH_2__, etc.)
2. Preserve any formatting, line breaks, and punctuation style
3. Translate naturally, not word-for-word
4. This is for an iOS/macOS app interface
5. Return ONLY the translations using the EXACT SAME <<ITEM_N>> markers
6. Do NOT include any context notes, explanations, or metadata in the translations
7. IMPORTANT: Each <<ITEM_N>> block is ONE translation unit. If the source has multiple paragraphs or blank lines, the translation MUST also have multiple paragraphs within the SAME <<ITEM_N>> block. NEVER split multi-paragraph content across different ITEM markers.

Texts to translate:
{batch_text}"""

        if contexts:
            prompt += "\n\nContext notes (for your reference only, do NOT include in translations):\n"
            prompt += "\n".join(contexts)

        prompt += f"\n\nTranslations (output exactly {count} items using <<ITEM_1>> through <<ITEM_{count}>> markers, one translation per marker, preserving all paragraphs within each item):"
        return prompt

    def _parse_batch_response(self, response: str, expected_count: int) -> list[str]:
        """Parse batch translation response.

        Extracts translations from <<ITEM_N>>...<</ITEM_N>> markers.
        Falls back to numbered list parsing if markers are not found.
        """
        import re

        # First, try to parse using our unique markers
        results: list[str] = []
        for i in range(1, expected_count + 1):
            # Match content between <<ITEM_N>> and <</ITEM_N>>
            pattern = rf"<<ITEM_{i}>>\s*(.*?)\s*<</ITEM_{i}>>"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                text = match.group(1).strip()
                # Clean up any context metadata that might have leaked through
                text = self._strip_context_metadata(text)
                results.append(text)
            else:
                results.append("")

        # If we got results with markers, return them
        if any(results):
            return results

        # Fallback: parse old-style numbered responses (for backwards compatibility)
        return self._parse_numbered_response(response, expected_count)

    def _strip_context_metadata(self, text: str) -> str:
        """Remove any context metadata that leaked into the translation."""
        import re
        # Remove [Context: ...], [Контекст: ...], [Contexto: ...], etc.
        # This handles various language variants of "Context"
        patterns = [
            r"\s*\[Context:.*?\]",
            r"\s*\[Контекст:.*?\]",
            r"\s*\[Contexto:.*?\]",
            r"\s*\[Contexte:.*?\]",
            r"\s*\[Contesto:.*?\]",
            r"\s*\[Kontext:.*?\]",
            r"\s*\[컨텍스트:.*?\]",
            r"\s*\[コンテキスト:.*?\]",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
        return text.strip()

    def _parse_numbered_response(self, response: str, expected_count: int) -> list[str]:
        """Parse old-style numbered batch response (fallback).

        Handles multi-line translations by grouping lines between numbered items.
        E.g. "1. first line\\nsecond line\\n2. another" -> ["first line\\nsecond line", "another"]
        """
        import re

        lines = response.strip().split("\n")
        results: list[list[str]] = []
        current_lines: list[str] = []
        current_item_num: int | None = None  # Track which item we're currently building

        for line in lines:
            # Check if this line starts a new numbered item
            match = re.match(r"^(\d+)[\.\)\:]\s*(.*)", line)
            if match:
                num = int(match.group(1))
                # Calculate expected next number
                # If we're building an item (current_item_num is set), next should be current + 1
                # Otherwise, next should be 1
                expected_next = (current_item_num + 1) if current_item_num is not None else 1

                # Treat as a new item marker if the number is sequential
                # This prevents inner numbered lists (like "1. Step one" inside content)
                # from being treated as item boundaries
                if num == expected_next:
                    # Save previous item if any
                    if current_lines:
                        results.append(current_lines)
                    current_lines = [match.group(2)] if match.group(2) else []
                    current_item_num = num
                else:
                    # This numbered line is content, not a marker (non-sequential number)
                    if results or current_lines:
                        current_lines.append(line)
            else:
                # Continuation of current item (or leading text before first number)
                if results or current_lines:
                    current_lines.append(line)
                elif line.strip():
                    # Text before any numbering — treat as first item
                    current_lines.append(line)

        # Don't forget the last item
        if current_lines:
            results.append(current_lines)

        # Join multi-line items back together
        joined = ["\n".join(lines_group) for lines_group in results]

        # Strip context metadata from each result
        joined = [self._strip_context_metadata(text) for text in joined]

        # Pad with empty strings if we got fewer results
        while len(joined) < expected_count:
            joined.append("")

        return joined[:expected_count]

    async def _call_api(self, prompt: str) -> str:
        """Call Gemini API with retry logic."""
        url = f"{GEMINI_API_URL}/{self.model}:generateContent"

        generation_config: dict[str, Any] = {
            "temperature": self.temperature,
            "topP": 0.8,
            "maxOutputTokens": 8192,
        }
        if self.thinking_config:
            generation_config["thinkingConfig"] = self.thinking_config

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
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
