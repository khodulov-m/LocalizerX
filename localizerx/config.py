"""Configuration management for LocalizerX."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from typing import Literal

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "localizerx" / "config.toml"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "localizerx"

# Available Gemini models
GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

DEFAULT_MODEL = "gemini-2.5-flash-lite"


class TranslatorConfig(BaseModel):
    """Configuration for translation provider."""

    provider: str = "gemini"
    model: str = DEFAULT_MODEL
    batch_size: int = Field(default=20, ge=1, le=50)
    max_retries: int = Field(default=3, ge=1, le=10)


class Config(BaseModel):
    """Main configuration for LocalizerX."""

    source_language: str = "en"
    concurrency: int = Field(default=5, ge=1, le=20)
    backup_enabled: bool = True
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

    default_content = '''# LocalizerX Configuration

# Source language for translations (default: en)
source_language = "en"

# Number of concurrent translation requests
concurrency = 5

# Create backup before writing changes
backup_enabled = true

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
batch_size = 20

# Maximum retry attempts for failed requests
max_retries = 3
'''

    config_path.write_text(default_content)
    return config_path
