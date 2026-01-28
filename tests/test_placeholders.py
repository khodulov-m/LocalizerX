"""Tests for placeholder masking/unmasking."""

from localizerx.utils.placeholders import (
    count_placeholders,
    extract_placeholders,
    mask_placeholders,
    unmask_placeholders,
    validate_placeholders,
)


class TestMaskPlaceholders:
    def test_basic_string_specifier(self):
        result = mask_placeholders("Hello %@!")
        assert result.masked == "Hello __PH_1__!"
        assert result.placeholders == {"__PH_1__": "%@"}

    def test_integer_specifier(self):
        result = mask_placeholders("You have %d items")
        assert result.masked == "You have __PH_1__ items"
        assert result.placeholders == {"__PH_1__": "%d"}

    def test_multiple_specifiers(self):
        result = mask_placeholders("Hello %@, you have %d messages")
        assert result.masked == "Hello __PH_1__, you have __PH_2__ messages"
        assert result.placeholders == {"__PH_1__": "%@", "__PH_2__": "%d"}

    def test_long_specifiers(self):
        result = mask_placeholders("Count: %ld, Total: %lld")
        assert "__PH_1__" in result.masked
        assert "__PH_2__" in result.masked
        assert "%ld" in result.placeholders.values()
        assert "%lld" in result.placeholders.values()

    def test_float_specifier(self):
        result = mask_placeholders("Progress: %.1f%%")
        assert result.masked == "Progress: __PH_1____PH_2__"
        assert "%.1f" in result.placeholders.values()

    def test_positional_specifiers(self):
        result = mask_placeholders("Created on %1$@ at %2$@")
        assert "__PH_1__" in result.masked
        assert "__PH_2__" in result.masked
        assert "%1$@" in result.placeholders.values()
        assert "%2$@" in result.placeholders.values()

    def test_named_placeholders(self):
        result = mask_placeholders("Hello {username}, your balance is {amount}")
        assert result.masked == "Hello __PH_1__, your balance is __PH_2__"
        assert result.placeholders == {"__PH_1__": "{username}", "__PH_2__": "{amount}"}

    def test_mixed_placeholders(self):
        result = mask_placeholders("Hi {name}, you have %d new messages")
        assert "__PH_1__" in result.masked
        assert "__PH_2__" in result.masked

    def test_no_placeholders(self):
        result = mask_placeholders("Hello world")
        assert result.masked == "Hello world"
        assert result.placeholders == {}


class TestUnmaskPlaceholders:
    def test_basic_unmask(self):
        masked = "Hola __PH_1__!"
        placeholders = {"__PH_1__": "%@"}
        result = unmask_placeholders(masked, placeholders)
        assert result == "Hola %@!"

    def test_multiple_unmask(self):
        masked = "Hola __PH_1__, tienes __PH_2__ mensajes"
        placeholders = {"__PH_1__": "%@", "__PH_2__": "%d"}
        result = unmask_placeholders(masked, placeholders)
        assert result == "Hola %@, tienes %d mensajes"

    def test_empty_placeholders(self):
        result = unmask_placeholders("Hello world", {})
        assert result == "Hello world"


class TestRoundTrip:
    def test_full_round_trip(self):
        original = "Hello %@, you have %d messages from {sender}"
        masked_result = mask_placeholders(original)

        # Simulate translation (just the text part changes)
        translated_masked = (
            masked_result.masked.replace("Hello", "Hola")
            .replace("you have", "tienes")
            .replace("messages from", "mensajes de")
        )

        restored = unmask_placeholders(translated_masked, masked_result.placeholders)

        # Verify placeholders are preserved
        assert "%@" in restored
        assert "%d" in restored
        assert "{sender}" in restored


class TestCountPlaceholders:
    def test_count_multiple(self):
        assert count_placeholders("Hello %@, you have %d items") == 2

    def test_count_zero(self):
        assert count_placeholders("Hello world") == 0

    def test_count_named(self):
        assert count_placeholders("{name} has {count} items") == 2


class TestValidatePlaceholders:
    def test_valid_same_placeholders(self):
        original = "Hello %@!"
        translated = "Hola %@!"
        assert validate_placeholders(original, translated) is True

    def test_invalid_missing_placeholder(self):
        original = "Hello %@!"
        translated = "Hola!"
        assert validate_placeholders(original, translated) is False

    def test_invalid_extra_placeholder(self):
        original = "Hello!"
        translated = "Hola %@!"
        assert validate_placeholders(original, translated) is False


class TestExtractPlaceholders:
    def test_extract_order(self):
        placeholders = extract_placeholders("Hello %@, you have %d items")
        assert placeholders[0] == "%@"
        assert placeholders[1] == "%d"

    def test_extract_empty(self):
        assert extract_placeholders("Hello world") == []


class TestDoubleBracePlaceholders:
    def test_mask_double_brace(self):
        result = mask_placeholders("Hello {{name}}, welcome to {{app}}")
        assert result.masked == "Hello __PH_1__, welcome to __PH_2__"
        assert result.placeholders == {"__PH_1__": "{{name}}", "__PH_2__": "{{app}}"}

    def test_unmask_double_brace(self):
        masked = "Hola __PH_1__, bienvenido a __PH_2__"
        placeholders = {"__PH_1__": "{{name}}", "__PH_2__": "{{app}}"}
        result = unmask_placeholders(masked, placeholders)
        assert result == "Hola {{name}}, bienvenido a {{app}}"

    def test_count_double_brace(self):
        assert count_placeholders("{{user}} has {{count}} items") == 2

    def test_validate_double_brace(self):
        assert validate_placeholders("Hello {{name}}!", "Hola {{name}}!") is True
        assert validate_placeholders("Hello {{name}}!", "Hola!") is False

    def test_extract_double_brace(self):
        placeholders = extract_placeholders("{{greeting}}, {{name}}")
        assert "{{greeting}}" in placeholders
        assert "{{name}}" in placeholders


class TestPositionalBracePlaceholders:
    def test_mask_positional_brace(self):
        result = mask_placeholders("Hello {0}, you have {1} messages")
        assert "__PH_1__" in result.masked
        assert "__PH_2__" in result.masked
        assert "{0}" in result.placeholders.values()
        assert "{1}" in result.placeholders.values()

    def test_unmask_positional_brace(self):
        masked = "Hola __PH_1__, tienes __PH_2__ mensajes"
        placeholders = {"__PH_1__": "{0}", "__PH_2__": "{1}"}
        result = unmask_placeholders(masked, placeholders)
        assert result == "Hola {0}, tienes {1} mensajes"

    def test_count_positional_brace(self):
        assert count_placeholders("{0} has {1} items") == 2

    def test_validate_positional_brace(self):
        assert validate_placeholders("Hello {0}!", "Hola {0}!") is True
        assert validate_placeholders("Hello {0}!", "Hola!") is False

    def test_mixed_double_and_positional(self):
        text = "{{greeting}} {0}!"
        result = mask_placeholders(text)
        assert len(result.placeholders) == 2
        assert "{{greeting}}" in result.placeholders.values()
        assert "{0}" in result.placeholders.values()
