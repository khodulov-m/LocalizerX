# LocalizerX

CLI tool for automatic translation of Xcode String Catalogs (`.xcstrings`), App Store metadata, Chrome Extension messages, frontend i18n JSON files, and Android `strings.xml` using Gemini API.

## Features

- Translate `.xcstrings` files to multiple languages with a single command
- Translate fastlane App Store metadata (name, subtitle, description, keywords, etc.)
- Generate App Store screenshot texts using AI with app context from fastlane metadata
- Translate App Store screenshot texts with ASO-optimized, marketing-focused prompts
- Translate Chrome Extension `_locales/` message files with SEO-optimized prompts
- Translate frontend i18n JSON files (Vue.js, React i18next, Angular, etc.)
- Translate Android `res/values/strings.xml` files (strings, string-arrays, plurals)
- Preserve placeholders (`%@`, `%d`, `{name}`, `{{name}}`, `{0}`, `$PLACEHOLDER$`, `$1`) during translation
- Support for pluralization and declension forms
- Use developer comments for translation context
- SQLite caching to reduce API calls
- Optional backups before changes (`--backup`)

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
default_targets = [
    "ru", "fr-FR", "pt-BR", "es-MX", "it", "ja", "pl", "no",
    "de-DE", "nl-NL", "ko", "da", "sk", "sv", "ro", "uk",
    "hi", "he", "hr", "zh-Hans", "zh-Hant", "fi", "th", "vi",
    "en-GB", "ms", "id", "tr",
]

[translator]
model = "gemini-2.5-flash-lite"
batch_size = 100
temperature = 0.3
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
| `--backup` | `-b` | Create backup before writing changes |
| `--batch-size` | | Strings per API call (1-100, default: 100) |
| `--model` | `-m` | Gemini model to use |
| `--temperature` | `-T` | Sampling temperature (0.0–2.0). Lower = more deterministic. |
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
| `--backup` | `-b` | Create backup before writing changes |
| `--model` | `-m` | Gemini model to use |
| `--temperature` | `-T` | Sampling temperature (0.0–2.0). Lower = more deterministic. |

### Check Metadata Character Limits & ASO Optimization

Validate that your App Store metadata fields comply with Apple's character limits and check for ASO optimization issues:

```bash
# Check all fields in all locales
localizerx metadata-check

# Check specific locale
localizerx metadata-check --locale de-DE

# Check specific field
localizerx metadata-check --field subtitle

# Check specific field in specific locale
localizerx metadata-check --locale en-US --field name

# Specify metadata directory
localizerx metadata-check ./fastlane/metadata

# Skip duplicate word check (only check character limits)
localizerx metadata-check --skip-duplicates
```

**Character Limits:**
- Name: 30 characters
- Subtitle: 30 characters
- Keywords: 100 characters
- Description: 4,000 characters
- Promotional text: 170 characters
- Release notes: 4,000 characters

**ASO Optimization - Duplicate Word Detection:**

The command also checks for duplicate words between `name`, `subtitle`, and `keywords` fields. Apple indexes words from all three fields, so repeating the same word wastes valuable character space.

Example output:
```
✓ All fields are within character limits

⚠ Found 2 duplicate word issue(s) (ASO optimization)

           Duplicate Words (ASO)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Locale       ┃ Fields              ┃ Duplicated Words ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ en-US        │ name → keywords     │ photo, editor    │
│ en-US        │ subtitle → keywords │ photo            │
└──────────────┴─────────────────────┴──────────────────┘
```

Common stop words (a, the, and, etc.) are automatically excluded from duplicate detection.

**Exit Codes:**
- `0` - All fields are within limits (duplicate warnings don't affect exit code)
- `1` - One or more fields exceed character limits (useful for CI/CD)

### Metadata Check Options

| Option | Short | Description |
|--------|-------|-------------|
| `--locale` | `-l` | Check specific locale only (default: all locales) |
| `--field` | `-f` | Check specific field only (e.g., `name`, `subtitle`, `keywords`) |
| `--skip-duplicates` | | Skip duplicate word check between name/subtitle/keywords |

### Translate App Store Screenshot Texts

Translate marketing texts displayed on App Store screenshots. Texts are ASO-optimized with a 5-word limit for maximum impact.

```bash
# Create a template (if screenshots/texts.json doesn't exist)
localizerx screenshots

# Translate to specific languages
localizerx screenshots --to de,fr,es

# Use default_targets from config (if --to is omitted)
localizerx screenshots

# Specify source language
localizerx screenshots --src ru --to en,de

# Dry run to see what would be translated
localizerx screenshots --to de --dry-run
```

**JSON Structure (`screenshots/texts.json`):**
```json
{
  "sourceLanguage": "en",
  "screens": {
    "screen_1": {
      "headline": { "small": "Track Habits", "large": "Track Your Daily Habits" },
      "subtitle": { "small": "Stay motivated", "large": "Stay motivated every day" }
    },
    "screen_2": {
      "headline": { "small": "Set Goals", "large": "Set Personal Goals" }
    }
  },
  "localizations": {
    "de": {
      "screen_1": {
        "headline": { "small": "Gewohnheiten tracken", "large": "Tägliche Gewohnheiten" }
      }
    }
  }
}
```

**Text Types:** `headline`, `subtitle`, `button`, `caption`, `callout`

**Device Classes:** `small` (iPhone SE, compact), `large` (iPad, Pro Max)

### Screenshots Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to` | `-t` | Target languages (comma-separated). Uses `default_targets` from config if omitted. |
| `--src` | `-s` | Source language (default: from file or `en`) |
| `--dry-run` | `-n` | Show what would be translated without changes |
| `--preview` | `-p` | Preview translations before applying |
| `--overwrite` | | Overwrite existing translations |
| `--backup` | `-b` | Create backup before writing changes |
| `--model` | `-m` | Gemini model to use |

**Key Features:**
- ASO-optimized prompts (not literal translation, but market adaptation)
- Maximum 5 words per text (hard limit for screenshot readability)
- Device-aware translation (small = extra short, large = slightly more descriptive)
- Auto-generates template if `screenshots/texts.json` doesn't exist
- Lossless round-trip (preserves JSON structure)

### Generate App Store Screenshot Texts

Automatically generate marketing-optimized screenshot texts using AI. The command reads your app context from fastlane/metadata (app name, subtitle, description) to generate relevant, on-brand copy.

```bash
# Interactive mode - prompts for screen descriptions
localizerx screenshots-generate

# From hints file (JSON with screen descriptions)
localizerx screenshots-generate --hints hints.json

# Generate only headlines (default: headline,subtitle)
localizerx screenshots-generate --text-types headline

# Preview generated texts before saving
localizerx screenshots-generate --preview

# Dry run - show prompts without API calls
localizerx screenshots-generate --dry-run

# Overwrite existing texts
localizerx screenshots-generate --overwrite
```

**Interactive Mode:**

When run without `--hints`, the command enters interactive mode:

```
$ localizerx screenshots-generate

Reading app context from fastlane/metadata/en-US...
  App: MyApp
  Subtitle: Track your habits daily

Screen 1 ID [screen_1]:
  Description (what does this screen show?): Main dashboard showing daily progress

Screen 2 ID [screen_2]:
  Description (what does this screen show?): Detailed statistics and charts

Generating texts...
```

**Hints File Format (`hints.json`):**

```json
{
  "screen_1": "Main dashboard showing daily progress tracking",
  "screen_2": "Settings page with customization options",
  "screen_3": "Achievement system and rewards"
}
```

### Screenshots Generate Options

| Option | Short | Description |
|--------|-------|-------------|
| `--hints` | | Path to JSON file with screen descriptions |
| `--metadata` | | Path to fastlane/metadata (auto-detected if omitted) |
| `--text-types` | | Text types to generate (comma-separated, default: `headline,subtitle`) |
| `--src` | `-s` | Source language for generated texts (default: `en`) |
| `--dry-run` | `-n` | Show prompts without making API calls |
| `--preview` | `-p` | Preview generated texts before saving |
| `--overwrite` | | Overwrite existing source texts |
| `--backup` | `-b` | Create backup before writing changes |
| `--model` | `-m` | Gemini model to use |

**Key Features:**
- Reads app context from fastlane/metadata for relevant generation
- ASO-optimized prompts (marketing-focused, benefit-oriented)
- Maximum 5 words per text (hard limit)
- Device-aware generation (small = extra concise, large = slightly more descriptive)
- Interactive mode or batch mode via hints file
- Generates both `small` and `large` variants for each text type

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
| `--backup` | `-b` | Create backup before writing changes |
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
| `--backup` | `-b` | Create backup before writing changes |
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
| `--backup` | `-b` | Create backup before writing changes |
| `--batch-size` | | Strings per API call (1-100) |
| `--model` | `-m` | Gemini model to use |

### View File Information

```bash
# xcstrings file info
localizerx info Localizable.xcstrings

# Fastlane metadata info
localizerx metadata-info
localizerx metadata-info ./fastlane/metadata

# Screenshot texts info
localizerx screenshots-info
localizerx screenshots-info ./screenshots/texts.json

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

Displays statistics: string count, languages, translation coverage, character/word limits.

### List Available Models

```bash
localizerx models
```

### List Supported Languages

```bash
localizerx languages
```

### Clear Translation Cache

Delete the local SQLite translation cache:

```bash
localizerx cache-clear

# Use a specific config file to locate the cache
localizerx cache-clear --config ./config.toml
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

### Screenshot Texts Generation

```bash
# Generate texts interactively (prompts for screen descriptions)
localizerx screenshots-generate

# Generate from a hints file with screen descriptions
localizerx screenshots-generate --hints hints.json

# Generate only headlines
localizerx screenshots-generate --text-types headline

# Preview before saving
localizerx screenshots-generate --preview

# Dry run to see the prompts
localizerx screenshots-generate --dry-run
```

### Screenshot Texts Translation

```bash
# Create template first time (if file doesn't exist)
localizerx screenshots

# Then edit screenshots/texts.json and translate
localizerx screenshots --to de,fr,ja

# Preview translations before applying
localizerx screenshots --to es --preview

# Overwrite existing translations
localizerx screenshots --to de --overwrite
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
