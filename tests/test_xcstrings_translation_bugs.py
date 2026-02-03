"""Tests for xcstrings translation bugs: context leaking, multiline shifting.

These tests reproduce the actual bugs found in examples/Localizable.xcstrings:
1. Context metadata like "[Контекст: ...]" appearing in translations
2. Multiline strings with \\n\\n causing translations to "shift" between keys
3. Batch translation mixing up items when content has internal numbered lists
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from localizerx.translator.base import TranslationRequest
from localizerx.translator.gemini_adapter import GeminiTranslator


def _make_translator() -> GeminiTranslator:
    """Create a translator instance without cache (API key is fake)."""
    return GeminiTranslator(api_key="fake-key")


# ---------------------------------------------------------------------------
# Bug #1: Context metadata leaking into translations
# ---------------------------------------------------------------------------

class TestContextMetadataStripping:
    """Verify that context metadata is stripped from translations."""

    def setup_method(self):
        self.translator = _make_translator()

    def test_strip_english_context(self):
        """Remove [Context: ...] from translation."""
        text = "Settings [Context: The title of the settings screen.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Settings"

    def test_strip_russian_context(self):
        """Remove [Контекст: ...] from Russian translation."""
        text = "Настройки [Контекст: Заголовок экрана настроек.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Настройки"

    def test_strip_spanish_context(self):
        """Remove [Contexto: ...] from Spanish translation."""
        text = "Guardar [Contexto: La etiqueta de un botón que guarda los cambios.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Guardar"

    def test_strip_french_context(self):
        """Remove [Contexte: ...] from French translation."""
        text = "Enregistrer [Contexte: L'étiquette d'un bouton qui enregistre les modifications.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Enregistrer"

    def test_strip_german_context(self):
        """Remove [Kontext: ...] from German translation."""
        text = "Speichern [Kontext: Eine Schaltflächenbeschriftung, die Änderungen speichert.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Speichern"

    def test_strip_italian_context(self):
        """Remove [Contesto: ...] from Italian translation."""
        text = "Salva [Contesto: L'etichetta di un pulsante che salva le modifiche.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Salva"

    def test_strip_korean_context(self):
        """Remove [컨텍스트: ...] from Korean translation."""
        text = "저장 [컨텍스트: 변경 사항을 저장하는 버튼 레이블입니다.]"
        result = self.translator._strip_context_metadata(text)
        assert result == "저장"

    def test_strip_japanese_context(self):
        """Remove [コンテキスト: ...] from Japanese translation."""
        text = "保存 [コンテキスト: 変更を保存するボタンのラベル。]"
        result = self.translator._strip_context_metadata(text)
        assert result == "保存"

    def test_no_context_unchanged(self):
        """Text without context metadata should be unchanged."""
        text = "Welcome to the app!"
        result = self.translator._strip_context_metadata(text)
        assert result == "Welcome to the app!"

    def test_context_case_insensitive(self):
        """Context matching should be case-insensitive."""
        text = "Settings [CONTEXT: Some info]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Settings"

    def test_multiline_with_context(self):
        """Context at end of multiline string."""
        text = "Line one\nLine two [Context: Developer note]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Line one\nLine two"


# ---------------------------------------------------------------------------
# Bug #2: Multiline strings with \n\n causing shift
# ---------------------------------------------------------------------------

class TestMultilineStringParsing:
    """Test parsing of responses with multiline content containing \\n\\n."""

    def setup_method(self):
        self.translator = _make_translator()

    def test_double_newline_preserved(self):
        """Strings with \\n\\n (like 'This action...\\n\\nType DELETE') stay together."""
        # Simulates the "This action cannot be undone..." string
        translated = (
            "Esta acción no se puede deshacer. Todos tus datos se eliminarán permanentemente.\n\n"
            "Escribe ELIMINAR para confirmar."
        )
        response = f"1. {translated}\n2. Nivel"
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        assert "\n\n" in result[0], "Double newline must be preserved"
        assert "Escribe ELIMINAR" in result[0], "Second part must stay with first"
        assert result[1] == "Nivel"

    def test_three_items_with_multiline_first(self):
        """First item has \\n\\n, second and third are simple."""
        multiline = "Line A\n\nLine B"
        response = f"1. {multiline}\n2. Second\n3. Third"
        result = self.translator._parse_batch_response(response, 3)

        assert len(result) == 3
        assert result[0] == "Line A\n\nLine B"
        assert result[1] == "Second"
        assert result[2] == "Third"

    def test_multiple_multiline_items(self):
        """Multiple items all have \\n\\n."""
        item1 = "First part\n\nSecond part"
        item2 = "Another\n\nMultiline"
        response = f"1. {item1}\n2. {item2}"
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        assert result[0] == "First part\n\nSecond part"
        assert result[1] == "Another\n\nMultiline"


# ---------------------------------------------------------------------------
# Bug reproduction: xcstrings example scenarios
# ---------------------------------------------------------------------------

class TestXcstringsExampleBugs:
    """Reproduce the exact bugs from examples/Localizable.xcstrings."""

    def setup_method(self):
        self.translator = _make_translator()

    def test_tier_not_delete_confirmation(self):
        """'Tier' translation should NOT contain 'DELETE' confirmation text.

        Bug: 'Tier' was incorrectly showing 'Type DELETE to confirm' translations
        because the multiline 'This action...' string caused a shift.
        """
        # Correct batch response where each item is correctly numbered
        response = (
            "1. Nivel\n"  # Tier
            "2. Esta acción no se puede deshacer.\n\nEscribe ELIMINAR.\n"  # Delete confirmation
            "3. Alterna la visibilidad de la contraseña"  # Toggles password
        )
        result = self.translator._parse_batch_response(response, 3)

        assert len(result) == 3
        assert result[0] == "Nivel"
        assert "DELETE" not in result[0].upper() or "ELIMINAR" not in result[0]
        assert "Esta acción" in result[1]
        assert "Alterna" in result[2]

    def test_settings_no_context_in_value(self):
        """'settings_title' translation should NOT contain [Context: ...].

        Bug: Translations like 'Configurações [Contexto: O título...]' had
        context metadata embedded in the value.
        """
        # Simulated batch response where Gemini incorrectly includes context
        response = "1. Configurações [Contexto: O título da tela de configurações.]\n2. Salvar"
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        # Context should be stripped
        assert result[0] == "Configurações"
        assert "[Contexto:" not in result[0]
        assert result[1] == "Salvar"

    def test_save_button_clean_translation(self):
        """'save_button' should be clean without context pollution."""
        response = "1. Speichern [Kontext: Eine Schaltflächenbeschriftung.]"
        result = self.translator._parse_batch_response(response, 1)

        assert len(result) == 1
        assert result[0] == "Speichern"
        assert "[Kontext:" not in result[0]

    def test_delete_confirmation_complete(self):
        """The 'This action cannot be undone...' string should have BOTH parts.

        Bug: Many translations were missing 'Type DELETE to confirm' part.
        """
        # Complete translation with both paragraphs
        full_translation = (
            "Diese Aktion kann nicht rückgängig gemacht werden. "
            "Alle Ihre Daten werden dauerhaft gelöscht.\n\n"
            "Geben Sie DELETE ein, um zu bestätigen."
        )
        response = f"1. {full_translation}"
        result = self.translator._parse_batch_response(response, 1)

        assert len(result) == 1
        assert "DELETE" in result[0]
        assert "\n\n" in result[0]

    def test_toggles_password_not_tier(self):
        """'Toggles password visibility' should NOT contain 'Tier' translations.

        Bug: This key was showing 'Niveau', 'Stufe', etc. (Tier translations)
        instead of password visibility hints.
        """
        response = (
            "1. Nivel\n"  # Tier
            "2. Alterna la visibilidad de la contraseña"  # Toggles password
        )
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        assert result[0] == "Nivel"
        assert result[1] == "Alterna la visibilidad de la contraseña"
        # Tier should NOT appear in password toggle
        assert "Nivel" not in result[1]


# ---------------------------------------------------------------------------
# New marker format: <<ITEM_N>>
# ---------------------------------------------------------------------------

class TestNewMarkerFormat:
    """Test parsing of new <<ITEM_N>> marker format."""

    def setup_method(self):
        self.translator = _make_translator()

    def test_parse_new_markers(self):
        """Parse response using <<ITEM_N>> format."""
        response = (
            "<<ITEM_1>>\nBonjour le monde\n<</ITEM_1>>\n\n"
            "<<ITEM_2>>\nAu revoir\n<</ITEM_2>>"
        )
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        assert result[0] == "Bonjour le monde"
        assert result[1] == "Au revoir"

    def test_parse_multiline_with_markers(self):
        """Multiline content preserved with new markers."""
        multiline_content = "Line 1\n\nLine 2\n\n1. Step one\n2. Step two"
        response = f"<<ITEM_1>>\n{multiline_content}\n<</ITEM_1>>"
        result = self.translator._parse_batch_response(response, 1)

        assert len(result) == 1
        assert result[0] == multiline_content

    def test_parse_markers_with_context_stripped(self):
        """Context metadata is stripped even with new marker format."""
        response = (
            "<<ITEM_1>>\n"
            "Настройки [Контекст: Заголовок экрана настроек.]\n"
            "<</ITEM_1>>"
        )
        result = self.translator._parse_batch_response(response, 1)

        assert len(result) == 1
        assert result[0] == "Настройки"
        assert "[Контекст:" not in result[0]

    def test_fallback_to_numbered_when_no_markers(self):
        """Fall back to numbered parsing if markers not found."""
        response = "1. First item\n2. Second item"
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        assert result[0] == "First item"
        assert result[1] == "Second item"


# ---------------------------------------------------------------------------
# Full translate_batch flow
# ---------------------------------------------------------------------------

class TestTranslateBatchWithContext:
    """Test translate_batch correctly handles context without pollution."""

    @pytest.mark.asyncio
    async def test_batch_with_comments_no_leakage(self):
        """Comments/context should NOT appear in translated text."""
        translator = _make_translator()

        requests = [
            TranslationRequest(
                key="settings_title",
                text="Settings",
                comment="The title of the settings screen."
            ),
            TranslationRequest(
                key="save_button",
                text="Save",
                comment="A button label that saves changes."
            ),
        ]

        # Mock response with new marker format (clean, no context)
        mock_response = (
            "<<ITEM_1>>\nEinstellungen\n<</ITEM_1>>\n\n"
            "<<ITEM_2>>\nSpeichern\n<</ITEM_2>>"
        )

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            results = await translator.translate_batch(requests, "en", "de")

        assert len(results) == 2
        assert results[0].translated == "Einstellungen"
        assert "[" not in results[0].translated
        assert results[1].translated == "Speichern"
        assert "[" not in results[1].translated

    @pytest.mark.asyncio
    async def test_batch_multiline_delete_confirmation(self):
        """Multiline 'delete confirmation' string translated correctly."""
        translator = _make_translator()

        original = (
            "This action cannot be undone. All your data will be permanently deleted.\n\n"
            "Type DELETE to confirm."
        )
        requests = [
            TranslationRequest(
                key="delete_warning",
                text=original,
                comment="An alert message for account deletion."
            ),
        ]

        translated = (
            "Diese Aktion kann nicht rückgängig gemacht werden. "
            "Alle Ihre Daten werden dauerhaft gelöscht.\n\n"
            "Geben Sie DELETE ein, um zu bestätigen."
        )
        mock_response = f"<<ITEM_1>>\n{translated}\n<</ITEM_1>>"

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            results = await translator.translate_batch(requests, "en", "de")

        assert len(results) == 1
        assert "\n\n" in results[0].translated
        assert "DELETE" in results[0].translated
        assert "Alle Ihre Daten" in results[0].translated

    @pytest.mark.asyncio
    async def test_batch_three_items_correct_order(self):
        """Three items in batch maintain correct order."""
        translator = _make_translator()

        requests = [
            TranslationRequest(key="tier", text="Tier", comment="Subscription tier label."),
            TranslationRequest(
                key="delete_msg",
                text="This action cannot be undone.\n\nType DELETE to confirm.",
                comment="Delete confirmation."
            ),
            TranslationRequest(
                key="password_toggle",
                text="Toggles password visibility",
                comment="Accessibility hint."
            ),
        ]

        mock_response = (
            "<<ITEM_1>>\nNivel\n<</ITEM_1>>\n\n"
            "<<ITEM_2>>\n"
            "Esta acción no se puede deshacer.\n\n"
            "Escribe ELIMINAR para confirmar.\n"
            "<</ITEM_2>>\n\n"
            "<<ITEM_3>>\nAlterna la visibilidad de la contraseña\n<</ITEM_3>>"
        )

        with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_response
            results = await translator.translate_batch(requests, "en", "es")

        assert len(results) == 3

        # Tier should be simple
        assert results[0].key == "tier"
        assert results[0].translated == "Nivel"

        # Delete message should have both parts
        assert results[1].key == "delete_msg"
        assert "\n\n" in results[1].translated
        assert "ELIMINAR" in results[1].translated

        # Password toggle should be about password, not tier
        assert results[2].key == "password_toggle"
        assert "contraseña" in results[2].translated.lower()
        assert "Nivel" not in results[2].translated


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and corner scenarios."""

    def setup_method(self):
        self.translator = _make_translator()

    def test_empty_context_bracket(self):
        """Handle malformed context brackets."""
        text = "Hello [Context: ]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Hello"

    def test_nested_brackets(self):
        """Text with nested brackets (not context)."""
        text = "Array[0] and List[String]"
        result = self.translator._strip_context_metadata(text)
        # Should not be stripped (not context metadata)
        assert result == "Array[0] and List[String]"

    def test_context_at_start(self):
        """Context at the beginning of text."""
        text = "[Context: Note] Settings"
        result = self.translator._strip_context_metadata(text)
        assert result == "Settings"

    def test_multiple_contexts(self):
        """Multiple context markers (shouldn't happen, but handle it)."""
        text = "Save [Context: Button] [Контекст: Кнопка]"
        result = self.translator._strip_context_metadata(text)
        assert result == "Save"

    def test_inner_numbered_list_with_new_markers(self):
        """Content with inner numbered list stays together with <<ITEM_N>> markers.

        The fallback numbered parser cannot distinguish inner numbered lists that
        coincide with expected batch numbers. Use <<ITEM_N>> markers for reliable
        parsing of content with inner numbered lists.
        """
        content = "How to use:\n1. First step\n2. Second step\n3. Third step"
        # With new markers, inner numbered lists are preserved
        response = f"<<ITEM_1>>\n{content}\n<</ITEM_1>>\n\n<<ITEM_2>>\nAnother item\n<</ITEM_2>>"
        result = self.translator._parse_batch_response(response, 2)

        assert len(result) == 2
        assert "1. First step" in result[0]
        assert "2. Second step" in result[0]
        assert "3. Third step" in result[0]
        assert result[1] == "Another item"

    def test_inner_numbered_list_fallback_limitation(self):
        """Document known limitation: fallback parser splits on sequential inner numbers.

        When inner numbered list starts with a number that matches the expected
        next batch item number, the fallback parser incorrectly splits.
        This is why <<ITEM_N>> markers were introduced.
        """
        content = "How to use:\n1. First step\n2. Second step\n3. Third step"
        response = f"1. {content}\n2. Another item"
        result = self.translator._parse_batch_response(response, 2)

        # Known limitation: "2. Second step" matches expected next number (2),
        # so fallback parser splits there
        assert len(result) == 2
        # First item is truncated at "2. Second step"
        assert "How to use:" in result[0]
        assert "1. First step" in result[0]
        # The rest is incorrectly in second item
        # This documents why CWS fields with numbered lists need individual translation
