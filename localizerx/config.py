"""Configuration management for LocalizerX."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "localizerx" / "config.toml"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "localizerx"

# Available Gemini models
GEMINI_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_SCREENSHOTS_MODEL = "gemini-3-flash-preview"


VALID_THINKING_LEVELS = ["minimal", "low", "medium", "high"]


class ScreenshotsConfig(BaseModel):
    """Configuration for screenshot text generation/translation."""

    model: str = DEFAULT_SCREENSHOTS_MODEL
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    thinking_level: str = Field(default="low")
    batch_size: int = Field(default=50, ge=1, le=50)


class TranslatorConfig(BaseModel):
    """Configuration for translation provider."""

    provider: str = "gemini"
    model: str = DEFAULT_MODEL
    batch_size: int = Field(default=100, ge=1, le=100)
    max_retries: int = Field(default=3, ge=1, le=10)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    thinking_level: str = Field(
        default="0",
        description="Thinking budget level (e.g. '0', 'minimal', 'low', 'medium', 'high')",
    )
    custom_instructions: str | None = None
    use_app_context: bool = Field(
        default=True,
        description="Automatically extract and use app context from fastlane metadata "
        "or Xcode projects in translation prompts.",
    )
    screenshots: ScreenshotsConfig = Field(default_factory=ScreenshotsConfig)


DEFAULT_TARGET_LANGUAGES = [
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


class Config(BaseModel):
    """Main configuration for LocalizerX."""

    source_language: str = "en"
    default_targets: list[str] = Field(default_factory=lambda: DEFAULT_TARGET_LANGUAGES.copy())
    concurrency: int = Field(default=5, ge=1, le=20)
    backup_enabled: bool = False
    cache_enabled: bool = True
    cache_dir: Path = DEFAULT_CACHE_DIR
    translator: TranslatorConfig = Field(default_factory=TranslatorConfig)

    class Config:
        arbitrary_types_allowed = True


def load_config(path: Path | None = None) -> Config:
    """
    Load configuration from TOML file.

    Falls back to defaults if file doesn't exist.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return Config()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> Config:
    """Parse configuration dictionary into Config object."""
    translator_data = data.pop("translator", {})
    translator = TranslatorConfig(**translator_data)

    # Handle cache_dir as Path
    if "cache_dir" in data:
        data["cache_dir"] = Path(data["cache_dir"]).expanduser()

    return Config(translator=translator, **data)


def get_cache_dir(config: Config) -> Path | None:
    """Get cache directory if caching is enabled."""
    if not config.cache_enabled:
        return None
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    return config.cache_dir


def create_default_config(path: Path | None = None) -> Path:
    """Create a default configuration file."""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_content = """# LocalizerX Configuration

# Source language for translations (default: en)
source_language = "en"

# Default target languages (used when --to is omitted)
# Run: localizerx translate (without --to) to translate to all these languages
default_targets = [
    "ru", "fr-FR", "pt-BR", "es-MX", "it", "ja", "pl", "no",
    "de-DE", "nl-NL", "ko", "da", "sk", "sv", "ro", "uk",
    "hi", "he", "hr", "zh-Hans", "zh-Hant", "fi", "th", "vi",
    "en-GB", "ms", "id","tr",
]

# Number of concurrent translation requests
concurrency = 5

# Create backup before writing changes
backup_enabled = false

# Enable translation caching
cache_enabled = true

# Cache directory (default: ~/.cache/localizerx)
# cache_dir = "~/.cache/localizerx"

[translator]
# Translation provider (currently only "gemini" is supported)
provider = "gemini"

# Gemini model to use
model = "gemini-2.5-flash-lite"

# Number of strings per API call
batch_size = 100

# Sampling temperature (0.0–2.0; lower = more deterministic)
temperature = 0.3

# Maximum retry attempts for failed requests
max_retries = 3

# Custom translation instructions
# Example: "Do not translate proper names. Do not translate the word 'Water'"
# custom_instructions = "Do not translate proper names"

# Automatically extract and use app context from fastlane metadata or Xcode projects
use_app_context = true

# Thinking budget for translation.
# Supported by Gemini 2.5 Pro/Flash and thinking-exp models.
# NOT supported by Gemini 2.5 Flash-Lite or 1.5 series.
# Levels: "minimal", "low", "medium", "high" or "0" (disabled).
thinking_level = "0"

[translator.screenshots]
# Gemini model for screenshot text generation and translation
model = "gemini-3-flash-preview"

# Sampling temperature (0.0–2.0; higher = more creative)
temperature = 1.0

# Thinking budget: "minimal", "low", "medium", "high"
thinking_level = "low"

# Number of screenshot texts per batch API call (1–50)
batch_size = 50
"""

    config_path.write_text(default_content)
    return config_path
