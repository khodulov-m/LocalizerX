"""Fastlane Frameit commands."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console, create_progress
from localizerx.config import get_cache_dir, load_config
from localizerx.io.frameit import (
    detect_frameit_path,
    ensure_framefile,
    read_frameit_catalog,
    write_frameit_locale,
)
from localizerx.translator.frameit_prompts import build_frameit_prompt
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.utils.locale import get_fastlane_locale_name, parse_fastlane_locale_list

frameit_cmd = typer.Typer(help="Fastlane Frameit screenshot text translation")

@frameit_cmd.callback(invoke_without_command=True)
def frameit(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Path to fastlane screenshots directory"),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to", "-t", help="Target fastlane locales (comma-separated, e.g., 'fr-FR,de-DE')"
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option("--src", "-s", help="Source locale"),
    ] = "en-US",
    prepare: Annotated[
        bool,
        typer.Option("--prepare", help="Prepare frameit structure (Framefile.json and templates) and exit"),
    ] = False,
    custom_prompt: Annotated[
        Optional[str],
        typer.Option("--custom-prompt", help="Custom instructions for translation"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Gemini model to use"),
    ] = None,
) -> None:
    """Translate frameit title.strings and keyword.strings to target locales."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_config()
    base_path = path if path else detect_frameit_path()

    if prepare:
        ensure_framefile(base_path)
        catalog = read_frameit_catalog(base_path, source_locale=src)
        source_metadata = catalog.get_source_metadata()
        
        if not source_metadata or (not source_metadata.title_strings and not source_metadata.keyword_strings):
            source_metadata = catalog.get_or_create_locale(src)
            source_metadata.set_title("screenshot_1", "Your Catchy Title")
            source_metadata.set_keyword("screenshot_1", "KEYWORD")
            write_frameit_locale(base_path, source_metadata)
            console.print(f"[green]Created template in {base_path / src}[/green]")
        
        console.print(f"[green]Frameit structure prepared in {base_path}[/green]")
        raise typer.Exit(0)

    target_locales = parse_fastlane_locale_list(to) if to else config.default_targets
    if not target_locales:
        console.print("[red]Error:[/red] No target locales specified.")
        raise typer.Exit(1)

    catalog = read_frameit_catalog(base_path, source_locale=src)
    source_metadata = catalog.get_source_metadata()

    # Initialize Framefile if needed
    ensure_framefile(base_path)

    # If source is missing or empty, create a template
    if not source_metadata or (not source_metadata.title_strings and not source_metadata.keyword_strings):
        console.print(
            f"[yellow]Source locale '{src}' not found or empty. Creating template...[/yellow]"
        )
        source_metadata = catalog.get_or_create_locale(src)
        source_metadata.set_title("App-Screenshot-1", "Amazing Feature")
        source_metadata.set_keyword("App-Screenshot-1", "Keyword")
        write_frameit_locale(base_path, source_metadata)
        console.print(f"[green]Created template in {base_path / src}[/green]")
        console.print("Please edit the template files and run again.")
        raise typer.Exit(0)

    console.print(f"[bold]Frameit path:[/bold] {base_path}")
    console.print(f"[bold]Source locale:[/bold] {src}")

    # Calculate tasks
    tasks = []
    for tgt in target_locales:
        tgt_metadata = catalog.get_locale(tgt)

        missing_titles = {}
        missing_keywords = {}

        for k, v in source_metadata.title_strings.items():
            if not tgt_metadata or k not in tgt_metadata.title_strings:
                missing_titles[k] = v.value

        for k, v in source_metadata.keyword_strings.items():
            if not tgt_metadata or k not in tgt_metadata.keyword_strings:
                missing_keywords[k] = v.value

        if missing_titles or missing_keywords:
            tasks.append((tgt, missing_titles, missing_keywords))

    if not tasks:
        console.print("[green]All strings are already translated.[/green]")
        return

    asyncio.run(_run_translations(base_path, catalog, src, tasks, config, model, custom_prompt))


async def _run_translations(
    base_path: Path,
    catalog,
    src_lang: str,
    tasks: list,
    config,
    model: str | None,
    custom_prompt: str | None,
) -> None:
    cache_dir = get_cache_dir(config)
    actual_model = model or config.translator.model

    async with GeminiTranslator(
        model=actual_model,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
    ) as translator:
        with create_progress() as progress:
            total_items = sum(len(t) + len(k) for _, t, k in tasks)
            p_task = progress.add_task("Translating", total=total_items)

            for tgt, missing_titles, missing_keywords in tasks:
                tgt_locale = catalog.get_or_create_locale(tgt)

                # Translate titles
                if missing_titles:
                    prompt = build_frameit_prompt(missing_titles, src_lang, tgt, custom_prompt)
                    try:
                        resp = await translator._call_api(prompt)
                        # Remove markdown code blocks if any
                        if resp.startswith("```json"):
                            resp = resp.replace("```json", "").replace("```", "").strip()
                        elif resp.startswith("```"):
                            resp = resp.replace("```", "").strip()

                        translated = json.loads(resp)
                        for k, v in translated.items():
                            tgt_locale.set_title(k, v)

                    except Exception as e:
                        console.print(f"[red]Error translating titles to {tgt}:[/red] {e}")

                    progress.advance(p_task, advance=len(missing_titles))

                # Translate keywords
                if missing_keywords:
                    prompt = build_frameit_prompt(missing_keywords, src_lang, tgt, custom_prompt)
                    try:
                        resp = await translator._call_api(prompt)
                        if resp.startswith("```json"):
                            resp = resp.replace("```json", "").replace("```", "").strip()
                        elif resp.startswith("```"):
                            resp = resp.replace("```", "").strip()

                        translated = json.loads(resp)
                        for k, v in translated.items():
                            tgt_locale.set_keyword(k, v)

                    except Exception as e:
                        console.print(f"[red]Error translating keywords to {tgt}:[/red] {e}")

                    progress.advance(p_task, advance=len(missing_keywords))

                write_frameit_locale(base_path, tgt_locale)
                console.print(f"  [green]Translated {tgt}[/green]")
