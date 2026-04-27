---
name: use-localizerx
description: Translates iOS String Catalogs (.xcstrings), Android strings.xml, frontend i18n JSON files, App Store metadata, screenshots texts, and Chrome Extension _locales/ using the LocalizerX (lrx) CLI tool. Use when you need to translate localization or marketing files.
---

# LocalizerX (lrx) Skill Guide

`LocalizerX` (or `lrx`) is a CLI tool designed to automate localization using the Google Gemini API. It handles diverse formats while ensuring lossless parsing and placeholder safety.

## Quick Start & Configuration

```bash
# Initialize a default configuration file (~/.config/localizerx/config.toml)
lrx init

# List available Gemini models
lrx list

# Set the active model and thinking level
lrx use gemini-2.5-flash-lite

# List supported language/locale codes
lrx languages
```

## Translation Commands

All translation commands support global options like `--to`, `--src`, `--dry-run`, `--preview`, and `--custom-prompt`.

### iOS String Catalogs (`.xcstrings`)

Translates `.xcstrings` files, preserving pluralization and metadata.

```bash
# Translate to specific languages
lrx translate <path> --to fr,es,de --src en

# Show info about a catalog (total keys, languages, missing translations)
lrx info Localizable.xcstrings

# Delete languages from a catalog
lrx delete Localizable.xcstrings fr,de --backup
```

### App Store Metadata (Fastlane)

Translates App Store metadata text files (`name.txt`, `subtitle.txt`, etc.). Automatically detects both iOS (`fastlane/metadata`) and macOS (`fastlane/metadata_macos`) directories. The `keywords` field is localized as ASO research using full app context (name, subtitle, description) — the model picks locale-appropriate search terms rather than translating word-by-word.

```bash
# Translate metadata
lrx metadata --to fr-FR,de-DE

# Show info about metadata files
lrx metadata-info

# Check metadata for character limits and ASO optimization
lrx metadata-check

# Batch set URLs across all locales
lrx metadata-urls --marketing <url> --privacy <url> --support <url>
```

### Android & Web Platforms

#### Android Strings
```bash
# Translate Android strings.xml (auto-detects res/ directory)
lrx android --to es,pt-BR --include-plurals --include-arrays

# Show info about Android string resources
lrx android-info
```

#### Frontend i18n (JSON)
```bash
# Translate JSON i18n files and optionally update index.ts imports
lrx i18n --to fr,de,it --index

# Show info about i18n files
lrx i18n-info
```

#### Chrome Extension
```bash
# Translate _locales/ message files
lrx chrome --to ja,ko,zh-CN

# Show info about Chrome Extension locales
lrx chrome-info
```

### Screenshots & Marketing

#### Generate & Translate Screenshot Texts
```bash
# Automatically generate 5 sets of marketing headlines/subtitles from metadata context
lrx screenshots-generate --auto 5 --preview

# Show info about screenshot texts file
lrx screenshots-info

# Translate generated screenshots/texts.json to target languages
lrx screenshots --to fr,de

# Translate fastlane Frameit title/keyword strings
lrx frameit --to es,pt-BR
```

## Advanced Usage & Options

### Global Options
- `--to`, `-t`: Target languages (e.g., `fr,es,de`).
- `--src`, `-s`: Source language (default: `en`).
- `--dry-run`, `-n`: Show what would be translated without modifying files.
- `--preview`, `-p`: Show proposed translations and wait for confirmation.
- `--overwrite`: Overwrite existing translations (use with caution).
- `--custom-prompt`, `--instructions`: Add specific context (e.g., "Keep brand names in English").
- `--backup`, `-b`: Create a `.bak` file before writing changes.
- `--batch-size`: Control number of strings per API call (1-100).
- `--no-app-context`: Disable automatic extraction of app context from project files.
- `--mark-empty`: Mark empty/whitespace strings as translated to avoid re-translation.

### Environment & Safety
- **`GEMINI_API_KEY`**: Must be set in the environment.
- **Cache**: Local SQLite cache prevents redundant API calls. Use `lrx cache-clear` to reset.
- **Placeholders**: The tool automatically masks variables (e.g., `%@`, `{name}`, `$1`), HTML/CDATA markup in Android `strings.xml`, escape sequences (`\n`, `\t`, `\u00A0`, …), and Markdown link URLs so they are not corrupted during translation.
- **Plurals**: For `.xcstrings` and Android `<plurals>`, the translator is CLDR-aware — it expands source forms (e.g., English `one`/`other`) into the full set of categories required by the target language (Russian `one`/`few`/`many`/`other`, Arabic six forms, etc.) in a single API call.
