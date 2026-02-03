"""App Store screenshot text commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from localizerx.cli.utils import console, create_progress
from localizerx.config import get_cache_dir, load_config
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.utils.locale import (
    get_language_name,
    parse_language_list,
    validate_language_code,
)


def screenshots_translate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to screenshots/texts.json (auto-detected if omitted)",
        ),
    ] = None,
    to: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help=(
                "Target languages (comma-separated)."
                " If not specified, uses default_targets from config."
            ),
        ),
    ] = "",
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source language (defaults to sourceLanguage from file or 'en')",
        ),
    ] = "",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be translated without making changes",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            "-p",
            help="Show proposed translations before applying",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing translations",
        ),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Create backup before writing changes",
        ),
    ] = False,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
) -> None:
    """Translate App Store screenshot texts to target languages.

    If screenshots/texts.json doesn't exist, creates a template.
    If it exists, translates to target languages (--to or config defaults).
    """
    _run_screenshots_translate(
        path=path,
        to=to,
        src=src,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=backup,
        model=model,
    )


def screenshots_info(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to screenshots/texts.json (auto-detected if omitted)",
        ),
    ] = None,
) -> None:
    """Show information about screenshot texts file."""
    from localizerx.io.screenshots import detect_screenshots_path, read_screenshots
    from localizerx.parser.screenshots_model import (
        SCREENSHOT_TEXT_WORD_LIMIT,
    )

    # Find screenshots path
    if path is None:
        path = detect_screenshots_path()
        if path is None:
            console.print("[red]Error:[/red] No screenshots/texts.json file found")
            console.print("Run 'localizerx screenshots' to create a template")
            raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Error:[/red] File does not exist: {path}")
        raise typer.Exit(1)

    try:
        catalog = read_screenshots(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Screenshots File:[/bold] {path}")
    console.print(f"[bold]Source Language:[/bold] {catalog.source_language}")
    console.print(f"[bold]Screens:[/bold] {catalog.screen_count}")
    console.print(f"[bold]Localized Languages:[/bold] {catalog.locale_count}")
    console.print()

    # Show screens table
    table = Table(title="Source Screens")
    table.add_column("Screen", style="cyan")
    table.add_column("Texts", style="green")
    table.add_column("Issues", style="yellow")

    for screen_id, screen in catalog.screens.items():
        text_count = screen.text_count
        over_limit = screen.get_over_limit_texts()

        issues = []
        if over_limit:
            issues.append(f"{len(over_limit)} over {SCREENSHOT_TEXT_WORD_LIMIT} words")

        issues_str = ", ".join(issues) if issues else "-"

        table.add_row(screen_id, str(text_count), issues_str)

    console.print(table)
    console.print()

    # Show localizations summary
    if catalog.localizations:
        loc_table = Table(title="Localizations")
        loc_table.add_column("Language", style="cyan")
        loc_table.add_column("Name", style="white")
        loc_table.add_column("Screens", style="green")

        for locale, locale_data in sorted(catalog.localizations.items()):
            locale_name = get_language_name(locale)
            loc_table.add_row(locale, locale_name, str(locale_data.screen_count))

        console.print(loc_table)
    else:
        console.print("[dim]No localizations yet[/dim]")


def screenshots_generate(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to screenshots/texts.json (auto-detected or created if omitted)",
        ),
    ] = None,
    metadata_path: Annotated[
        Optional[Path],
        typer.Option(
            "--metadata",
            help="Path to fastlane/metadata directory (auto-detected if omitted)",
        ),
    ] = None,
    hints: Annotated[
        Optional[Path],
        typer.Option(
            "--hints",
            help="JSON file with screen descriptions (interactive mode if omitted)",
        ),
    ] = None,
    text_types: Annotated[
        Optional[str],
        typer.Option(
            "--text-types",
            help="Comma-separated text types to generate (default: headline,subtitle)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show prompts without making API calls",
        ),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            "-p",
            help="Show generated texts before saving",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Overwrite existing source texts",
        ),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Create backup before writing changes",
        ),
    ] = False,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help="Gemini model to use (see 'localizerx models' for list)",
        ),
    ] = None,
    src: Annotated[
        str,
        typer.Option(
            "--src",
            "-s",
            help="Source language for the generated texts (default: en)",
        ),
    ] = "en",
) -> None:
    """Generate marketing-optimized screenshot texts using Gemini AI.

    Reads app context from fastlane/metadata to understand your app,
    then generates compelling screenshot texts based on screen descriptions.

    Two modes:
    - Interactive: prompts for screen descriptions one by one
    - Hints file: reads descriptions from a JSON file (--hints)

    Examples:

        # Interactive mode - prompts for screen descriptions
        localizerx screenshots-generate

        # From hints file
        localizerx screenshots-generate --hints hints.json

        # Generate only headlines
        localizerx screenshots-generate --text-types headline

        # Preview before saving
        localizerx screenshots-generate --preview
    """
    _run_screenshots_generate(
        path=path,
        metadata_path=metadata_path,
        hints_path=hints,
        text_types=text_types,
        dry_run=dry_run,
        preview=preview,
        overwrite=overwrite,
        backup=backup,
        model=model,
        src_lang=src,
    )


def _run_screenshots_generate(
    path: Path | None,
    metadata_path: Path | None,
    hints_path: Path | None,
    text_types: str | None,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
    src_lang: str,
) -> None:
    """Core screenshots generation logic."""
    from localizerx.io.metadata import detect_metadata_path, read_metadata
    from localizerx.io.screenshots import (
        detect_screenshots_path,
        get_default_screenshots_path,
        read_hints_file,
        read_screenshots,
    )
    from localizerx.parser.app_context import AppContext
    from localizerx.parser.screenshots_model import (
        DeviceClass,
        ScreenshotsCatalog,
        ScreenshotTextType,
    )

    config = load_config()

    # Parse text types to generate
    if text_types:
        type_names = [t.strip().lower() for t in text_types.split(",")]
        types_to_generate = []
        for name in type_names:
            try:
                types_to_generate.append(ScreenshotTextType(name))
            except ValueError:
                console.print(f"[yellow]Warning:[/yellow] Unknown text type '{name}'")
        if not types_to_generate:
            console.print("[red]Error:[/red] No valid text types specified")
            raise typer.Exit(1)
    else:
        # Default: headline and subtitle
        types_to_generate = [ScreenshotTextType.HEADLINE, ScreenshotTextType.SUBTITLE]

    # Detect or read metadata for app context
    if metadata_path is None:
        metadata_path = detect_metadata_path()

    if metadata_path is None:
        console.print("[yellow]Warning:[/yellow] No fastlane/metadata found")
        console.print("Creating minimal app context. For better results, create fastlane/metadata.")
        app_context = AppContext(name="App")
    else:
        try:
            # Read metadata with en-US as default source locale
            catalog = read_metadata(metadata_path, source_locale="en-US")
            source_metadata = catalog.get_source_metadata()
            if source_metadata is None:
                # Try to find any locale with data
                for locale in ["en-US", "en", "en-GB"]:
                    source_metadata = catalog.get_locale(locale)
                    if source_metadata and source_metadata.field_count > 0:
                        break

            if source_metadata:
                app_context = AppContext.from_metadata(source_metadata)
                console.print(f"[green]Reading app context from {metadata_path}[/green]")
                console.print(f"  App: {app_context.name}")
                if app_context.subtitle:
                    console.print(f"  Subtitle: {app_context.subtitle}")
            else:
                console.print("[yellow]Warning:[/yellow] No source metadata found")
                app_context = AppContext(name="App")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to read metadata: {e}")
            app_context = AppContext(name="App")

    console.print()

    # Get screen hints (from file or interactive)
    if hints_path:
        try:
            screen_hints = read_hints_file(hints_path)
            console.print(f"[green]Read {len(screen_hints)} screen hints from {hints_path}[/green]")
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    else:
        # Interactive mode
        screen_hints = _interactive_screen_hints()

    if not screen_hints:
        console.print("[yellow]No screens defined. Exiting.[/yellow]")
        raise typer.Exit(0)

    console.print()
    console.print(f"[bold]Screens:[/bold] {len(screen_hints)}")
    console.print(f"[bold]Text types:[/bold] {', '.join(t.value for t in types_to_generate)}")
    console.print()

    # Determine screenshots file path
    if path is None:
        path = detect_screenshots_path()
    if path is None:
        path = get_default_screenshots_path()

    # Load existing catalog or create new one
    if path.exists():
        try:
            catalog = read_screenshots(path)
            console.print(f"[dim]Using existing file: {path}[/dim]")
        except Exception:
            catalog = ScreenshotsCatalog(source_language=src_lang)
    else:
        catalog = ScreenshotsCatalog(source_language=src_lang)
        console.print(f"[dim]Will create new file: {path}[/dim]")

    # Determine which texts need to be generated
    generation_tasks: list[tuple[str, ScreenshotTextType, DeviceClass, str]] = []

    for screen_id, hint in screen_hints.items():
        for text_type in types_to_generate:
            for device_class in DeviceClass:
                # Check if text already exists
                screen = catalog.screens.get(screen_id)
                if screen and not overwrite:
                    existing_text = screen.get_text(text_type)
                    if existing_text:
                        existing_value = existing_text.get_variant(device_class)
                        if existing_value and existing_value.strip():
                            continue  # Skip - already exists

                generation_tasks.append((screen_id, text_type, device_class, hint))

    if not generation_tasks:
        console.print("[green]All texts already exist (use --overwrite to regenerate)[/green]")
        return

    console.print(f"[bold]Texts to generate:[/bold] {len(generation_tasks)}")

    if dry_run:
        console.print("\n[yellow]Dry run - showing prompts without API calls[/yellow]")
        _show_generation_dry_run(app_context, generation_tasks)
        return

    # Perform generation
    asyncio.run(
        _generate_screenshots(
            catalog=catalog,
            path=path,
            app_context=app_context,
            generation_tasks=generation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            model=model,
        )
    )


def _interactive_screen_hints() -> dict[str, str]:
    """Interactively prompt for screen descriptions."""
    console.print("[bold]Interactive mode[/bold] - describe each screenshot screen")
    console.print("[dim]Enter screen descriptions to help generate marketing text.[/dim]")
    console.print("[dim]Press Enter with empty description to finish.[/dim]")
    console.print()

    screen_hints: dict[str, str] = {}
    screen_num = 1

    while True:
        # Prompt for screen ID
        default_id = f"screen_{screen_num}"
        screen_id = typer.prompt(
            f"Screen {screen_num} ID",
            default=default_id,
            show_default=True,
        )

        if not screen_id:
            break

        # Prompt for description
        description = typer.prompt(
            "  Description (what does this screen show?)",
            default="",
        )

        if not description:
            console.print("[dim]  Empty description, skipping this screen[/dim]")
            if not screen_hints:
                continue  # Keep asking if no screens yet
            break

        screen_hints[screen_id] = description
        screen_num += 1
        console.print()

    return screen_hints


def _show_generation_dry_run(
    app_context,
    tasks: list[tuple[str, str, str, str]],
) -> None:
    """Show generation prompts for dry run."""
    from localizerx.translator.screenshots_generation_prompts import build_generation_prompt

    console.print("\n[bold]Prompts that would be sent:[/bold]\n")

    # Show first few prompts
    for i, (screen_id, text_type, device_class, hint) in enumerate(tasks[:3]):
        prompt = build_generation_prompt(
            app_context=app_context,
            screen_id=screen_id,
            text_type=text_type,
            device_class=device_class,
            user_hint=hint,
        )

        header = f"{screen_id} / {text_type.value} / {device_class.value}"
        console.print(f"[cyan]--- {header} ---[/cyan]")
        # Show truncated prompt
        lines = prompt.split("\n")
        preview_lines = lines[:15]
        console.print("\n".join(preview_lines))
        if len(lines) > 15:
            console.print(f"[dim]... ({len(lines) - 15} more lines)[/dim]")
        console.print()

    if len(tasks) > 3:
        console.print(f"[dim]... and {len(tasks) - 3} more prompts[/dim]")


async def _generate_screenshots(
    catalog,
    path: Path,
    app_context,
    generation_tasks: list[tuple[str, str, str, str]],
    config,
    preview: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Perform screenshot text generation and update file."""
    from localizerx.io.screenshots import write_screenshots
    from localizerx.translator.screenshots_generation_prompts import build_generation_prompt

    ss_cfg = config.translator.screenshots
    cache_dir = get_cache_dir(config)
    actual_model = model or ss_cfg.model
    thinking_config = {"thinkingLevel": ss_cfg.thinking_level}

    # {(screen_id, text_type, device_class): generated_text}
    all_generations: dict[tuple, str] = {}

    async with GeminiTranslator(
        model=actual_model,
        batch_size=1,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
        temperature=ss_cfg.temperature,
        thinking_config=thinking_config,
    ) as translator:
        console.print("Generating screenshot texts...")

        with create_progress() as progress:
            task = progress.add_task("Generating", total=len(generation_tasks))

            for screen_id, text_type, device_class, hint in generation_tasks:
                # Build generation prompt
                prompt = build_generation_prompt(
                    app_context=app_context,
                    screen_id=screen_id,
                    text_type=text_type,
                    device_class=device_class,
                    user_hint=hint,
                )

                try:
                    generated = await translator._call_api(prompt)
                    generated = generated.strip()
                except Exception as e:
                    console.print(
                        f"  [red]Error generating {screen_id}/{text_type.value}: {e}[/red]"
                    )
                    progress.advance(task)
                    continue

                all_generations[(screen_id, text_type, device_class)] = generated
                progress.advance(task)

    if not all_generations:
        console.print("[red]No texts were generated[/red]")
        return

    # Show preview if requested
    if preview:
        _show_generation_preview(all_generations)
        if not typer.confirm("Save these generated texts?"):
            console.print("  [yellow]Cancelled[/yellow]")
            return

    # Update catalog
    for (screen_id, text_type, device_class), generated_text in all_generations.items():
        screen = catalog.get_or_create_source_screen(screen_id)
        screen.set_text_variant(text_type, device_class, generated_text)

    # Write file
    write_screenshots(catalog, path, backup=backup)

    console.print(f"\n[green]Saved {len(all_generations)} generated texts to {path}[/green]")
    console.print("\nNext steps:")
    console.print("  1. Review and edit the generated texts in the file")
    console.print("  2. Translate to other languages with:")
    console.print("     localizerx screenshots --to de,fr,es")


def _show_generation_preview(generations: dict) -> None:
    """Show preview of generated texts."""
    table = Table(title="Generated Texts Preview")
    table.add_column("Screen", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Device", style="blue")
    table.add_column("Generated Text", style="green")

    count = 0
    for (screen_id, text_type, device_class), text in generations.items():
        text_preview = text[:40] + "..." if len(text) > 40 else text
        table.add_row(
            screen_id,
            text_type.value,
            device_class.value,
            text_preview,
        )
        count += 1
        if count >= 20:
            break

    if len(generations) > 20:
        table.add_row("...", "", "", f"({len(generations) - 20} more)")

    console.print(table)


def _run_screenshots_translate(
    path: Path | None,
    to: str,
    src: str,
    dry_run: bool,
    preview: bool,
    overwrite: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Core screenshots translation logic."""
    from localizerx.io.screenshots import (
        create_screenshots_template,
        detect_screenshots_path,
        get_default_screenshots_path,
        read_screenshots,
    )

    config = load_config()

    # Determine file path
    if path is None:
        path = detect_screenshots_path()

    # If file doesn't exist, create template
    if path is None or not path.exists():
        template_path = path or get_default_screenshots_path()
        console.print(f"[yellow]Creating template:[/yellow] {template_path}")

        src_lang = src if src else config.source_language
        create_screenshots_template(template_path, source_language=src_lang)

        console.print(f"[green]Created screenshots template at {template_path}[/green]")
        console.print("\nEdit the file to add your screenshot texts, then run:")
        console.print("  localizerx screenshots --to de,fr,es")
        return

    # File exists, translate it
    try:
        catalog = read_screenshots(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Determine source language
    source_lang = src if src else catalog.source_language

    # Parse target languages (use config defaults if not specified)
    if to:
        target_langs = parse_language_list(to)
    else:
        target_langs = config.default_targets.copy()
        if target_langs:
            console.print(
                f"[dim]Using default targets from config ({len(target_langs)} languages)[/dim]"
            )

    if not target_langs:
        console.print("[red]Error:[/red] No target languages specified")
        console.print("Use --to option or set default_targets in config.toml")
        raise typer.Exit(1)

    # Validate
    invalid_langs = [lang for lang in target_langs if not validate_language_code(lang)]
    if invalid_langs:
        codes = ", ".join(invalid_langs)
        console.print(f"[yellow]Warning:[/yellow] Unrecognized language codes: {codes}")

    console.print(f"[bold]Screenshots File:[/bold] {path}")
    console.print(f"[bold]Source:[/bold] {get_language_name(source_lang)} ({source_lang})")
    target_display = ", ".join(f"{get_language_name(loc)} ({loc})" for loc in target_langs)
    console.print(f"[bold]Targets:[/bold] {target_display}")
    console.print()

    # Determine texts to translate per language

    translation_tasks: dict[str, list] = {}  # lang -> [(screen_id, text_type, device_class)]

    for target_lang in target_langs:
        needs = catalog.get_texts_needing_translation(target_lang, overwrite=overwrite)
        if needs:
            translation_tasks[target_lang] = needs

    if not translation_tasks:
        console.print("[green]All texts already translated[/green]")
        return

    # Show summary
    for lang, texts in translation_tasks.items():
        console.print(f"  {get_language_name(lang)}: {len(texts)} text(s) to translate")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        _show_screenshots_dry_run(catalog, translation_tasks)
        return

    # Perform translation
    asyncio.run(
        _translate_screenshots(
            catalog=catalog,
            path=path,
            source_lang=source_lang,
            translation_tasks=translation_tasks,
            config=config,
            preview=preview,
            backup=backup,
            model=model,
        )
    )


def _show_screenshots_dry_run(
    catalog,
    tasks: dict[str, list],
) -> None:
    """Show table of texts that would be translated."""
    from localizerx.parser.screenshots_model import SCREENSHOT_TEXT_WORD_LIMIT

    table = Table(title="Texts to Translate")
    table.add_column("Language", style="cyan")
    table.add_column("Screen", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Device", style="blue")
    table.add_column("Words", style="green")

    for lang, items in tasks.items():
        for screen_id, text_type, device_class in items[:20]:
            screen = catalog.screens.get(screen_id)
            if screen:
                text = screen.get_text(text_type)
                if text:
                    word_count = text.word_count(device_class)
                    words_str = str(word_count)
                    if word_count > SCREENSHOT_TEXT_WORD_LIMIT:
                        words_str = f"[red]{word_count}[/red]"
                    table.add_row(
                        lang,
                        screen_id,
                        text_type.value,
                        device_class.value,
                        words_str,
                    )

        if len(items) > 20:
            table.add_row(lang, f"... ({len(items) - 20} more)", "", "", "")

    console.print(table)


async def _translate_screenshots(
    catalog,
    path: Path,
    source_lang: str,
    translation_tasks: dict[str, list],
    config,
    preview: bool,
    backup: bool,
    model: str | None,
) -> None:
    """Perform screenshot text translations and update file."""
    from localizerx.io.screenshots import write_screenshots
    from localizerx.parser.screenshots_model import DeviceClass, ScreenshotTextType
    from localizerx.translator.screenshots_prompts import (
        build_batch_screenshot_prompt,
        build_screenshot_prompt,
        parse_batch_screenshot_response,
    )

    ss_cfg = config.translator.screenshots
    cache_dir = get_cache_dir(config)
    actual_model = model or ss_cfg.model
    thinking_config = {"thinkingLevel": ss_cfg.thinking_level}

    batch_size = ss_cfg.batch_size

    async with GeminiTranslator(
        model=actual_model,
        max_retries=config.translator.max_retries,
        cache_dir=cache_dir,
        temperature=ss_cfg.temperature,
        thinking_config=thinking_config,
    ) as translator:
        # {lang: {(screen_id, text_type, device_class): translated_text}}
        all_translations: dict[str, dict[tuple, str]] = {}

        for target_lang, items in translation_tasks.items():
            console.print(f"  Translating to {get_language_name(target_lang)}...")
            all_translations[target_lang] = {}

            # Resolve source texts, filtering out missing screens/variants
            resolved: list[tuple[str, ScreenshotTextType, DeviceClass, str]] = []
            for screen_id, text_type, device_class in items:
                screen = catalog.screens.get(screen_id)
                if not screen:
                    continue
                text_obj = screen.get_text(text_type)
                if not text_obj:
                    continue
                source_text = text_obj.get_variant(device_class)
                if not source_text:
                    continue
                resolved.append((screen_id, text_type, device_class, source_text))

            with create_progress() as progress:
                task = progress.add_task(f"    {target_lang}", total=len(resolved))

                for batch_start in range(0, len(resolved), batch_size):
                    batch = resolved[batch_start : batch_start + batch_size]

                    try:
                        if len(batch) == 1:
                            screen_id, text_type, device_class, source_text = batch[0]
                            prompt = build_screenshot_prompt(
                                text=source_text,
                                text_type=text_type,
                                device_class=device_class,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                            )
                            response = await translator._call_api(prompt)
                            translations = [response.strip()]
                        else:
                            prompt = build_batch_screenshot_prompt(
                                items=batch,
                                src_lang=source_lang,
                                tgt_lang=target_lang,
                            )
                            response = await translator._call_api(prompt)
                            translations = parse_batch_screenshot_response(
                                response, len(batch)
                            )

                        for (screen_id, text_type, device_class, _), translated in zip(
                            batch, translations
                        ):
                            if translated:
                                all_translations[target_lang][
                                    (screen_id, text_type, device_class)
                                ] = translated
                    except Exception as e:
                        items_str = ", ".join(
                            f"{sid}/{tt.value}" for sid, tt, _, _ in batch
                        )
                        console.print(
                            f"    [red]Error translating batch [{items_str}]: {e}[/red]"
                        )

                    progress.advance(task, advance=len(batch))

        # Show preview if requested
        if preview:
            _show_screenshots_preview(catalog, all_translations)
            if not typer.confirm("Apply these translations?"):
                console.print("  [yellow]Cancelled[/yellow]")
                return

        # Update catalog
        for target_lang, translations in all_translations.items():
            locale_data = catalog.get_or_create_locale(target_lang)

            for (screen_id, text_type, device_class), translated_text in translations.items():
                target_screen = locale_data.get_or_create_screen(screen_id)
                target_screen.set_text_variant(text_type, device_class, translated_text)

        # Write file
        write_screenshots(catalog, path, backup=backup)

        console.print(f"\n[green]Saved translations to {path}[/green]")


def _show_screenshots_preview(catalog, all_translations: dict) -> None:
    """Show preview of screenshot translations."""
    table = Table(title="Translation Preview")
    table.add_column("Language", style="cyan")
    table.add_column("Screen", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Original", style="dim")
    table.add_column("Translation", style="green")

    count = 0
    for lang, translations in all_translations.items():
        for (screen_id, text_type, device_class), translated in translations.items():
            screen = catalog.screens.get(screen_id)
            original = ""
            if screen:
                text = screen.get_text(text_type)
                if text:
                    original = text.get_variant(device_class) or ""

            orig_preview = original[:25] + "..." if len(original) > 25 else original
            trans_preview = translated[:25] + "..." if len(translated) > 25 else translated

            table.add_row(
                lang,
                screen_id,
                f"{text_type.value}/{device_class.value}",
                orig_preview,
                trans_preview,
            )
            count += 1
            if count >= 20:
                break
        if count >= 20:
            break

    total = sum(len(t) for t in all_translations.values())
    if total > 20:
        table.add_row("...", "", "", "", f"({total - 20} more)")

    console.print(table)
