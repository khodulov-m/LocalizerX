# LocalizerX

CLI tool for automatic translation of Xcode String Catalogs (`.xcstrings`) and App Store metadata using Gemini API.

## Features

- Translate `.xcstrings` files to multiple languages with a single command
- Translate fastlane App Store metadata (name, subtitle, description, keywords, etc.)
- Preserve placeholders (`%@`, `%d`, `{name}`) during translation
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

### View File Information

```bash
# xcstrings file info
localizerx info Localizable.xcstrings

# Fastlane metadata info
localizerx metadata-info
localizerx metadata-info ./fastlane/metadata
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
