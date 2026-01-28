# LocalizerX

CLI tool for automatic translation of Xcode String Catalogs (`.xcstrings`), App Store metadata, Chrome Extension messages, frontend i18n JSON files, and Android `strings.xml` using Gemini API.

## Features

- Translate `.xcstrings` files to multiple languages with a single command
- Translate fastlane App Store metadata (name, subtitle, description, keywords, etc.)
- Translate Chrome Extension `_locales/` message files with SEO-optimized prompts
- Translate frontend i18n JSON files (Vue.js, React i18next, Angular, etc.)
- Translate Android `res/values/strings.xml` files (strings, string-arrays, plurals)
- Preserve placeholders (`%@`, `%d`, `{name}`, `{{name}}`, `{0}`, `$PLACEHOLDER$`, `$1`) during translation
- Support for pluralization and declension forms
- Use developer comments for translation context
- SQLite caching to reduce API calls
- Automatic backups before changes

## Installation

### Requirements

- macOS
- Python 3.10+
- Gemini API key

### Via pipx (recommended)

```bash
# Install pipx if not already installed
brew install pipx
pipx ensurepath

# Install LocalizerX
pipx install localizerx
```

### From source

```bash
# Clone the repository
git clone https://github.com/localizerx/localizerx.git
cd localizerx

# Install globally
pipx install .

# Or for development (changes apply immediately)
pipx install -e .
```

### Via pip

```bash
pip install localizerx
```

## Setup

### API Key

Set the environment variable with your Gemini API key:

```bash
export GEMINI_API_KEY="your-api-key"
```

For permanent use, add to `~/.zshrc` or `~/.bashrc`:

```bash
echo 'export GEMINI_API_KEY="your-api-key"' >> ~/.zshrc
```

### Configuration File

Create a configuration file:

```bash
localizerx init
```

Config is created at `~/.config/localizerx/config.toml`:

```toml
# Source language for translations
source_language = "en"

# Default target languages (used when --to is omitted)
default_targets = ["ru", "fr", "pt-BR", "es-MX", "it", "ja", "pl", "no", "de-DE", "nl", "ko", "da", "sv", "ro"]

[translator]
model = "gemini-2.5-flash-lite"
batch_size = 100
max_retries = 3

cache_enabled = true
```

## Usage

### Quick Translation

```bash
# Translate to all default languages (from config)
localizerx translate

# Translate to specific languages
localizerx --to fr,es,de

# Same as above, explicit command
localizerx translate --to fr,es,de
```

### Translate xcstrings Files

```bash
# Translate specific file
localizerx translate Localizable.xcstrings --to fr,es,de

# Specify source language (default is English)
localizerx translate Localizable.xcstrings --to ru --src en

# Translate all .xcstrings in a directory
localizerx translate ./MyApp --to fr,es,de
```

### Translate Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to` | `-t` | Target languages (comma-separated). Omit to use `default_targets` from config. |
| `--src` | `-s` | Source language (default: `en`) |
| `--dry-run` | `-n` | Show what would be translated without changes |
| `--preview` | `-p` | Preview translations before applying |
| `--overwrite` | | Overwrite existing translations |
| `--no-backup` | | Don't create backup before changes |
| `--batch-size` | | Strings per API call (1-100, default: 100) |
| `--model` | `-m` | Gemini model to use |
| `--config` | `-c` | Path to configuration file |

### Translate App Store Metadata

Translate fastlane metadata files:

```bash
# Translate metadata to German and French
localizerx metadata --to de-DE,fr-FR

# Specify source locale
localizerx metadata --to ja --src en-US

# Translate specific fields only
localizerx metadata --to es-ES --fields name,subtitle,keywords

# Handle character limit violations
localizerx metadata --to de-DE --on-limit truncate
```

### Metadata Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to` | `-t` | Target locales (comma-separated, e.g., `de-DE,fr-FR`) |
| `--src` | `-s` | Source locale (default: `en-US`) |
| `--fields` | `-f` | Fields to translate (comma-separated) |
| `--on-limit` | | Action when exceeding character limit: `warn`, `truncate`, `error` |
| `--dry-run` | `-n` | Show what would be translated without changes |
| `--preview` | `-p` | Preview translations before applying |
| `--overwrite` | | Overwrite existing translations |
| `--no-backup` | | Don't create backup before changes |
| `--model` | `-m` | Gemini model to use |

### Translate Chrome Extension Messages

Translate Chrome Extension `_locales/` message files:

```bash
# Translate messages to French and German
localizerx chrome --to fr,de

# Translate specific message keys only
localizerx chrome --to ja --keys appName,appDesc,shortName

# Handle character limit violations for Chrome Web Store fields
localizerx chrome --to pt-BR --on-limit truncate

# Accept hyphenated locales (auto-converted to underscore format)
localizerx chrome --to pt-BR,zh-CN  # Creates pt_BR/ and zh_CN/
```

### Chrome Extension Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to` | `-t` | Target locales (comma-separated, e.g., `fr,de,pt-BR`). Hyphens auto-converted to underscores. |
| `--src` | `-s` | Source locale (default: `en`) |
| `--keys` | `-k` | Filter specific message keys (comma-separated) |
| `--on-limit` | | Action when CWS field exceeds character limit: `warn`, `truncate`, `error` |
| `--dry-run` | `-n` | Show what would be translated without changes |
| `--preview` | `-p` | Preview translations before applying |
| `--overwrite` | | Overwrite existing translations |
| `--no-backup` | | Don't create backup before changes |
| `--model` | `-m` | Gemini model to use |

**Key Features:**
- SEO-optimized prompts for Chrome Web Store fields (`appName`, `shortName`, `appDesc`)
- Character limit enforcement: `appName` (75 chars), `shortName` (12 chars), `appDesc` (132 chars)
- Preserves `description` and `placeholders` fields losslessly
- Supports Chrome placeholder syntax (`$PLACEHOLDER_NAME$`, `$1`)

**Expected Directory Structure:**
```
_locales/
├── en/
│   └── messages.json
├── fr/
│   └── messages.json
└── ...
```

### Translate Frontend i18n JSON Files

Translate JSON-based i18n files used by Vue.js, React i18next, Angular, and other frameworks:

```bash
# Translate to French and German
localizerx i18n --to fr,de

# Specify path to locales directory
localizerx i18n ./src/locales --to es,ja

# Dry run to see what would be translated
localizerx i18n --to fr --dry-run
```

**Supported Layouts:**
- Flat files: `locales/en.json`, `locales/fr.json`
- Directory-per-locale: `locales/en/translation.json`

Nested JSON structures are preserved losslessly (e.g., `{"common": {"ok": "OK"}}`).

**Auto-detected directories:** `locales/`, `src/locales/`, `i18n/`, `src/i18n/`, `public/locales/`, `lang/`

### i18n Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to` | `-t` | Target locales (comma-separated, e.g., `fr,es,de`) |
| `--src` | `-s` | Source locale (default: `en`) |
| `--dry-run` | `-n` | Show what would be translated without changes |
| `--preview` | `-p` | Preview translations before applying |
| `--overwrite` | | Overwrite existing translations |
| `--no-backup` | | Don't create backup before changes |
| `--batch-size` | | Strings per API call (1-100) |
| `--model` | `-m` | Gemini model to use |

### Translate Android strings.xml

Translate Android string resources from `res/` directories:

```bash
# Translate strings to French and German
localizerx android --to fr,de

# Include string-arrays and plurals
localizerx android --to ja --include-arrays --include-plurals

# Specify path to res/ directory
localizerx android ./app/src/main/res --to es,pt-BR
```

**Supported resources:** `<string>`, `<string-array>`, `<plurals>`

Respects `translatable="false"` attributes. Handles Android locale directory naming (`values-pt-rBR`, `values-b+zh+Hans`).

**Auto-detected directories:** `res/`, `app/src/main/res/`, `src/main/res/`

### Android Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to` | `-t` | Target locales (comma-separated, e.g., `fr,es,de,pt-BR`) |
| `--src` | `-s` | Source locale (default: `en`) |
| `--include-arrays` | | Also translate `<string-array>` resources |
| `--include-plurals` | | Also translate `<plurals>` resources |
| `--dry-run` | `-n` | Show what would be translated without changes |
| `--preview` | `-p` | Preview translations before applying |
| `--overwrite` | | Overwrite existing translations |
| `--no-backup` | | Don't create backup before changes |
| `--batch-size` | | Strings per API call (1-100) |
| `--model` | `-m` | Gemini model to use |

### View File Information

```bash
# xcstrings file info
localizerx info Localizable.xcstrings

# Fastlane metadata info
localizerx metadata-info
localizerx metadata-info ./fastlane/metadata

# Chrome Extension messages info
localizerx chrome-info
localizerx chrome-info ./_locales

# Frontend i18n info
localizerx i18n-info
localizerx i18n-info ./src/locales

# Android resources info
localizerx android-info
localizerx android-info ./app/src/main/res
```

Displays statistics: string count, languages, translation coverage, character limits.

### List Available Models

```bash
localizerx models
```

### List Supported Languages

```bash
localizerx languages
```

### Check Version

```bash
localizerx --version
```

## Examples

### Dry Run

```bash
localizerx translate App.xcstrings --to fr,de --dry-run
```

### Translation with Preview

```bash
localizerx translate App.xcstrings --to ja --preview
```

Shows a table of translations and asks for confirmation before saving.

### Overwrite Existing Translations

```bash
localizerx translate App.xcstrings --to es --overwrite
```

### Use a Specific Model

```bash
localizerx translate App.xcstrings --to ru --model gemini-2.0-flash
```

### Batch Process a Project

```bash
localizerx translate ~/Projects/MyApp --to fr,es,de,ja,ko,zh-Hans
```

Finds and translates all `.xcstrings` files in the directory.

### App Store Metadata Translation

```bash
# Translate all metadata fields
localizerx metadata --to de-DE,fr-FR,ja

# Translate only keywords with truncation if over limit
localizerx metadata --to es-ES --fields keywords --on-limit truncate
```

### Chrome Extension Translation

```bash
# Translate all messages to multiple locales
localizerx chrome --to fr,de,pt-BR,zh-CN

# Translate specific message keys only
localizerx chrome --to ja --keys appName,appDesc

# Preview translations before applying
localizerx chrome --to es --preview

# Truncate Chrome Web Store fields if they exceed character limits
localizerx chrome --to de --on-limit truncate
```

### Frontend i18n Translation

```bash
# Translate all i18n keys
localizerx i18n --to fr,de,ja

# Preview before applying
localizerx i18n --to es --preview
```

### Android Translation

```bash
# Translate strings only
localizerx android --to fr,de,pt-BR

# Translate strings, arrays, and plurals
localizerx android --to ja --include-arrays --include-plurals

# Overwrite existing translations
localizerx android --to es --overwrite
```

## Development

```bash
# Clone and install dependencies
git clone https://github.com/localizerx/localizerx.git
cd localizerx
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Linting
ruff check .

# Formatting
black .

# Tests
pytest
```

## License

MIT
