"""Tests for metadata character limit validation."""

import pytest

from localizerx.parser.metadata_model import FIELD_LIMITS, MetadataFieldType
from localizerx.utils.limits import (
    LimitAction,
    LimitValidationResult,
    format_limit_warning,
    get_limit_for_field,
    truncate_to_limit,
    validate_limit,
)


class TestValidateLimit:
    def test_within_limit(self):
        result = validate_limit("Short text", MetadataFieldType.NAME)
        assert result.is_valid
        assert result.chars_over == 0
        assert result.char_count == 10

    def test_at_limit(self):
        # NAME limit is 30
        text = "x" * 30
        result = validate_limit(text, MetadataFieldType.NAME)
        assert result.is_valid
        assert result.chars_over == 0

    def test_over_limit(self):
        # NAME limit is 30
        text = "x" * 35
        result = validate_limit(text, MetadataFieldType.NAME)
        assert not result.is_valid
        assert result.chars_over == 5
        assert result.char_count == 35
        assert result.limit == 30

    def test_empty_string(self):
        result = validate_limit("", MetadataFieldType.NAME)
        assert result.is_valid
        assert result.char_count == 0

    def test_all_field_types(self):
        for field_type in MetadataFieldType:
            limit = FIELD_LIMITS[field_type]
            text = "x" * (limit + 10)
            result = validate_limit(text, field_type)
            assert not result.is_valid
            assert result.limit == limit

    def test_validation_result_message_valid(self):
        result = validate_limit("Test", MetadataFieldType.NAME)
        assert "OK" in result.message

    def test_validation_result_message_invalid(self):
        result = validate_limit("x" * 40, MetadataFieldType.NAME)
        assert "OVER LIMIT" in result.message
        assert "by 10 chars" in result.message


class TestTruncateToLimit:
    def test_no_truncation_needed(self):
        text = "Short text"
        result = truncate_to_limit(text, MetadataFieldType.NAME)
        assert result == text

    def test_basic_truncation(self):
        text = "x" * 40
        result = truncate_to_limit(text, MetadataFieldType.NAME)
        assert len(result) == 30

    def test_keywords_truncation_at_comma(self):
        keywords = "one,two,three,four,five,six,seven,eight,nine,ten,eleven,twelve,thirteen,fourteen,fifteen"
        result = truncate_to_limit(keywords, MetadataFieldType.KEYWORDS)

        # Should be within limit
        assert len(result) <= FIELD_LIMITS[MetadataFieldType.KEYWORDS]

        # Should end at a comma boundary (no partial keywords)
        assert not result.endswith(",")
        assert "," in result  # Should have some keywords

    def test_keywords_no_comma(self):
        # Keywords with no commas should truncate normally
        keywords = "x" * 120
        result = truncate_to_limit(keywords, MetadataFieldType.KEYWORDS)
        assert len(result) == 100

    def test_description_truncation(self):
        # Large description should truncate
        text = "x" * 5000
        result = truncate_to_limit(text, MetadataFieldType.DESCRIPTION)
        assert len(result) == 4000


class TestGetLimitForField:
    def test_all_field_limits(self):
        assert get_limit_for_field(MetadataFieldType.NAME) == 30
        assert get_limit_for_field(MetadataFieldType.SUBTITLE) == 30
        assert get_limit_for_field(MetadataFieldType.KEYWORDS) == 100
        assert get_limit_for_field(MetadataFieldType.DESCRIPTION) == 4000
        assert get_limit_for_field(MetadataFieldType.PROMOTIONAL_TEXT) == 170
        assert get_limit_for_field(MetadataFieldType.RELEASE_NOTES) == 4000


class TestLimitAction:
    def test_action_values(self):
        assert LimitAction.WARN.value == "warn"
        assert LimitAction.TRUNCATE.value == "truncate"
        assert LimitAction.ERROR.value == "error"

    def test_action_from_string(self):
        assert LimitAction("warn") == LimitAction.WARN
        assert LimitAction("truncate") == LimitAction.TRUNCATE
        assert LimitAction("error") == LimitAction.ERROR

    def test_invalid_action(self):
        with pytest.raises(ValueError):
            LimitAction("invalid")


class TestFormatLimitWarning:
    def test_format_warning(self):
        result = LimitValidationResult(
            field_type=MetadataFieldType.NAME,
            content="x" * 40,
            char_count=40,
            limit=30,
            is_valid=False,
            chars_over=10,
        )
        warning = format_limit_warning(result, "de-DE")
        assert "[de-DE]" in warning
        assert "name" in warning
        assert "40" in warning
        assert "30" in warning
        assert "10" in warning


class TestMetadataFieldLimits:
    """Test that MetadataField model handles limits correctly."""

    def test_field_char_count(self):
        from localizerx.parser.metadata_model import MetadataField

        field = MetadataField(field_type=MetadataFieldType.NAME, content="Test App")
        assert field.char_count == 8

    def test_field_is_over_limit(self):
        from localizerx.parser.metadata_model import MetadataField

        field = MetadataField(field_type=MetadataFieldType.NAME, content="x" * 35)
        assert field.is_over_limit
        assert field.chars_over == 5

    def test_field_not_over_limit(self):
        from localizerx.parser.metadata_model import MetadataField

        field = MetadataField(field_type=MetadataFieldType.NAME, content="x" * 25)
        assert not field.is_over_limit
        assert field.chars_over == 0

    def test_field_truncate(self):
        from localizerx.parser.metadata_model import MetadataField

        field = MetadataField(field_type=MetadataFieldType.NAME, content="x" * 40)
        truncated = field.truncate()

        assert truncated.char_count == 30
        assert not truncated.is_over_limit

    def test_field_truncate_no_change_needed(self):
        from localizerx.parser.metadata_model import MetadataField

        original = MetadataField(field_type=MetadataFieldType.NAME, content="Short")
        truncated = original.truncate()

        assert truncated.content == original.content

    def test_field_keywords_truncate_preserves_comma_boundary(self):
        from localizerx.parser.metadata_model import MetadataField

        keywords = "keyword1,keyword2,keyword3,keyword4,keyword5,keyword6,keyword7,keyword8,keyword9,keyword10"
        field = MetadataField(field_type=MetadataFieldType.KEYWORDS, content=keywords)

        truncated = field.truncate()
        assert not truncated.is_over_limit
        # Should not end with partial keyword
        assert not truncated.content.endswith(",")
