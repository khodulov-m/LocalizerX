# LocalizerX - Gemini Integration Guide

## Project Overview

LocalizerX (or `lrx` for short) is a Python-based CLI tool designed to automate the translation of various software localization and metadata formats using the Google Gemini API. It targets macOS users and runs on Python 3.10+.

### Core Capabilities
- Translates Xcode String Catalogs (`.xcstrings`), Android `strings.xml`, frontend i18n JSON files, and Chrome Extension `_locales` messages.
- Translates and manages App Store metadata (via fastlane formats), app screenshot marketing texts, and Fastlane Frameit titles/keywords.
- Handles complex localization nuances like pluralization, declension forms, and developer comments.
- **Key Design Principles:**
  - **Lossless Parsing:** Ensure the structure of localization files is preserved exactly; only translations are added.
  - **Placeholder Masking:** Variables (like `%@`, `%d`, `{name}`, `$1`) are safely masked prior to translation and unmasked afterward to prevent corruption.
  - **Caching:** Uses a local SQLite cache to prevent redundant API calls for previously translated strings.
  - **Customization:** Supports custom translation instructions per run or globally via config.

## Technology Stack

- **Language:** Python (3.10+)
- **CLI Framework:** Typer
- **HTTP Client:** HTTPX
- **Data Validation:** Pydantic
- **Formatting/Output:** Rich
- **LLM Provider:** Google Gemini API (via `gemini-3-flash-preview` by default)

## Development Conventions & Commands

This project uses standard Python tooling for linting, formatting, and testing.

### Setup and Installation
```bash
# Set up a virtual environment and install locally in editable mode with dev dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Formatting & Linting
- **Formatter:** Black
- **Linter:** Ruff

```bash
# Format code
black .

# Lint code
ruff check .
```

### Testing
- **Framework:** Pytest (with `pytest-asyncio` for async tests)

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_file.py

# Run a specific test function
pytest tests/test_file.py::test_function
```

## Architecture Map

- **`localizerx/cli/`**: Typer-based CLI command definitions (`translate.py`, `metadata.py`, `android.py`, `frameit.py`, etc.).
- **`localizerx/config.py`**: Configuration management using TOML (stored in `~/.config/localizerx/config.toml`).
- **`localizerx/io/`**: I/O handlers for various formats (e.g., `xcstrings.py`, `android.py`, `extension.py`, `frameit.py`). Ensures lossless parsing.
- **`localizerx/parser/`**: Pydantic data models for entries, translations, and specific app contexts (`model.py`, `metadata_model.py`, `frameit_model.py`, etc.).
- **`localizerx/translator/`**: Core translation logic. Contains the `gemini_adapter.py` for API interaction and domain-specific prompt templates (`extension_prompts.py`, `screenshots_prompts.py`, `frameit_prompts.py`).
- **`localizerx/utils/`**: Utilities for placeholder masking (`placeholders.py`), locale mapping (`locale.py`), and character limit enforcement (`limits.py`).
- **`tests/`**: Comprehensive test suite organized by module and functionality.

## Usage Environment Variables

- `GEMINI_API_KEY`: Required for translation operations.

## AI Assistant Guidelines

When modifying this codebase, please adhere to the following principles:
- **Preserve Data Integrity:** Modifications to I/O or parser code MUST guarantee lossless read/write cycles. Do not reformat the source JSON/XML unless strictly updating translations.
- **Respect Placeholders:** If modifying translation logic, ensure `localizerx.utils.placeholders` is utilized correctly to avoid breaking format strings.
- **Update Tests:** All new features or bug fixes must include corresponding Pytest coverage in the `tests/` directory.
- **Follow Formatting Rules:** Any newly generated Python code should be compatible with `black` (100 char line limit) and `ruff` configurations found in `pyproject.toml`.
