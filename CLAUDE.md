# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalizerX is a Python CLI tool for macOS that automates translation of Xcode String Catalogs (`.xcstrings` files), App Store metadata, and Chrome Extension `_locales/` message files using Google's Gemini API. It handles placeholder preservation, pluralization rules, and developer comments while translating iOS localization files and Chrome Extension messages.

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
- `localizerx/config.py` - Configuration management (TOML)
- `localizerx/io/xcstrings.py` - Lossless xcstrings file I/O
- `localizerx/io/extension.py` - Chrome Extension _locales/ I/O
- `localizerx/parser/model.py` - Entry and Translation data models
- `localizerx/parser/extension_model.py` - Chrome Extension message and catalog data models
- `localizerx/translator/base.py` - Abstract translator interface
- `localizerx/translator/gemini_adapter.py` - Gemini API implementation (async)
- `localizerx/translator/extension_prompts.py` - SEO-optimized prompts for Chrome Web Store fields
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
```

## Environment Variables

- `GEMINI_API_KEY` - Required for translation API access

## Configuration

User config location: `~/.config/localizerx/config.toml`
