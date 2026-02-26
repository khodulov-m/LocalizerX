---
name: use-localizerx
description: Translates iOS String Catalogs (.xcstrings), App Store metadata, App Store screenshots texts, and Chrome Extension _locales/ using the LocalizerX CLI tool. Use when you need to translate localization or marketing files.
---

# Use LocalizerX

This skill provides instructions for using the `localizerx` CLI tool to translate localization files in this project.

## Command Reference

The `localizerx` tool supports several commands:

### Translate General Files (iOS `.xcstrings`)

Translates `.xcstrings` files to target languages.

```bash
localizerx translate <path> --to <target_languages> --src <source_language>
```

**Options:**
- `<path>`: The path to the `.xcstrings` file or directory.
- `--to`: Comma-separated list of target language codes (e.g., `fr,es,de`).
- `--src`: The source language code (e.g., `en`).
- `--custom-prompt`: Add custom translation instructions (e.g., "Keep brand names in English").

**Example:**
```bash
localizerx translate Localizable.xcstrings --to fr,es,de --src en
```

### Translate App Store Metadata

Translates App Store metadata text files (`name.txt`, `subtitle.txt`, etc.). Untranslatable URLs (`marketing_url.txt`, `privacy_url.txt`, `support_url.txt`, `apple_tv_privacy_policy.txt`) are automatically copied.

```bash
localizerx metadata <path> --to <target_languages> --src <source_language>
```

**Example:**
```bash
localizerx metadata ./fastlane/metadata --to fr-FR,de-DE
```

You can also set URLs across all locales using the `metadata-urls` command:

```bash
localizerx metadata-urls --marketing <url> --privacy <url> --support <url>
```

### Translate App Store Screenshot Texts

Translates App Store screenshot marketing texts.

```bash
localizerx screenshots --to <target_languages>
```

### Translate Chrome Extension Messages

Translates Chrome Extension `_locales/` message files.

```bash
localizerx chrome --to <target_languages>
```

### Delete Languages from `.xcstrings`

Deletes specified languages from `.xcstrings` files.

```bash
localizerx delete <path> <languages>
```

**Example:**
```bash
localizerx delete Localizable.xcstrings fr,de --backup
```

## Important Notes

- **Environment Variable:** Ensure `GEMINI_API_KEY` is set in the environment before running `localizerx` commands.
- **Dry Run:** You can append `--dry-run` to see what would be translated without modifying files.
