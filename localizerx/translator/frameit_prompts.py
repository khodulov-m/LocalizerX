"""Prompts for translating frameit strings."""

from __future__ import annotations

import json

from localizerx.utils.formality import FORMALITY_AUTO, build_formality_directive
from localizerx.utils.locale import get_fastlane_locale_name


def build_frameit_prompt(
    source_strings: dict[str, str],
    src_lang: str,
    tgt_lang: str,
    custom_prompt: str | None = None,
    formality: str = FORMALITY_AUTO,
) -> str:
    """Build a prompt for translating a dictionary of frameit strings."""
    src_name = get_fastlane_locale_name(src_lang) or src_lang
    tgt_name = get_fastlane_locale_name(tgt_lang) or tgt_lang

    prompt = [
        "You are an expert app localization translator specializing in App Store screenshot texts.",
        f"Translate the following screenshot texts from {src_name} ({src_lang}) to {tgt_name} ({tgt_lang}).",
        "",
        "These are short, punchy marketing texts displayed on app screenshots.",
        "Maintain the marketing tone and keep translations as short as possible.",
        "",
    ]

    formality_directive = build_formality_directive(tgt_lang, formality)
    if formality_directive:
        prompt.extend([formality_directive, ""])

    if custom_prompt:
        prompt.extend(["Custom Instructions:", custom_prompt, ""])

    prompt.extend(
        [
            "Return ONLY a valid JSON object where keys are identical to the source, and values are the translations.",
            "Source texts:",
            json.dumps(source_strings, ensure_ascii=False, indent=2),
        ]
    )

    return "\n".join(prompt)
