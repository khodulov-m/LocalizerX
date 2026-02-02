"""Tests for metadata CLI commands."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localizerx.cli import app

runner = CliRunner()


@pytest.fixture
def sample_metadata_dir():
    """Create a temporary metadata directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create en-US locale
        en_dir = tmpdir / "en-US"
        en_dir.mkdir()
        (en_dir / "name.txt").write_text("My Awesome App\n")
        (en_dir / "subtitle.txt").write_text("The best app ever\n")
        (en_dir / "keywords.txt").write_text("app,awesome,productivity\n")
        (en_dir / "description.txt").write_text("This is my awesome app.\n")
        (en_dir / "promotional_text.txt").write_text("Check out our new feature!\n")
        (en_dir / "release_notes.txt").write_text("- Bug fixes\n- New feature\n")

        yield tmpdir


@pytest.fixture
def sample_fastlane_metadata():
    """Create a fastlane/metadata directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        metadata_dir = tmpdir / "fastlane" / "metadata"
        metadata_dir.mkdir(parents=True)

        # Create en-US locale
        en_dir = metadata_dir / "en-US"
        en_dir.mkdir()
        (en_dir / "name.txt").write_text("My App\n")
        (en_dir / "subtitle.txt").write_text("Best app\n")

        yield tmpdir, metadata_dir


class TestMetadataCommand:
    """Tests for metadata command."""

    def test_metadata_requires_to_option(self, sample_metadata_dir):
        """Test that --to option is required."""
        result = runner.invoke(app, ["metadata", str(sample_metadata_dir)])
        assert result.exit_code == 1
        assert "--to option is required" in result.stdout

    def test_metadata_dry_run(self, sample_metadata_dir):
        """Test metadata command with --dry-run."""
        result = runner.invoke(
            app, ["metadata", str(sample_metadata_dir), "--to", "de-DE", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Dry run" in result.stdout

    def test_metadata_invalid_path(self):
        """Test metadata with non-existent path."""
        result = runner.invoke(app, ["metadata", "/nonexistent/path", "--to", "de-DE"])
        assert result.exit_code == 1
        assert "does not exist" in result.stdout

    def test_metadata_invalid_on_limit(self, sample_metadata_dir):
        """Test metadata with invalid --on-limit value."""
        result = runner.invoke(
            app, ["metadata", str(sample_metadata_dir), "--to", "de-DE", "--on-limit", "invalid"]
        )
        assert result.exit_code == 1
        assert "Invalid --on-limit value" in result.stdout

    def test_metadata_on_limit_options(self, sample_metadata_dir):
        """Test that valid --on-limit values are accepted."""
        for option in ["warn", "truncate", "error"]:
            result = runner.invoke(
                app,
                [
                    "metadata",
                    str(sample_metadata_dir),
                    "--to",
                    "de-DE",
                    "--on-limit",
                    option,
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0

    def test_metadata_fields_filter(self, sample_metadata_dir):
        """Test metadata with --fields filter."""
        result = runner.invoke(
            app,
            [
                "metadata",
                str(sample_metadata_dir),
                "--to",
                "de-DE",
                "--fields",
                "name,subtitle",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "name" in result.stdout
        assert "subtitle" in result.stdout

    def test_metadata_invalid_field(self, sample_metadata_dir):
        """Test metadata with invalid field name."""
        result = runner.invoke(
            app,
            [
                "metadata",
                str(sample_metadata_dir),
                "--to",
                "de-DE",
                "--fields",
                "invalid_field",
                "--dry-run",
            ],
        )
        assert result.exit_code == 1
        assert "No valid fields specified" in result.stdout

    def test_metadata_source_not_found(self, sample_metadata_dir):
        """Test metadata with non-existent source locale."""
        result = runner.invoke(
            app,
            [
                "metadata",
                str(sample_metadata_dir),
                "--to",
                "de-DE",
                "--src",
                "fr-FR",
                "--dry-run",
            ],
        )
        assert result.exit_code == 1
        assert "Source locale 'fr-FR' not found" in result.stdout


class TestMetadataInfoCommand:
    """Tests for metadata-info command."""

    def test_metadata_info_basic(self, sample_metadata_dir):
        """Test metadata-info command."""
        result = runner.invoke(app, ["metadata-info", str(sample_metadata_dir)])
        assert result.exit_code == 0
        assert "Metadata Directory:" in result.stdout
        assert "Source Locale:" in result.stdout
        assert "en-US" in result.stdout

    def test_metadata_info_shows_fields(self, sample_metadata_dir):
        """Test metadata-info shows field details."""
        result = runner.invoke(app, ["metadata-info", str(sample_metadata_dir)])
        assert result.exit_code == 0
        assert "Source Fields" in result.stdout
        assert "name" in result.stdout
        assert "subtitle" in result.stdout

    def test_metadata_info_invalid_path(self):
        """Test metadata-info with non-existent path."""
        result = runner.invoke(app, ["metadata-info", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "does not exist" in result.stdout


class TestMetadataAutoDetection:
    """Tests for metadata directory auto-detection."""

    def test_auto_detect_fastlane_metadata(self, sample_fastlane_metadata, monkeypatch):
        """Test auto-detection of fastlane/metadata directory."""
        tmpdir, _ = sample_fastlane_metadata
        monkeypatch.chdir(tmpdir)

        result = runner.invoke(app, ["metadata", "--to", "de-DE", "--dry-run"])
        assert result.exit_code == 0

    def test_auto_detect_no_metadata(self, monkeypatch):
        """Test failure when no metadata directory found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.chdir(tmpdir)
            result = runner.invoke(app, ["metadata", "--to", "de-DE"])
            assert result.exit_code == 1
            assert "No metadata directory found" in result.stdout


class TestMetadataLocaleValidation:
    """Tests for locale validation in metadata command."""

    def test_valid_locales(self, sample_metadata_dir):
        """Test with valid fastlane locales."""
        result = runner.invoke(
            app,
            ["metadata", str(sample_metadata_dir), "--to", "de-DE,fr-FR,ja", "--dry-run"],
        )
        assert result.exit_code == 0

    def test_invalid_locale_warning(self, sample_metadata_dir):
        """Test warning for unrecognized locales."""
        result = runner.invoke(
            app,
            ["metadata", str(sample_metadata_dir), "--to", "invalid-XX", "--dry-run"],
        )
        # Should show warning but continue
        assert "Unrecognized locale codes" in result.stdout


class TestMetadataDryRunOutput:
    """Tests for dry run output format."""

    def test_dry_run_shows_table(self, sample_metadata_dir):
        """Test that dry run shows a table of fields to translate."""
        result = runner.invoke(
            app,
            ["metadata", str(sample_metadata_dir), "--to", "de-DE", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Fields to Translate" in result.stdout
        assert "de-DE" in result.stdout

    def test_dry_run_shows_char_counts(self, sample_metadata_dir):
        """Test that dry run shows character counts."""
        result = runner.invoke(
            app,
            ["metadata", str(sample_metadata_dir), "--to", "de-DE", "--dry-run"],
        )
        assert result.exit_code == 0
        # Should show source length and limit columns
        assert "Source Length" in result.stdout or "Chars" in result.stdout
        assert "Limit" in result.stdout


@pytest.fixture
def metadata_with_overlimit():
    """Create a metadata directory with over-limit fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create en-US locale with over-limit fields
        en_dir = tmpdir / "en-US"
        en_dir.mkdir()
        (en_dir / "name.txt").write_text("x" * 40 + "\n")  # Limit is 30
        (en_dir / "subtitle.txt").write_text("x" * 35 + "\n")  # Limit is 30
        (en_dir / "keywords.txt").write_text("x" * 120 + "\n")  # Limit is 100
        (en_dir / "description.txt").write_text("Valid description\n")

        # Create de-DE locale with over-limit field
        de_dir = tmpdir / "de-DE"
        de_dir.mkdir()
        (de_dir / "name.txt").write_text("y" * 45 + "\n")  # Limit is 30

        yield tmpdir


class TestMetadataCheckCommand:
    """Tests for metadata-check command."""

    def test_metadata_check_all_valid(self, sample_metadata_dir):
        """Test metadata-check when all fields are valid."""
        result = runner.invoke(app, ["metadata-check", str(sample_metadata_dir)])
        assert result.exit_code == 0
        assert "All fields are within character limits" in result.stdout
        assert "Character Limit Summary" in result.stdout

    def test_metadata_check_with_violations(self, metadata_with_overlimit):
        """Test metadata-check when fields exceed limits."""
        result = runner.invoke(app, ["metadata-check", str(metadata_with_overlimit)])
        assert result.exit_code == 1
        assert "field(s) exceeding character limits" in result.stdout
        assert "Character Limit Violations" in result.stdout

    def test_metadata_check_single_locale(self, metadata_with_overlimit):
        """Test metadata-check with --locale filter."""
        result = runner.invoke(
            app, ["metadata-check", str(metadata_with_overlimit), "--locale", "en-US"]
        )
        assert result.exit_code == 1
        assert "en-US" in result.stdout
        # Should only show violations for en-US
        assert result.stdout.count("en-US") >= 2

    def test_metadata_check_single_field(self, metadata_with_overlimit):
        """Test metadata-check with --field filter."""
        result = runner.invoke(
            app, ["metadata-check", str(metadata_with_overlimit), "--field", "name"]
        )
        assert result.exit_code == 1
        assert "name" in result.stdout
        # Should only check 'name' field
        assert "subtitle" not in result.stdout or "Keywords" not in result.stdout

    def test_metadata_check_valid_field(self, metadata_with_overlimit):
        """Test metadata-check on a field that's within limits."""
        result = runner.invoke(
            app,
            ["metadata-check", str(metadata_with_overlimit), "--field", "description"],
        )
        assert result.exit_code == 0
        assert "All fields are within character limits" in result.stdout

    def test_metadata_check_invalid_field(self, sample_metadata_dir):
        """Test metadata-check with invalid field name."""
        result = runner.invoke(
            app, ["metadata-check", str(sample_metadata_dir), "--field", "invalid"]
        )
        assert result.exit_code == 1
        assert "Invalid field type" in result.stdout

    def test_metadata_check_invalid_locale(self, sample_metadata_dir):
        """Test metadata-check with non-existent locale."""
        result = runner.invoke(
            app, ["metadata-check", str(sample_metadata_dir), "--locale", "xx-XX"]
        )
        assert result.exit_code == 1
        assert "No valid locales to check" in result.stdout

    def test_metadata_check_invalid_path(self):
        """Test metadata-check with non-existent path."""
        result = runner.invoke(app, ["metadata-check", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "does not exist" in result.stdout

    def test_metadata_check_auto_detect(self, sample_fastlane_metadata, monkeypatch):
        """Test metadata-check with auto-detection."""
        tmpdir, _ = sample_fastlane_metadata
        monkeypatch.chdir(tmpdir)

        result = runner.invoke(app, ["metadata-check"])
        assert result.exit_code == 0

    def test_metadata_check_shows_violation_details(self, metadata_with_overlimit):
        """Test that violations show all required details."""
        result = runner.invoke(app, ["metadata-check", str(metadata_with_overlimit)])
        assert result.exit_code == 1
        # Should show locale, field, characters, limit, and over by
        assert "Locale" in result.stdout
        assert "Field" in result.stdout
        assert "Characters" in result.stdout
        assert "Limit" in result.stdout
        assert "Over By" in result.stdout
