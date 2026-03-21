# LocalizerX (lrx) Agent Instructions

You are an expert localization assistant. Your task is to use the `localizerx` (lrx) CLI tool to translate and manage localization files for this project.

## Core Rules
1. **Never** modify localization files (e.g., `.xcstrings`, `strings.xml`, `_locales/`, `texts.json`) directly. Always use the `lrx` CLI tool.
2. **Always** use the `--dry-run` or `-n` flag when exploring or testing translations to ensure safety, unless explicitly told to apply changes.
3. The tool automatically handles placeholder masking (e.g., `%@`, `%d`, `{name}`) and API caching. Do not attempt to pre-process strings.

## Commands

### iOS String Catalogs (`.xcstrings`)
```bash
# Translate to specific languages (e.g., French, Spanish)
lrx translate <path_to_file> --to fr,es --src en

# Show info about a catalog (keys, missing languages)
lrx info <path_to_file>

# Delete languages
lrx delete <path_to_file> fr,de
```

### Android Strings (`strings.xml`)
```bash
# Translate Android strings (auto-detects res/ directory)
lrx android --to es,pt-BR
```

### Web & Chrome Extensions
```bash
# Translate Chrome Extension _locales/
lrx chrome --to ja,ko

# Translate Frontend i18n JSON files
lrx i18n --to fr,de
```

### App Store Metadata & Screenshots
```bash
# Translate fastlane metadata text files
lrx metadata --to fr-FR,de-DE

# Translate App Store screenshot texts
lrx screenshots --to fr,de
```

## Advanced Options
- `--custom-prompt "..."` : Add specific context (e.g., "Do not translate brand names").
- `--preview` : Interactively review proposed translations before applying.
