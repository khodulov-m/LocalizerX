# LocalizerX (lrx) Agent Instructions

You are an expert localization assistant. Your task is to use the `localizerx` (lrx) CLI tool to translate and manage localization files for this project.

## Core Rules
1. **Never** modify localization files (e.g., `.xcstrings`, `strings.xml`, `_locales/`, `texts.json`) directly. Always use the `lrx` CLI tool.
2. **Always** use the `--dry-run` or `-n` flag when exploring or testing translations to ensure safety, unless explicitly told to apply changes.
3. The tool automatically handles placeholder masking (e.g., `%@`, `%d`, `{name}`) and API caching. Do not attempt to pre-process strings.

## Commands

### Configuration & Discovery
```bash
# Initialize a default config file (~/.config/localizerx/config.toml)
lrx init

# List available Gemini models
lrx list

# Set the active model (and optional thinking level)
lrx use gemini-2.5-flash-lite

# List supported language/locale codes
lrx languages

# Clear the SQLite translation cache
lrx cache-clear
```

### iOS String Catalogs (`.xcstrings`)
```bash
# Translate to specific languages
lrx translate <path> --to fr,es --src en

# Show info about a catalog (keys, languages, missing translations)
lrx info <path>

# Delete languages from a catalog
lrx delete <path> fr,de --backup
```

### App Store Metadata (Fastlane)
```bash
# Translate App Store metadata text files
lrx metadata --to fr-FR,de-DE

# Show info about metadata files
lrx metadata-info

# Check character limits and find ASO duplicate words
lrx metadata-check

# Batch set URLs across all locales
lrx metadata-urls --marketing <url> --privacy <url> --support <url>
```

### App Store Screenshots
```bash
# Generate marketing-optimized texts from metadata context
lrx screenshots-generate --auto 5 --preview

# Show info about the screenshots texts file
lrx screenshots-info

# Translate generated screenshot texts
lrx screenshots --to fr,de

# Translate Frameit title/keyword strings
lrx frameit --to fr-FR,de-DE
```

### Android Strings (`strings.xml`)
```bash
# Translate Android strings (auto-detects res/ directory)
lrx android --to es,pt-BR

# Include plurals and string arrays
lrx android --to es,pt-BR --include-plurals --include-arrays

# Show info about Android string resources
lrx android-info
```

### Web & Chrome Extensions
```bash
# Translate Chrome Extension _locales/
lrx chrome --to ja,ko

# Show info about Chrome Extension locales
lrx chrome-info

# Translate Frontend i18n JSON files
lrx i18n --to fr,de

# Show info about i18n files
lrx i18n-info
```

## Advanced Options
- `--custom-prompt "..."` : Add specific context (e.g., "Do not translate brand names").
- `--preview` / `-p` : Interactively review proposed translations before applying.
- `--dry-run` / `-n` : Show what would happen without modifying files.
- `--overwrite` : Overwrite existing translations.
- `--backup` / `-b` : Create a `.bak` file before writing changes.
- `--no-app-context` : Disable automatic extraction of app context from project files.
- `--mark-empty` : Mark empty/whitespace strings as translated to avoid re-translation.
