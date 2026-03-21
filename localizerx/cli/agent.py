"""CLI commands for AI agent integration."""

import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Prompt

from localizerx.cli.utils import console

AGENT_INSTRUCTIONS = """# LocalizerX (lrx) Agent Instructions

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
"""

SKILL_INSTRUCTIONS = """---
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

Translates App Store metadata text files (`name.txt`, `subtitle.txt`, etc.). Automatically detects both iOS (`fastlane/metadata`) and macOS (`fastlane/metadata_macos`) directories.

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
- **Placeholders**: The tool automatically masks variables (e.g., `%@`, `{name}`, `$1`) to ensure they are not corrupted during translation.
"""

def init_agent(
    target_file: Annotated[
        Optional[str],
        typer.Option(
            "--file",
            "-f",
            help="Specific file to write to (e.g., '.cursorrules', 'AGENT.md')",
        ),
    ] = None,
    skill: Annotated[
        bool,
        typer.Option(
            "--skill",
            help="Install as Gemini CLI Skill (to ~/.agents/skills/localizerx/)",
        ),
    ] = False,
) -> None:
    """Install AI agent instructions into your project.
    
    This command writes LocalizerX instructions to a standard agent file
    (like .cursorrules, .clinerules, or AGENT.md) so your AI assistant 
    knows how to use the `lrx` CLI automatically.
    """
    options = {
        "1": "Gemini CLI Skill (~/.agents/skills/localizerx/SKILL.md)",
        "2": ".cursorrules",
        "3": ".clinerules",
        "4": "AGENT.md",
        "5": "Other (specify)",
    }
    
    if skill:
        choice = "1"
    elif target_file:
        # If target_file is provided, we skip the interactive prompt
        choice = None
    else:
        console.print("[bold]Select the AI assistant instructions format/file:[/bold]")
        for key, value in options.items():
            console.print(f"  {key}. {value}")
            
        choice = Prompt.ask("Choose an option", choices=list(options.keys()), default="1")
        
    if choice == "1":
        skill_dir = Path.home() / ".agents" / "skills" / "localizerx"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(SKILL_INSTRUCTIONS)
        console.print(f"[green]Installed Gemini CLI skill to {skill_file}[/green]")
        console.print("[blue]Tip: Run `/skills reload` in Gemini CLI to activate the new skill.[/blue]")
        return
    elif choice == "5":
        target_file = Prompt.ask("Enter filename")
    elif choice in ["2", "3", "4"]:
        target_file = options[choice]
        
    # If choice was None and target_file was provided, we continue here
    if not target_file:
        return
        
    path = Path(target_file)
    
    if path.exists():
        content = path.read_text()
        if "LocalizerX (lrx) Agent Instructions" in content:
            console.print(f"[yellow]Instructions already exist in {path.name}.[/yellow]")
            raise typer.Exit(0)
            
        path.write_text(content + "\n\n" + AGENT_INSTRUCTIONS)
        console.print(f"[green]Appended LocalizerX instructions to {path.name}[/green]")
    else:
        path.write_text(AGENT_INSTRUCTIONS)
        console.print(f"[green]Created {path.name} with LocalizerX instructions[/green]")
