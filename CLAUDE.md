# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalizerX is a Python CLI tool for macOS that automates translation of Xcode String Catalogs (`.xcstrings` files), App Store metadata, App Store screenshot texts, and Chrome Extension `_locales/` message files using Google's Gemini API. It handles placeholder preservation, pluralization rules, and developer comments while translating iOS localization files and Chrome Extension messages.

## Development Commands

```bash
# Linting
ruff check .

# Formatting
black .

# Testing
pytest

# Run single test
pytest tests/test_file.py::test_function

# Install locally (editable)
pip install -e .

# Run CLI
localizerx translate <path> --to fr,es,de --src en

# Run delete command
localizerx delete fr,de --backup
localizerx delete --all --yes
localizerx delete ru --keep
```

## Architecture

```
CLI (Typer)
 └─ File Scanner
     └─ xcstrings Parser
         └─ Translation Queue
             └─ Gemini API Adapter
                 └─ Post-processing (placeholders, plurals)
                     └─ Writer + Backup
```

### Package Structure

- `localizerx/cli.py` - Typer-based CLI commands
- `localizerx/cli/delete.py` - Delete languages from xcstrings files
- `localizerx/config.py` - Configuration management (TOML)
- `localizerx/io/xcstrings.py` - Lossless xcstrings file I/O
- `localizerx/io/extension.py` - Chrome Extension _locales/ I/O
- `localizerx/io/screenshots.py` - App Store screenshot texts JSON I/O
- `localizerx/parser/model.py` - Entry and Translation data models
- `localizerx/parser/extension_model.py` - Chrome Extension message and catalog data models
- `localizerx/parser/screenshots_model.py` - Screenshot text data models (ScreenshotsCatalog, ScreenshotScreen, etc.)
- `localizerx/parser/app_context.py` - AppContext data class for screenshot text generation
- `localizerx/translator/base.py` - Abstract translator interface
- `localizerx/translator/gemini_adapter.py` - Gemini API implementation (async)
- `localizerx/translator/extension_prompts.py` - SEO-optimized prompts for Chrome Web Store fields
- `localizerx/translator/screenshots_prompts.py` - ASO-optimized prompts for screenshot text translation (5-word limit)
- `localizerx/translator/screenshots_generation_prompts.py` - ASO-optimized prompts for screenshot text generation
- `localizerx/utils/placeholders.py` - Placeholder masking/unmasking (%@, %d, {name}, $NAME$, $1)
- `localizerx/utils/locale.py` - Language/locale mapping
- `localizerx/utils/limits.py` - Character limit validation (App Store + Chrome Web Store)

### Key Design Principles

- **Lossless parsing**: `read → write` must preserve structure exactly, only adding translations
- **Translator abstraction**: Provider-agnostic interface allows swapping Gemini for other APIs
- **Placeholder masking**: Mask placeholders before translation (`%@` → `__PH_1__`, `$NAME$` → `__PH_1__`), restore after
- **SQLite caching**: Key is `(src_lang, tgt_lang, text_hash)` to avoid redundant API calls

### Data Models

```python
Entry:
  key: str
  source_text: str
  comment: str | None
  translations: dict[lang, Translation]

Translation:
  value: str
  variations: dict | None  # for plural/gender forms

ExtensionMessage:
  key: str
  message: str
  description: str | None
  placeholders: dict | None

ExtensionCatalog:
  source_locale: str
  locales: dict[str, ExtensionLocale]

ScreenshotText:
  small: str | None  # for compact devices (iPhone SE)
  large: str | None  # for large devices (iPad, Pro Max)

ScreenshotScreen:
  texts: dict[ScreenshotTextType, ScreenshotText]

ScreenshotsCatalog:
  source_language: str
  screens: dict[str, ScreenshotScreen]
  localizations: dict[str, ScreenshotLocale]

AppContext:
  name: str
  subtitle: str | None
  promo_text: str | None
  description: str | None
  keywords: list[str] | None
```

## Environment Variables

- `GEMINI_API_KEY` - Required for translation API access

## Configuration

User config location: `~/.config/localizerx/config.toml`
