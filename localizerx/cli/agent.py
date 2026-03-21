"""CLI commands for AI agent integration."""

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


def init_agent(
    target_file: Annotated[
        Optional[str],
        typer.Option(
            "--file",
            "-f",
            help="Specific file to write to (e.g., '.cursorrules', 'AGENT.md')",
        ),
    ] = None,
) -> None:
    """Install AI agent instructions into your project.

    This command writes LocalizerX instructions to a standard agent file
    (like .cursorrules, .clinerules, or AGENT.md) so your AI assistant
    knows how to use the `lrx` CLI automatically.
    """
    options = {
        "1": ".cursorrules",
        "2": ".clinerules",
        "3": "AGENT.md",
        "4": "Other (specify)",
    }

    if not target_file:
        console.print("[bold]Select the AI assistant instructions file to update:[/bold]")
        for key, value in options.items():
            console.print(f"  {key}. {value}")

        choice = Prompt.ask("Choose an option", choices=list(options.keys()), default="3")

        if choice == "4":
            target_file = Prompt.ask("Enter filename")
        else:
            target_file = options[choice]

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
