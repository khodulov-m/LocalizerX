"""Use cases for translating App Store screenshot texts."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.screenshots_model import DeviceClass, ScreenshotsCatalog, ScreenshotTextType
from localizerx.translator.base import TranslationRequest, Translator

@dataclass
class ScreenshotsTranslationTask:
    locale: str
    items: list[tuple[str, ScreenshotTextType, DeviceClass]] = field(default_factory=list)

@dataclass
class TranslateScreenshotsRequest:
    path: Path
    source_lang: str
    target_langs: list[str]
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    batch_size: int = 10

@dataclass
class ScreenshotsTranslationPreview:
    locale: str
    screen_id: str
    text_type: ScreenshotTextType
    device_class: DeviceClass
    translation: str

@dataclass
class TranslateScreenshotsResult:
    tasks: dict[str, ScreenshotsTranslationTask] = field(default_factory=dict)
    preview_items: list[ScreenshotsTranslationPreview] = field(default_factory=list)
    saved: bool = False

class TranslateScreenshotsUseCase:
    """Orchestrates the translation of App Store screenshot texts."""

    def __init__(self, repository: CatalogRepository[ScreenshotsCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self,
        request: TranslateScreenshotsRequest,
        on_task_summary: Callable[[dict[str, ScreenshotsTranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None,
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[ScreenshotsTranslationPreview]], bool] | None = None,
    ) -> TranslateScreenshotsResult:
        """Execute screenshot text translation workflow."""
        from localizerx.translator.screenshots_prompts import (
            build_batch_screenshot_prompt,
            build_screenshot_prompt,
            parse_batch_screenshot_response,
        )
        
        catalog = self.repository.read(request.path)
        
        tasks = {}
        for target_lang in request.target_langs:
            items = catalog.get_texts_needing_translation(target_lang, overwrite=request.overwrite)
            if items:
                tasks[target_lang] = ScreenshotsTranslationTask(locale=target_lang, items=items)

        result = TranslateScreenshotsResult(tasks=tasks)
        
        if not tasks:
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_results = {} # locale -> {(screen_id, text_type, device_class): translation}
        
        batch_size = request.batch_size

        for locale, task in tasks.items():
            # Resolve source texts
            resolved: list[tuple[str, ScreenshotTextType, DeviceClass, str]] = []
            for screen_id, text_type, device_class in task.items:
                source_screen = catalog.get_source_screen(screen_id)
                if not source_screen:
                    continue
                text_obj = source_screen.get_text(text_type)
                if not text_obj:
                    continue
                source_text = text_obj.get_variant(device_class)
                if not source_text:
                    continue
                resolved.append((screen_id, text_type, device_class, source_text))

            if not resolved:
                continue

            task_id = on_translation_start(locale, len(resolved)) if on_translation_start else None
            all_results[locale] = {}

            for batch_start in range(0, len(resolved), batch_size):
                batch = resolved[batch_start : batch_start + batch_size]
                
                try:
                    if len(batch) == 1:
                        screen_id, text_type, device_class, source_text = batch[0]
                        prompt = build_screenshot_prompt(
                            text=source_text,
                            text_type=text_type,
                            device_class=device_class,
                            src_lang=request.source_lang,
                            tgt_lang=locale,
                        )
                        response = await self.translator._call_api(prompt)
                        translations = [response.strip()]
                    else:
                        prompt = build_batch_screenshot_prompt(
                            items=batch,
                            src_lang=request.source_lang,
                            tgt_lang=locale,
                        )
                        response = await self.translator._call_api(prompt)
                        translations = parse_batch_screenshot_response(response, len(batch))

                    for (screen_id, text_type, device_class, _), translated in zip(batch, translations):
                        if translated:
                            all_results[locale][(screen_id, text_type, device_class)] = translated
                        if on_translation_progress and task_id:
                            on_translation_progress(task_id, 1)
                except Exception:
                    if on_translation_progress and task_id:
                        on_translation_progress(task_id, len(batch))

        if request.preview and on_preview_request:
            preview_items = []
            for locale, res in all_results.items():
                for (sid, tt, dc), value in res.items():
                    preview_items.append(ScreenshotsTranslationPreview(locale, sid, tt, dc, value))
            
            if not on_preview_request(preview_items):
                return result

        # Apply results
        for locale, res in all_results.items():
            locale_data = catalog.get_or_create_locale(locale)
            for (sid, tt, dc), value in res.items():
                target_screen = locale_data.get_or_create_screen(sid)
                target_screen.set_text_variant(tt, dc, value)

        # Save
        self.repository.write(catalog, request.path)
        result.saved = True
        return result
