"""Utility for extracting app context for translation prompts."""

from __future__ import annotations

from pathlib import Path

from localizerx.io.metadata import detect_metadata_path, read_metadata
from localizerx.parser.app_context import AppContext


def extract_app_context_string(source_locale: str = "en-US") -> str | None:
    """Extract app context from fastlane metadata or Xcode project files.
    
    Used to enrich translation prompts with app context (name, subtitle, description)
    to provide better context for the AI model.
    """
    # 1. Try fastlane metadata first
    try:
        metadata_path = detect_metadata_path()
        if metadata_path:
            catalog = read_metadata(metadata_path, source_locale=source_locale)
            # Try specified locale first, fallback to en-US, then any available
            locale_data = catalog.locales.get(source_locale)
            if not locale_data and "en-US" in catalog.locales:
                locale_data = catalog.locales["en-US"]
            if not locale_data and catalog.locales:
                locale_data = next(iter(catalog.locales.values()))

            if locale_data:
                app_context = AppContext.from_metadata(locale_data)
                context_str = app_context.to_prompt_context(max_desc_length=150)
                if context_str:
                    return context_str
    except Exception:
        # If metadata reading fails, fall back to Xcode project parsing
        pass

    # 2. Fallback to Xcode workspace or project name
    cwd = Path.cwd()

    # Try .xcworkspace first
    workspaces = list(cwd.glob("*.xcworkspace"))
    if workspaces:
        return f"- App Name: {workspaces[0].stem}"

    # Then try .xcodeproj
    projects = list(cwd.glob("*.xcodeproj"))
    if projects:
        return f"- App Name: {projects[0].stem}"

    return None
