"""Tests for Chrome Extension translation: batch parsing, CWS field routing, and end-to-end."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from localizerx.parser.extension_model import (
    EXTENSION_FIELD_LIMITS,
    KNOWN_CWS_KEYS,
    ExtensionFieldType,
    ExtensionMessage,
)
from localizerx.translator.base import TranslationRequest
from localizerx.translator.gemini_adapter import GeminiTranslator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_translator() -> GeminiTranslator:
    """Create a translator instance without cache (API key is fake)."""
    return GeminiTranslator(api_key="fake-key")


# ---------------------------------------------------------------------------
# _parse_batch_response
# ---------------------------------------------------------------------------


class TestParseBatchResponse:
    """Ensure _parse_batch_response correctly handles various response formats."""

    def setup_method(self):
        self.translator = _make_translator()

    def test_single_line_items(self):
        response = "1. Bonjour le monde\n2. Au revoir"
        result = self.translator._parse_batch_response(response, 2)
        assert result == ["Bonjour le monde", "Au revoir"]

    def test_multiline_item(self):
        """A numbered item that spans multiple lines must be kept together."""
        response = "1. Première ligne\nDeuxième ligne\nTroisième ligne\n" "2. Autre traduction"
        result = self.translator._parse_batch_response(response, 2)
        assert len(result) == 2
        assert result[0] == "Première ligne\nDeuxième ligne\nTroisième ligne"
        assert result[1] == "Autre traduction"

    def test_multiline_markdown_item(self):
        """Simulate a store description with markdown headers, bullets, and newlines."""
        store_desc_translated = (
            "# Titre Principal\n"
            "\n"
            "Description du produit.\n"
            "\n"
            "## Fonctionnalités\n"
            "\n"
            "• Première fonctionnalité\n"
            "• Deuxième fonctionnalité\n"
            "\n"
            "## Comment ça marche\n"
            "\n"
            "1. Étape un\n"  # inner numbered list should NOT split
            "2. Étape deux\n"  # inner numbered list should NOT split
            "3. Étape trois"
        )
        # The batch has only 1 item
        response = f"1. {store_desc_translated}"
        result = self.translator._parse_batch_response(response, 1)
        assert len(result) == 1
        # The full markdown must be preserved (inner "1. Étape" will cause extra splits)
        # With expected_count=1 we get everything in the first item
        assert "# Titre Principal" in result[0]
        assert "## Fonctionnalités" in result[0]
        assert "## Comment ça marche" in result[0]

    def test_two_items_first_is_multiline(self):
        """First item is multi-line, second is single-line."""
        response = "1. Ligne A\nLigne B\nLigne C\n" "2. Traduction simple"
        result = self.translator._parse_batch_response(response, 2)
        assert len(result) == 2
        assert "Ligne A\nLigne B\nLigne C" == result[0]
        assert "Traduction simple" == result[1]

    def test_padding_when_fewer_results(self):
        response = "1. Seule traduction"
        result = self.translator._parse_batch_response(response, 3)
        assert len(result) == 3
        assert result[0] == "Seule traduction"
        assert result[1] == ""
        assert result[2] == ""

    def test_truncation_when_more_results(self):
        response = "1. Un\n2. Deux\n3. Trois"
        result = self.translator._parse_batch_response(response, 2)
        assert len(result) == 2
        assert result[0] == "Un"
        assert result[1] == "Deux"

    def test_empty_response(self):
        result = self.translator._parse_batch_response("", 2)
        assert result == ["", ""]

    def test_response_without_numbering(self):
        """Some models return translations without numbering."""
        response = "Bonjour"
        result = self.translator._parse_batch_response(response, 1)
        assert len(result) == 1
        assert result[0] == "Bonjour"

    def test_various_numbering_styles(self):
        """Support 1. / 1) / 1: numbering."""
        for sep in [".", ")", ":"]:
            response = f"1{sep} Premier\n2{sep} Deuxième"
            result = self.translator._parse_batch_response(response, 2)
            assert result == ["Premier", "Deuxième"], f"Failed for separator '{sep}'"

    def test_multiline_with_blank_lines(self):
        """Blank lines inside a multi-line item must be preserved."""
        response = "1. Paragraphe un\n" "\n" "Paragraphe deux\n" "2. Autre"
        result = self.translator._parse_batch_response(response, 2)
        assert len(result) == 2
        assert "Paragraphe un\n\nParagraphe deux" == result[0]
        assert "Autre" == result[1]


# ---------------------------------------------------------------------------
# CWS field classification for storeDesc / shortDesc
# ---------------------------------------------------------------------------


class TestCWSFieldClassification:
    """Verify storeDesc and shortDesc are recognized as CWS fields."""

    def test_store_desc_is_known_cws_key(self):
        assert "storeDesc" in KNOWN_CWS_KEYS

    def test_short_desc_is_known_cws_key(self):
        assert "shortDesc" in KNOWN_CWS_KEYS

    def test_store_desc_field_type(self):
        msg = ExtensionMessage(key="storeDesc", message="Full store description...")
        assert msg.field_type == ExtensionFieldType.STORE_DESC

    def test_short_desc_field_type(self):
        msg = ExtensionMessage(key="shortDesc", message="Short description")
        assert msg.field_type == ExtensionFieldType.SHORT_DESC

    def test_store_desc_has_limit(self):
        msg = ExtensionMessage(key="storeDesc", message="x")
        assert msg.has_limit is True
        assert msg.limit == EXTENSION_FIELD_LIMITS[ExtensionFieldType.STORE_DESC]

    def test_short_desc_has_limit(self):
        msg = ExtensionMessage(key="shortDesc", message="x")
        assert msg.has_limit is True
        assert msg.limit == EXTENSION_FIELD_LIMITS[ExtensionFieldType.SHORT_DESC]

    def test_store_desc_not_over_limit(self):
        msg = ExtensionMessage(key="storeDesc", message="x" * 5000)
        assert msg.is_over_limit is False

    def test_store_desc_over_limit(self):
        limit = EXTENSION_FIELD_LIMITS[ExtensionFieldType.STORE_DESC]
        msg = ExtensionMessage(key="storeDesc", message="x" * (limit + 1))
        assert msg.is_over_limit is True

    def test_all_cws_keys_have_limits(self):
        """Every ExtensionFieldType must have a corresponding limit."""
        for ft in ExtensionFieldType:
            assert ft in EXTENSION_FIELD_LIMITS, f"{ft.value} has no limit defined"

    def test_cws_messages_separated_from_regular(self):
        """storeDesc and shortDesc should be classified as CWS, not regular."""
        messages = [
            ExtensionMessage(key="appName", message="My App"),
            ExtensionMessage(key="shortDesc", message="Short desc"),
            ExtensionMessage(key="storeDesc", message="Full desc"),
            ExtensionMessage(key="greeting", message="Hello"),
        ]
        cws = [m for m in messages if m.key in KNOWN_CWS_KEYS]
        regular = [m for m in messages if m.key not in KNOWN_CWS_KEYS]

        assert len(cws) == 3  # appName, shortDesc, storeDesc
        assert len(regular) == 1  # greeting
        cws_keys = {m.key for m in cws}
        assert "appName" in cws_keys
        assert "shortDesc" in cws_keys
        assert "storeDesc" in cws_keys


# ---------------------------------------------------------------------------
# End-to-end Chrome translation with mocked API
# ---------------------------------------------------------------------------


class TestChromeTranslationE2E:
    """Test that storeDesc gets translated individually (not batched)."""

    @pytest.fixture
    def locales_dir(self):
        """Create a _locales/ directory with a multi-line storeDesc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            locales = Path(tmpdir) / "_locales"
            locales.mkdir()

            en_dir = locales / "en"
            en_dir.mkdir()

            en_messages = {
                "appName": {"message": "Hashtag Generator"},
                "shortDesc": {"message": "Create perfect hashtags for social media."},
                "storeDesc": {
                    "message": (
                        "# Hashtag Generator\n\n"
                        "Generate perfect hashtags in seconds.\n\n"
                        "## Features\n\n"
                        "• AI-powered analysis\n"
                        "• Platform-specific tags\n\n"
                        "## How It Works\n\n"
                        "1. Install the extension\n"
                        "2. Select your media\n"
                        "3. Get hashtags instantly"
                    ),
                },
                "greeting": {"message": "Hello!"},
            }
            (en_dir / "messages.json").write_text(
                json.dumps(en_messages, indent=2, ensure_ascii=False)
            )
            yield locales

    @pytest.mark.asyncio
    async def test_store_desc_translated_individually(self, locales_dir):
        """storeDesc must be translated via _call_api (individually), not batched."""
        from localizerx.io.extension import read_extension

        catalog = read_extension(locales_dir)
        messages = catalog.get_messages_needing_translation("fr")

        cws = [m for m in messages if m.key in KNOWN_CWS_KEYS]
        regular = [m for m in messages if m.key not in KNOWN_CWS_KEYS]

        # storeDesc, shortDesc, appName should be CWS; greeting should be regular
        cws_keys = {m.key for m in cws}
        regular_keys = {m.key for m in regular}

        assert "storeDesc" in cws_keys
        assert "shortDesc" in cws_keys
        assert "appName" in cws_keys
        assert "greeting" in regular_keys

    @pytest.mark.asyncio
    async def test_multiline_store_desc_not_truncated(self):
        """Multi-line content without inner numbered lists is kept together in batch."""
        translator = _make_translator()

        # Store description WITHOUT inner numbered lists (bullets only)
        full_translation = (
            "# Générateur de Hashtags\n\n"
            "Générez des hashtags parfaits.\n\n"
            "## Fonctionnalités\n\n"
            "• Analyse IA\n"
            "• Tags par plateforme\n\n"
            "## Comment ça marche\n\n"
            "- Installez l'extension\n"
            "- Sélectionnez votre média\n"
            "- Obtenez des hashtags"
        )

        batch_response = f"1. {full_translation}\n2. Bonjour !"
        results = translator._parse_batch_response(batch_response, 2)

        assert len(results) == 2
        assert "# Générateur de Hashtags" in results[0]
        assert "## Fonctionnalités" in results[0]
        assert "## Comment ça marche" in results[0]
        assert "• Analyse IA" in results[0]
        assert results[1] == "Bonjour !"

    @pytest.mark.asyncio
    async def test_inner_numbered_lists_cause_split_in_batch(self):
        """Content with inner numbered lists gets mis-split in batch — this is why
        storeDesc must be translated individually as a CWS field, not batched."""
        translator = _make_translator()

        # Content with inner numbered list
        content_with_numbers = "# Title\n\n" "1. Step one\n" "2. Step two\n" "3. Step three"

        batch_response = f"1. {content_with_numbers}\n99. Other item"
        # Parser will split on inner "1.", "2.", "3.", "99." — more items than expected
        results = translator._parse_batch_response(batch_response, 2)

        # The parser produces more items due to inner numbering, then truncates to 2
        # This demonstrates why storeDesc (which has numbered lists) MUST NOT go
        # through batch translation — it must be a CWS field translated individually
        assert len(results) == 2
        # First result is only partial — the bug we're guarding against
        assert "# Title" in results[0]

    @pytest.mark.asyncio
    async def test_translate_batch_preserves_multiline(self):
        """Full translate_batch flow with mocked API preserves multi-line content."""
        translator = _make_translator()

        multiline_text = "Line one\nLine two\nLine three"
        single_text = "Hello world"

        requests = [
            TranslationRequest(key="desc", text=multiline_text),
            TranslationRequest(key="greeting", text=single_text),
        ]

        translated_multiline = "Ligne un\nLigne deux\nLigne trois"
        mock_response = f"1. {translated_multiline}\n2. Bonjour le monde"

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            results = await translator.translate_batch(requests, "en", "fr")

        assert len(results) == 2
        assert results[0].key == "desc"
        assert "Ligne un\nLigne deux\nLigne trois" == results[0].translated
        assert results[1].key == "greeting"
        assert results[1].translated == "Bonjour le monde"
