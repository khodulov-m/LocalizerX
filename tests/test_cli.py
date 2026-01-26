"""Tests for CLI."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from localizerx.cli import _find_xcstrings_files, _prompt_file_selection, app
from localizerx.config import DEFAULT_TARGET_LANGUAGES

runner = CliRunner()


@pytest.fixture
def sample_xcstrings():
    """Sample xcstrings content for testing."""
    return {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "hello": {
                "localizations": {
                    "en": {"stringUnit": {"state": "translated", "value": "Hello"}}
                }
            }
        },
    }


@pytest.fixture
def temp_xcstrings_file(sample_xcstrings):
    """Create a temporary xcstrings file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xcstrings", delete=False
    ) as f:
        json.dump(sample_xcstrings, f)
        return Path(f.name)


@pytest.fixture
def temp_dir_with_xcstrings(sample_xcstrings):
    """Create a temporary directory with xcstrings files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create single file
        file1 = tmpdir / "Localizable.xcstrings"
        file1.write_text(json.dumps(sample_xcstrings))

        yield tmpdir, [file1]


@pytest.fixture
def temp_dir_with_multiple_xcstrings(sample_xcstrings):
    """Create a temporary directory with multiple xcstrings files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create multiple files in subdirectories
        (tmpdir / "App").mkdir()
        (tmpdir / "Widgets").mkdir()

        file1 = tmpdir / "App" / "Localizable.xcstrings"
        file2 = tmpdir / "Widgets" / "Localizable.xcstrings"

        file1.write_text(json.dumps(sample_xcstrings))
        file2.write_text(json.dumps(sample_xcstrings))

        yield tmpdir, sorted([file1, file2])


class TestFindXcstringsFiles:
    """Tests for _find_xcstrings_files."""

    def test_find_single_file(self, temp_xcstrings_file):
        """Find a single xcstrings file by path."""
        files = _find_xcstrings_files(temp_xcstrings_file)
        assert len(files) == 1
        assert files[0] == temp_xcstrings_file
        temp_xcstrings_file.unlink()

    def test_find_files_in_directory(self, temp_dir_with_xcstrings):
        """Find xcstrings files in a directory."""
        tmpdir, expected_files = temp_dir_with_xcstrings
        files = _find_xcstrings_files(tmpdir)
        assert len(files) == 1
        assert files[0].name == "Localizable.xcstrings"

    def test_find_files_recursively(self, temp_dir_with_multiple_xcstrings):
        """Find xcstrings files recursively in subdirectories."""
        tmpdir, expected_files = temp_dir_with_multiple_xcstrings
        files = _find_xcstrings_files(tmpdir)
        assert len(files) == 2
        assert all(f.suffix == ".xcstrings" for f in files)

    def test_non_xcstrings_file_returns_empty(self):
        """Return empty list for non-xcstrings files."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = Path(f.name)

        files = _find_xcstrings_files(path)
        assert files == []
        path.unlink()

    def test_empty_directory_returns_empty(self):
        """Return empty list for directory without xcstrings files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = _find_xcstrings_files(Path(tmpdir))
            assert files == []


class TestPromptFileSelection:
    """Tests for _prompt_file_selection."""

    def test_select_single_file(self, temp_dir_with_multiple_xcstrings):
        """Select a single file by number."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="1"):
            selected = _prompt_file_selection(files)
        assert len(selected) == 1
        assert selected[0] == files[0]

    def test_select_all_files(self, temp_dir_with_multiple_xcstrings):
        """Select all files with 'a'."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="a"):
            selected = _prompt_file_selection(files)
        assert selected == files

    def test_select_multiple_files_comma(self, temp_dir_with_multiple_xcstrings):
        """Select multiple files with comma-separated numbers."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="1,2"):
            selected = _prompt_file_selection(files)
        assert len(selected) == 2

    def test_select_range(self, temp_dir_with_multiple_xcstrings):
        """Select files with range notation."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="1-2"):
            selected = _prompt_file_selection(files)
        assert len(selected) == 2

    def test_invalid_selection(self, temp_dir_with_multiple_xcstrings):
        """Invalid selection returns empty list."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="invalid"):
            selected = _prompt_file_selection(files)
        assert selected == []

    def test_out_of_range_ignored(self, temp_dir_with_multiple_xcstrings):
        """Out of range numbers are ignored."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="1,99"):
            selected = _prompt_file_selection(files)
        assert len(selected) == 1
        assert selected[0] == files[0]

    def test_duplicates_removed(self, temp_dir_with_multiple_xcstrings):
        """Duplicate selections are removed."""
        _, files = temp_dir_with_multiple_xcstrings
        with patch("localizerx.cli.typer.prompt", return_value="1,1,1"):
            selected = _prompt_file_selection(files)
        assert len(selected) == 1


class TestCLICommands:
    """Tests for CLI commands."""

    def test_version_option(self):
        """Test --version option."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "LocalizerX version" in result.stdout

    def test_help_option(self):
        """Test --help option."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Translate Xcode String Catalogs" in result.stdout

    def test_no_args_shows_help(self):
        """Test that no arguments shows help."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Translate Xcode String Catalogs" in result.stdout

    def test_translate_without_to_uses_defaults(self, temp_dir_with_xcstrings, monkeypatch):
        """Test that translate without --to uses default targets from config."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"])
        assert result.exit_code == 0
        assert "Using default targets from config" in result.stdout
        assert f"{len(DEFAULT_TARGET_LANGUAGES)} languages" in result.stdout

    def test_translate_without_to_shows_all_default_languages(self, temp_dir_with_xcstrings, monkeypatch):
        """Test that translate without --to shows all default languages."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"])
        assert result.exit_code == 0
        # Check some of the default languages are shown in targets
        assert "Russian" in result.stdout or "ru" in result.stdout
        assert "French" in result.stdout or "fr" in result.stdout
        assert "Japanese" in result.stdout or "ja" in result.stdout

    def test_translate_dry_run(self, temp_dir_with_xcstrings):
        """Test translate command with --dry-run."""
        tmpdir, _ = temp_dir_with_xcstrings
        result = runner.invoke(
            app, ["translate", str(tmpdir), "--to", "ru", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Found 1 .xcstrings file(s)" in result.stdout

    def test_translate_with_path(self, temp_xcstrings_file):
        """Test translate command with explicit path."""
        result = runner.invoke(
            app, ["translate", str(temp_xcstrings_file), "--to", "ru", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Found 1 .xcstrings file(s)" in result.stdout
        temp_xcstrings_file.unlink()

    def test_translate_invalid_path(self):
        """Test translate with non-existent path."""
        result = runner.invoke(
            app, ["translate", "/nonexistent/path", "--to", "ru"]
        )
        assert result.exit_code == 1
        assert "does not exist" in result.stdout

    def test_translate_no_xcstrings_in_path(self):
        """Test translate with path containing no xcstrings files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["translate", tmpdir, "--to", "ru"])
            assert result.exit_code == 1
            assert "No .xcstrings files found" in result.stdout

    def test_main_callback_with_to_option(self, temp_dir_with_xcstrings, monkeypatch):
        """Test main callback with --to option (shorthand syntax)."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["--to", "ru", "--dry-run"])
        assert result.exit_code == 0
        assert "Found 1 .xcstrings file(s)" in result.stdout

    def test_models_command(self):
        """Test models command."""
        result = runner.invoke(app, ["models"])
        assert result.exit_code == 0
        assert "Available Gemini Models" in result.stdout

    def test_languages_command(self):
        """Test languages command."""
        result = runner.invoke(app, ["languages"])
        assert result.exit_code == 0
        assert "Supported Languages" in result.stdout

    def test_info_command(self, temp_xcstrings_file):
        """Test info command."""
        result = runner.invoke(app, ["info", str(temp_xcstrings_file)])
        assert result.exit_code == 0
        assert "Source Language:" in result.stdout
        assert "Total Strings:" in result.stdout
        temp_xcstrings_file.unlink()

    def test_info_non_xcstrings_file(self):
        """Test info command with non-xcstrings file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = Path(f.name)

        result = runner.invoke(app, ["info", str(path)])
        assert result.exit_code == 1
        assert "Not an .xcstrings file" in result.stdout
        path.unlink()


class TestAutoDetection:
    """Tests for auto-detection of xcstrings files."""

    def test_auto_detect_single_file(self, temp_dir_with_xcstrings, monkeypatch):
        """Auto-detect single xcstrings file in current directory."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["--to", "fr", "--dry-run"])
        assert result.exit_code == 0
        assert "Found 1 .xcstrings file(s)" in result.stdout

    def test_auto_detect_prompts_for_multiple(
        self, temp_dir_with_multiple_xcstrings, monkeypatch
    ):
        """Auto-detect prompts for selection when multiple files found."""
        tmpdir, _ = temp_dir_with_multiple_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["--to", "fr", "--dry-run"], input="a\n")
        assert result.exit_code == 0
        assert "Found 2 .xcstrings file(s)" in result.stdout

    def test_auto_detect_no_files(self, monkeypatch):
        """Auto-detect fails gracefully when no files found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.chdir(tmpdir)
            result = runner.invoke(app, ["--to", "fr"])
            assert result.exit_code == 1
            assert "No .xcstrings files found" in result.stdout

    def test_auto_detect_select_one(
        self, temp_dir_with_multiple_xcstrings, monkeypatch
    ):
        """Select one file when multiple are found."""
        tmpdir, files = temp_dir_with_multiple_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["--to", "fr", "--dry-run"], input="1\n")
        assert result.exit_code == 0
        assert "Found 1 .xcstrings file(s)" in result.stdout

    def test_auto_detect_cancel_selection(
        self, temp_dir_with_multiple_xcstrings, monkeypatch
    ):
        """Cancel when prompted for file selection."""
        tmpdir, _ = temp_dir_with_multiple_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["--to", "fr"], input="invalid\n")
        assert "Cancelled" in result.stdout


class TestDefaultTargets:
    """Tests for default target languages feature."""

    @pytest.fixture
    def sample_xcstrings(self):
        """Sample xcstrings content for testing."""
        return {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}}
                    }
                }
            },
        }

    @pytest.fixture
    def temp_dir_with_xcstrings(self, sample_xcstrings):
        """Create a temporary directory with xcstrings files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            file1 = tmpdir / "Localizable.xcstrings"
            file1.write_text(json.dumps(sample_xcstrings))
            yield tmpdir, [file1]

    def test_translate_uses_default_targets_when_to_omitted(
        self, temp_dir_with_xcstrings, monkeypatch
    ):
        """Translate command should use default targets when --to is omitted."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"])
        assert result.exit_code == 0
        assert "Using default targets from config" in result.stdout

    def test_translate_explicit_to_overrides_defaults(
        self, temp_dir_with_xcstrings, monkeypatch
    ):
        """Explicit --to option should override default targets."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--to", "es", "--dry-run"])
        assert result.exit_code == 0
        # Should not show "Using default targets" message
        assert "Using default targets" not in result.stdout
        # Should show only Spanish
        assert "Spanish" in result.stdout
        # Should not show other default languages
        assert "Russian" not in result.stdout
        assert "Japanese" not in result.stdout

    def test_translate_default_targets_count(
        self, temp_dir_with_xcstrings, monkeypatch
    ):
        """Translate should show correct count of default languages."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"])
        assert result.exit_code == 0
        assert "14 languages" in result.stdout

    def test_translate_default_targets_dry_run_shows_languages(
        self, temp_dir_with_xcstrings, monkeypatch
    ):
        """Dry run with default targets should show all target languages."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"])
        assert result.exit_code == 0
        # Check output contains target language info
        assert "Targets:" in result.stdout

    def test_translate_with_explicit_path_uses_defaults(
        self, temp_dir_with_xcstrings
    ):
        """Translate with explicit path should use default targets when --to omitted."""
        tmpdir, files = temp_dir_with_xcstrings
        result = runner.invoke(app, ["translate", str(files[0]), "--dry-run"])
        assert result.exit_code == 0
        assert "Using default targets from config" in result.stdout

    def test_translate_with_custom_config_default_targets(
        self, temp_dir_with_xcstrings
    ):
        """Translate should use custom default_targets from config file."""
        tmpdir, files = temp_dir_with_xcstrings

        # Create custom config with only 2 languages
        config_content = '''
source_language = "en"
default_targets = ["fr", "de"]

[translator]
model = "gemini-2.5-flash-lite"
'''
        config_path = tmpdir / "config.toml"
        config_path.write_text(config_content)

        result = runner.invoke(
            app,
            ["translate", str(files[0]), "--config", str(config_path), "--dry-run"]
        )
        assert result.exit_code == 0
        assert "Using default targets from config (2 languages)" in result.stdout
        assert "French" in result.stdout
        assert "German" in result.stdout
        # Should not have other languages
        assert "Russian" not in result.stdout

    def test_translate_with_empty_config_default_targets(
        self, temp_dir_with_xcstrings
    ):
        """Translate should show error when config has empty default_targets."""
        tmpdir, files = temp_dir_with_xcstrings

        # Create config with empty default_targets
        config_content = '''
source_language = "en"
default_targets = []

[translator]
model = "gemini-2.5-flash-lite"
'''
        config_path = tmpdir / "config.toml"
        config_path.write_text(config_content)

        result = runner.invoke(
            app,
            ["translate", str(files[0]), "--config", str(config_path)]
        )
        assert result.exit_code == 1
        assert "No target languages specified" in result.stdout

    def test_main_callback_without_to_shows_help(self):
        """Main callback without --to should show help (not use defaults)."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        # Should show help, not start translation
        assert "Translate Xcode String Catalogs" in result.stdout

    def test_translate_subcommand_help_shows_default_info(self):
        """Translate subcommand help should mention default targets."""
        result = runner.invoke(app, ["translate", "--help"])
        assert result.exit_code == 0
        assert "default" in result.stdout.lower()

    def test_translate_default_targets_includes_all_expected_languages(
        self, temp_dir_with_xcstrings, monkeypatch
    ):
        """Translate should include all expected default languages."""
        tmpdir, _ = temp_dir_with_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"])
        assert result.exit_code == 0

        # Check that the output mentions various expected languages
        # (checking both language names and codes)
        expected_indicators = [
            ("ru", "Russian"),
            ("fr", "French"),
            ("pt-BR", "Portuguese"),
            ("es-MX", "Spanish"),
            ("it", "Italian"),
            ("ja", "Japanese"),
            ("pl", "Polish"),
            ("no", "Norwegian"),
            ("de-DE", "German"),
            ("nl", "Dutch"),
            ("ko", "Korean"),
            ("da", "Danish"),
            ("sv", "Swedish"),
            ("ro", "Romanian"),
        ]

        output = result.stdout
        for code, name in expected_indicators:
            assert code in output or name in output, f"Expected {code} or {name} in output"


class TestDefaultTargetsWithMultipleFiles:
    """Tests for default targets with multiple xcstrings files."""

    @pytest.fixture
    def sample_xcstrings(self):
        """Sample xcstrings content for testing."""
        return {
            "sourceLanguage": "en",
            "version": "1.0",
            "strings": {
                "hello": {
                    "localizations": {
                        "en": {"stringUnit": {"state": "translated", "value": "Hello"}}
                    }
                }
            },
        }

    @pytest.fixture
    def temp_dir_with_multiple_xcstrings(self, sample_xcstrings):
        """Create a temporary directory with multiple xcstrings files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "App").mkdir()
            (tmpdir / "Widgets").mkdir()

            file1 = tmpdir / "App" / "Localizable.xcstrings"
            file2 = tmpdir / "Widgets" / "Localizable.xcstrings"

            file1.write_text(json.dumps(sample_xcstrings))
            file2.write_text(json.dumps(sample_xcstrings))

            yield tmpdir, sorted([file1, file2])

    def test_translate_multiple_files_uses_defaults(
        self, temp_dir_with_multiple_xcstrings, monkeypatch
    ):
        """Translate multiple files should use default targets."""
        tmpdir, _ = temp_dir_with_multiple_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"], input="a\n")
        assert result.exit_code == 0
        assert "Using default targets from config" in result.stdout
        assert "Found 2 .xcstrings file(s)" in result.stdout

    def test_translate_select_one_file_uses_defaults(
        self, temp_dir_with_multiple_xcstrings, monkeypatch
    ):
        """Select one file from multiple should use default targets."""
        tmpdir, _ = temp_dir_with_multiple_xcstrings
        monkeypatch.chdir(tmpdir)
        result = runner.invoke(app, ["translate", "--dry-run"], input="1\n")
        assert result.exit_code == 0
        assert "Using default targets from config" in result.stdout
        assert "Found 1 .xcstrings file(s)" in result.stdout
