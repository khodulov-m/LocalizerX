"""Tests for configuration management."""

import tempfile
from pathlib import Path

import pytest

from localizerx.config import (
    DEFAULT_TARGET_LANGUAGES,
    Config,
    TranslatorConfig,
    create_default_config,
    load_config,
)


class TestDefaultTargetLanguages:
    """Tests for DEFAULT_TARGET_LANGUAGES constant."""

    def test_default_targets_is_list(self):
        """Default targets should be a list."""
        assert isinstance(DEFAULT_TARGET_LANGUAGES, list)

    def test_default_targets_not_empty(self):
        """Default targets should not be empty."""
        assert len(DEFAULT_TARGET_LANGUAGES) > 0

    def test_default_targets_contains_expected_languages(self):
        """Default targets should contain expected languages."""
        expected = [
            "ru",
            "fr-FR",
            "pt-BR",
            "es-MX",
            "it",
            "ja",
            "pl",
            "no",
            "de-DE",
            "nl-NL",
            "ko",
            "da",
            "sk",
            "sv",
            "ro",
            "uk",
            "hi",
            "he",
            "hr",
            "zh-Hans",
            "zh-Hant",
            "fi",
            "th",
            "vi",
            "en-GB",
            "ms",
            "id",
            "tr",
        ]
        assert DEFAULT_TARGET_LANGUAGES == expected

    def test_default_targets_count(self):
        """Default targets should have 28 languages."""
        assert len(DEFAULT_TARGET_LANGUAGES) == 28

    def test_default_targets_all_strings(self):
        """All default targets should be strings."""
        assert all(isinstance(lang, str) for lang in DEFAULT_TARGET_LANGUAGES)

    def test_default_targets_no_duplicates(self):
        """Default targets should have no duplicates."""
        assert len(DEFAULT_TARGET_LANGUAGES) == len(set(DEFAULT_TARGET_LANGUAGES))


class TestConfig:
    """Tests for Config class."""

    def test_config_default_values(self):
        """Config should have correct default values."""
        config = Config()
        assert config.source_language == "en"
        assert config.concurrency == 5
        assert config.backup_enabled is False
        assert config.cache_enabled is True

    def test_config_default_targets(self):
        """Config should have default_targets field."""
        config = Config()
        assert hasattr(config, "default_targets")
        assert isinstance(config.default_targets, list)

    def test_config_default_targets_matches_constant(self):
        """Config default_targets should match DEFAULT_TARGET_LANGUAGES."""
        config = Config()
        assert config.default_targets == DEFAULT_TARGET_LANGUAGES

    def test_config_default_targets_is_copy(self):
        """Config default_targets should be a copy, not a reference."""
        config1 = Config()
        config2 = Config()
        config1.default_targets.append("test")
        assert "test" not in config2.default_targets
        assert "test" not in DEFAULT_TARGET_LANGUAGES

    def test_config_custom_default_targets(self):
        """Config should accept custom default_targets."""
        custom_targets = ["fr", "de"]
        config = Config(default_targets=custom_targets)
        assert config.default_targets == custom_targets

    def test_config_empty_default_targets(self):
        """Config should accept empty default_targets."""
        config = Config(default_targets=[])
        assert config.default_targets == []

    def test_config_translator_defaults(self):
        """Config should have default translator settings."""
        config = Config()
        assert config.translator.provider == "gemini"
        assert config.translator.batch_size == 180
        assert config.translator.max_retries == 3


class TestTranslatorConfig:
    """Tests for TranslatorConfig class."""

    def test_translator_config_defaults(self):
        """TranslatorConfig should have correct defaults."""
        tc = TranslatorConfig()
        assert tc.provider == "gemini"
        assert tc.batch_size == 180
        assert tc.max_retries == 3
        assert tc.custom_instructions is None
        assert tc.use_app_context is True

    def test_translator_config_custom_values(self):
        """TranslatorConfig should accept custom values."""
        tc = TranslatorConfig(provider="custom", batch_size=50, max_retries=5)
        assert tc.provider == "custom"
        assert tc.batch_size == 50
        assert tc.max_retries == 5

    def test_translator_config_batch_size_validation(self):
        """TranslatorConfig should validate batch_size bounds."""
        # Valid batch_size
        tc = TranslatorConfig(batch_size=1)
        assert tc.batch_size == 1

        tc = TranslatorConfig(batch_size=180)
        assert tc.batch_size == 180

        # Invalid batch_size should raise
        with pytest.raises(ValueError):
            TranslatorConfig(batch_size=0)

        with pytest.raises(ValueError):
            TranslatorConfig(batch_size=501)

    def test_translator_config_max_retries_validation(self):
        """TranslatorConfig should validate max_retries bounds."""
        # Valid max_retries
        tc = TranslatorConfig(max_retries=1)
        assert tc.max_retries == 1

        tc = TranslatorConfig(max_retries=10)
        assert tc.max_retries == 10

        # Invalid max_retries should raise
        with pytest.raises(ValueError):
            TranslatorConfig(max_retries=0)

        with pytest.raises(ValueError):
            TranslatorConfig(max_retries=11)

    def test_translator_config_custom_instructions(self):
        """TranslatorConfig should accept custom_instructions."""
        tc = TranslatorConfig(custom_instructions="Do not translate proper names")
        assert tc.custom_instructions == "Do not translate proper names"

        tc = TranslatorConfig(custom_instructions=None)
        assert tc.custom_instructions is None


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_nonexistent_file(self):
        """Load config returns defaults when file doesn't exist."""
        config = load_config(Path("/nonexistent/path/config.toml"))
        assert config.source_language == "en"
        assert config.default_targets == DEFAULT_TARGET_LANGUAGES

    def test_load_config_basic_file(self):
        """Load config from basic TOML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('source_language = "de"\n')
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.source_language == "de"
            # default_targets should still be default
            assert config.default_targets == DEFAULT_TARGET_LANGUAGES
        finally:
            config_path.unlink()

    def test_load_config_with_default_targets(self):
        """Load config with custom default_targets."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('source_language = "en"\n')
            f.write('default_targets = ["fr", "de", "es"]\n')
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.default_targets == ["fr", "de", "es"]
        finally:
            config_path.unlink()

    def test_load_config_with_empty_default_targets(self):
        """Load config with empty default_targets."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('source_language = "en"\n')
            f.write("default_targets = []\n")
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.default_targets == []
        finally:
            config_path.unlink()

    def test_load_config_with_translator_section(self):
        """Load config with translator section."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[translator]\n")
            f.write('model = "gemini-2.5-pro"\n')
            f.write("batch_size = 50\n")
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.translator.model == "gemini-2.5-pro"
            assert config.translator.batch_size == 50
        finally:
            config_path.unlink()

    def test_load_config_with_custom_instructions(self):
        """Load config with custom translation instructions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[translator]\n")
            f.write('custom_instructions = "Do not translate proper names"\n')
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.translator.custom_instructions == "Do not translate proper names"
        finally:
            config_path.unlink()

    def test_load_config_full_example(self):
        """Load config with all options."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('source_language = "ja"\n')
            f.write('default_targets = ["en", "ko", "zh-Hans"]\n')
            f.write("concurrency = 10\n")
            f.write("backup_enabled = false\n")
            f.write("cache_enabled = false\n")
            f.write("\n")
            f.write("[translator]\n")
            f.write('provider = "gemini"\n')
            f.write('model = "gemini-2.5-flash"\n')
            f.write("batch_size = 25\n")
            f.write("max_retries = 5\n")
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.source_language == "ja"
            assert config.default_targets == ["en", "ko", "zh-Hans"]
            assert config.concurrency == 10
            assert config.backup_enabled is False
            assert config.cache_enabled is False
            assert config.translator.model == "gemini-2.5-flash"
            assert config.translator.batch_size == 25
            assert config.translator.max_retries == 5
        finally:
            config_path.unlink()


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_create_default_config_creates_file(self):
        """Create default config creates a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            result = create_default_config(config_path)

            assert result == config_path
            assert config_path.exists()

    def test_create_default_config_contains_default_targets(self):
        """Created config should contain default_targets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            content = config_path.read_text()
            assert "default_targets" in content

    def test_create_default_config_default_targets_values(self):
        """Created config should have correct default_targets values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            content = config_path.read_text()
            # Check some of the expected languages are present
            assert '"ru"' in content
            assert '"fr-FR"' in content
            assert '"pt-BR"' in content
            assert '"ja"' in content
            assert '"de-DE"' in content

    def test_create_default_config_is_valid_toml(self):
        """Created config should be valid TOML that can be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            # Should be able to load the created config
            config = load_config(config_path)
            assert config.source_language == "en"
            assert config.default_targets == DEFAULT_TARGET_LANGUAGES

    def test_create_default_config_creates_parent_dirs(self):
        """Create default config should create parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "path" / "config.toml"
            create_default_config(config_path)

            assert config_path.exists()
            assert config_path.parent.exists()

    def test_create_default_config_contains_all_sections(self):
        """Created config should contain all expected sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            content = config_path.read_text()
            assert "source_language" in content
            assert "default_targets" in content
            assert "concurrency" in content
            assert "backup_enabled" in content
            assert "cache_enabled" in content
            assert "[translator]" in content
            assert "model" in content
            assert "batch_size" in content
            assert "max_retries" in content
            assert "use_app_context" in content
