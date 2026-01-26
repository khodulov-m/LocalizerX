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
# Warn but continue (default)
localizerx metadata examples/metadata --to de-DE --on-limit warn

# Auto-truncate to fit limits
localizerx metadata examples/metadata --to de-DE --on-limit truncate

# Stop on limit exceeded
localizerx metadata examples/metadata --to de-DE --on-limit error
```

### View metadata info

```bash
localizerx metadata-info examples/metadata
```
