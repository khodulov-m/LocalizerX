# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalizerX (or `lrx` for short) is a Python CLI tool for macOS that automates translation of Xcode String Catalogs (`.xcstrings` files), App Store metadata, App Store screenshot texts, Chrome Extension `_locales/` message files, Android `strings.xml`, and frontend i18n JSON files using Google's Gemini API. It handles placeholder preservation, pluralization rules, and developer comments while translating localization files across all supported platforms.

## AI Agent Skills

This repository includes an Agent Skill located at `skills/localizerx/SKILL.md` that enables Claude Code and other compatible AI agents to easily use the `localizerx` CLI tool for automating translation tasks across the project. Use the skill instructions when tasked with localization.

## Development Commands

```bash
# Linting
ruff check .

# Formatting
black .

# Testing
uv run python -m pytest

# Run single test
uv run python -m pytest tests/test_file.py::test_function

# Install locally (editable)
pip install -e ".[dev]"

# Run CLI
localizerx translate <path> --to fr,es,de --src en

# Remove languages
localizerx translate <path> --remove fr,de,it
localizerx android --remove fr,es

# Translate with custom instructions
localizerx translate <path> --to fr,es,de --custom-prompt "Do not translate proper names. Do not translate the word 'Water'"

# Run delete command
localizerx delete fr,de --backup
localizerx delete --all --yes
localizerx delete ru --keep

# Utility commands
localizerx list              # List available Gemini models
localizerx use gemini-2.5-flash-lite  # Set active model in config
localizerx languages         # List supported locale codes
localizerx cache-clear       # Clear SQLite translation cache
```

## Architecture

The project follows Clean Architecture. Business logic is isolated from the CLI framework; orchestration happens in Use Cases, which depend on abstract Ports.

```
CLI (Typer)  [localizerx/cli/]
 └─ Use Cases  [localizerx/core/use_cases/]
     └─ Ports (abstract)  [localizerx/core/ports/]
         └─ Adapters (concrete)  [localizerx/adapters/]
             └─ I/O handlers  [localizerx/io/]
             └─ Gemini API Adapter  [localizerx/translator/gemini_adapter.py]
                 └─ Post-processing (placeholders, plurals)
```

### Package Structure

- `localizerx/cli/` - Typer-based CLI commands (one module per format/command group)
  - `translate.py` - `.xcstrings` translation and `info` command
  - `delete.py` - Delete languages from `.xcstrings` files
  - `metadata.py` - App Store metadata + `metadata-info`, `metadata-check`, `metadata-urls`
  - `android.py` - Android `strings.xml` + `android-info`
  - `chrome.py` - Chrome Extension `_locales/` + `chrome-info`
  - `i18n.py` - Frontend i18n JSON + `i18n-info`
  - `screenshots.py` - Screenshot texts: translate, generate, info
  - `frameit.py` - Fastlane Frameit title/keyword strings
  - `agent.py` - `init-agent` command
- `localizerx/core/use_cases/` - Format-specific translation orchestrators (framework-agnostic)
- `localizerx/core/ports/repository.py` - Abstract cache/repository interface
- `localizerx/adapters/repository.py` - SQLite cache implementation
- `localizerx/config.py` - Configuration management (TOML)
- `localizerx/io/` - Lossless file I/O per format
  - `xcstrings.py`, `extension.py`, `screenshots.py`, `android.py`, `frameit.py`, `i18n.py`, `metadata.py`
- `localizerx/parser/` - Domain entities and Pydantic data models
  - `model.py` - `Entry`, `Translation` (xcstrings)
  - `extension_model.py` - `ExtensionMessage`, `ExtensionCatalog`
  - `screenshots_model.py` - `ScreenshotsCatalog`, `ScreenshotScreen`, `ScreenshotText`
  - `android_model.py` - `AndroidString`, `AndroidPlural`, `AndroidCatalog`
  - `frameit_model.py` - `FrameitString`, `FrameitCatalog`
  - `i18n_model.py` - `I18nMessage`, `I18nCatalog`
  - `metadata_model.py` - `MetadataField`, `MetadataCatalog`, `MetadataFieldType`
  - `app_context.py` - `AppContext` data class for screenshot text generation
- `localizerx/translator/base.py` - Abstract translator interface
- `localizerx/translator/gemini_adapter.py` - Gemini API implementation (async)
- `localizerx/translator/extension_prompts.py` - SEO-optimized prompts for Chrome Web Store fields
- `localizerx/translator/metadata_prompts.py` - ASO-optimized prompts for App Store metadata
- `localizerx/translator/frameit_prompts.py` - Prompts for Frameit title/keyword strings
- `localizerx/translator/screenshots_prompts.py` - ASO-optimized prompts for screenshot text translation
- `localizerx/translator/screenshots_generation_prompts.py` - ASO-optimized prompts for screenshot text generation
- `localizerx/utils/placeholders.py` - Placeholder masking/unmasking (%@, %d, {name}, $NAME$, $1)
- `localizerx/utils/locale.py` - Language/locale mapping
- `localizerx/utils/limits.py` - Character limit validation (App Store + Chrome Web Store)
- `localizerx/utils/context.py` - App context extraction (from metadata, workspace, project)

### Key Design Principles

- **Lossless parsing**: `read → write` must preserve structure exactly, only adding translations
- **Translator abstraction**: Provider-agnostic interface allows swapping Gemini for other APIs
- **Placeholder masking**: Mask placeholders before translation (`%@` → `__PH_1__`, `$NAME$` → `__PH_1__`), restore after
- **SQLite caching**: Key is `(src_lang, tgt_lang, text_hash)` to avoid redundant API calls
- **Custom instructions**: Support for custom translation rules via `--custom-prompt` CLI option or `custom_instructions` config field

### Data Models

```python
# xcstrings
Entry:
  key: str
  source_text: str
  comment: str | None
  translations: dict[lang, Translation]

Translation:
  value: str
  variations: dict | None  # for plural/gender forms

# Chrome Extension
ExtensionMessage:
  key: str
  message: str
  description: str | None
  placeholders: dict | None

ExtensionCatalog:
  source_locale: str
  locales: dict[str, ExtensionLocale]

# Screenshots
ScreenshotText:
  small: str | None  # for compact devices (iPhone SE)
  large: str | None  # for large devices (iPad, Pro Max)

ScreenshotScreen:
  texts: dict[ScreenshotTextType, ScreenshotText]

ScreenshotsCatalog:
  source_language: str
  screens: dict[str, ScreenshotScreen]
  localizations: dict[str, ScreenshotLocale]

# Android
AndroidString:
  name: str
  value: str
  translatable: bool

AndroidPlural:
  name: str
  items: dict[str, str]  # quantity → string

AndroidCatalog:
  source_language: str
  strings: list[AndroidString]
  arrays: list[AndroidStringArray]
  plurals: list[AndroidPlural]

# Frontend i18n
I18nMessage:
  key: str
  value: str

I18nCatalog:
  source_locale: str
  locales: dict[str, I18nLocale]

# Fastlane metadata
MetadataField:
  field_type: MetadataFieldType
  value: str

MetadataCatalog:
  source_language: str
  locales: dict[str, LocaleMetadata]

# Frameit
FrameitString:
  key: str
  value: str

FrameitCatalog:
  source_language: str
  locales: dict[str, FrameitLocale]

# App context (for screenshot generation)
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
