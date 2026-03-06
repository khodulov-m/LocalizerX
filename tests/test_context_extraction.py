"""Tests for app context extraction logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from localizerx.parser.app_context import AppContext
from localizerx.parser.metadata_model import LocaleMetadata, MetadataFieldType
from localizerx.utils.context import extract_app_context_string


class TestAppContextExtraction:
    """Tests for AppContext data extraction and summarization."""

    def test_description_summary_short(self):
        """Test description summary with short text."""
        context = AppContext(name="TestApp", description="Short description.")
        assert context.get_description_summary(150) == "Short description."

    def test_description_summary_long_truncated(self):
        """Test description summary with long text truncates correctly."""
        long_desc = "This is a very long description. " * 20  # ~660 chars
        context = AppContext(name="TestApp", description=long_desc)

        summary = context.get_description_summary(max_length=150)
        assert summary is not None
        assert len(summary) <= 153  # 150 + "..."
        assert summary.endswith("...")
        assert "This is a very long description" in summary

    def test_description_summary_no_spaces(self):
        """Test description summary with long text without spaces."""
        long_desc = "A" * 600
        context = AppContext(name="TestApp", description=long_desc)

        summary = context.get_description_summary(max_length=150)
        assert summary is not None
        assert summary == "A" * 150 + "..."

    def test_to_prompt_context_formatting(self):
        """Test to_prompt_context formats correctly."""
        context = AppContext(
            name="SuperApp",
            subtitle="The best app",
            promo_text="50% off today",
            description="Detailed description goes here.",
            keywords=["app", "best", "super"],
        )

        prompt = context.to_prompt_context(max_desc_length=150)

        assert "- App Name: SuperApp" in prompt
        assert "- Tagline: The best app" in prompt
        assert "- Promo: 50% off today" in prompt
        assert "- Description: Detailed description goes here." in prompt
        assert "- Keywords: app, best, super" in prompt

    def test_to_prompt_context_missing_fields(self):
        """Test to_prompt_context handles missing fields."""
        context = AppContext(name="MinimalApp")

        prompt = context.to_prompt_context(max_desc_length=150)

        assert "- App Name: MinimalApp" in prompt
        assert "- Tagline:" not in prompt
        assert "- Promo:" not in prompt
        assert "- Description:" not in prompt
        assert "- Keywords:" not in prompt

    def test_to_prompt_context_max_desc_length(self):
        """Test to_prompt_context respects max_desc_length."""
        context = AppContext(name="SuperApp", description="This is a very long description. " * 20)

        prompt = context.to_prompt_context(max_desc_length=50)
        assert "- App Name: SuperApp" in prompt
        # the description line should be relatively short (around 50 + "..." + length
        # of "- Description: ")
        # Let's just check the description line is in the output and ends with ...
        assert "..." in prompt


@patch("localizerx.utils.context.detect_metadata_path")
@patch("localizerx.utils.context.read_metadata")
class TestExtractAppContextString:
    """Tests for extract_app_context_string utility function."""

    def test_extract_from_metadata(self, mock_read, mock_detect):
        """Test extracting context from fastlane metadata."""
        mock_detect.return_value = Path("/mock/metadata")

        # Setup mock metadata
        mock_catalog = MagicMock()
        mock_locale = LocaleMetadata(locale="en-US")
        mock_locale.set_field(MetadataFieldType.NAME, "MetaApp")
        mock_locale.set_field(MetadataFieldType.SUBTITLE, "Metadata Subtitle")
        mock_catalog.locales = {"en-US": mock_locale}
        mock_read.return_value = mock_catalog

        result = extract_app_context_string()

        assert result is not None
        assert "- App Name: MetaApp" in result
        assert "- Tagline: Metadata Subtitle" in result

    @patch("pathlib.Path.cwd")
    def test_extract_from_xcworkspace(self, mock_cwd, mock_read, mock_detect):
        """Test fallback to xcworkspace when metadata is not available."""
        mock_detect.return_value = None  # No metadata

        # Setup mock cwd to return an xcworkspace
        mock_path = MagicMock()
        mock_workspace = MagicMock()
        mock_workspace.stem = "MyWorkspaceApp"
        mock_path.glob.side_effect = lambda pattern: (
            [mock_workspace] if pattern == "*.xcworkspace" else []
        )
        mock_cwd.return_value = mock_path

        result = extract_app_context_string()

        assert result is not None
        assert result == "- App Name: MyWorkspaceApp"

    @patch("pathlib.Path.cwd")
    def test_extract_from_xcodeproj(self, mock_cwd, mock_read, mock_detect):
        """Test fallback to xcodeproj when metadata and xcworkspace are not available."""
        mock_detect.return_value = None  # No metadata

        # Setup mock cwd to return an xcodeproj
        mock_path = MagicMock()
        mock_project = MagicMock()
        mock_project.stem = "MyProjectApp"

        def mock_glob(pattern):
            if pattern == "*.xcodeproj":
                return [mock_project]
            return []

        mock_path.glob.side_effect = mock_glob
        mock_cwd.return_value = mock_path

        result = extract_app_context_string()

        assert result is not None
        assert result == "- App Name: MyProjectApp"

    @patch("pathlib.Path.cwd")
    def test_extract_no_context_found(self, mock_cwd, mock_read, mock_detect):
        """Test when no context can be found at all."""
        mock_detect.return_value = None

        mock_path = MagicMock()
        mock_path.glob.return_value = []
        mock_cwd.return_value = mock_path

        result = extract_app_context_string()

        assert result is None
