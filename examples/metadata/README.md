# Metadata Examples

This directory contains example fastlane metadata files for testing the `localizerx metadata` command.

## Directory Structure

```
metadata/
├── en-US/           # Source locale
│   ├── name.txt
│   ├── subtitle.txt
│   ├── keywords.txt
│   ├── description.txt
│   ├── promotional_text.txt
│   └── release_notes.txt
└── README.md
```

## Character Limits

| Field | Limit |
|-------|-------|
| name | 30 |
| subtitle | 30 |
| keywords | 100 |
| description | 4000 |
| promotional_text | 170 |
| release_notes | 4000 |

## Usage Examples

### Basic translation

```bash
localizerx metadata examples/metadata --to de-DE,fr-FR,es-ES
```

### Dry run (preview without changes)

```bash
localizerx metadata examples/metadata --to de-DE --dry-run
```

### Translate specific fields

```bash
localizerx metadata examples/metadata --to de-DE --fields name,subtitle,keywords
```

### Handle character limit violations

```bash
# Re-ask the model to shorten (default), with truncate as last-resort fallback
localizerx metadata examples/metadata --to de-DE --on-limit retry

# Warn but keep the over-limit text
localizerx metadata examples/metadata --to de-DE --on-limit warn

# Hard-truncate to fit limits (cuts at character or comma boundary)
localizerx metadata examples/metadata --to de-DE --on-limit truncate

# Stop on limit exceeded
localizerx metadata examples/metadata --to de-DE --on-limit error
```

### Check character limits and ASO optimization

```bash
# Check all locales for limit violations and duplicate words
localizerx metadata-check examples/metadata

# Check specific locale
localizerx metadata-check examples/metadata --locale en-US

# Skip duplicate word detection (only check character limits)
localizerx metadata-check examples/metadata --skip-duplicates
```

### Set URLs across locales

```bash
localizerx metadata-urls examples/metadata --marketing "https://example.com" --support "https://example.com/support"
```

### View metadata info

```bash
localizerx metadata-info examples/metadata
```
