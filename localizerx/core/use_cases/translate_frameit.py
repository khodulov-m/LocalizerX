"""Use cases for translating fastlane frameit strings."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.frameit_model import FrameitCatalog, FrameitString
from localizerx.translator.base import TranslationRequest, Translator

@dataclass
class FrameitTranslationTask:
    locale: str
    titles: list[FrameitString] = field(default_factory=list)
    keywords: list[FrameitString] = field(default_factory=list)

@dataclass
class TranslateFrameitRequest:
    path: Path
    source_locale: str
    target_locales: list[str]
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    custom_instructions: str | None = None

@dataclass
class FrameitTranslationPreview:
    locale: str
    key: str
    type: str # "title" or "keyword"
    translation: str

@dataclass
class TranslateFrameitResult:
    tasks: dict[str, FrameitTranslationTask] = field(default_factory=dict)
    preview_items: list[FrameitTranslationPreview] = field(default_factory=list)
    saved: bool = False

class TranslateFrameitUseCase:
    """Orchestrates the translation of fastlane frameit strings."""

    def __init__(self, repository: CatalogRepository[FrameitCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self,
        request: TranslateFrameitRequest,
        on_task_summary: Callable[[dict[str, FrameitTranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None,
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[FrameitTranslationPreview]], bool] | None = None,
    ) -> TranslateFrameitResult:
        """Execute frameit translation workflow."""
        from localizerx.translator.frameit_prompts import build_frameit_prompt
        
        catalog = self.repository.read(request.path, source_locale=request.source_locale)
        
        tasks = {}
        for target_locale in request.target_locales:
            titles, keywords = catalog.get_strings_needing_translation(
                target_locale, overwrite=request.overwrite
            )
            if titles or keywords:
                tasks[target_locale] = FrameitTranslationTask(
                    locale=target_locale, titles=titles, keywords=keywords
                )

        result = TranslateFrameitResult(tasks=tasks)
        
        if not tasks:
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_results = {} # locale -> {titles: {key: val}, keywords: {key: val}}

        for locale, task in tasks.items():
            total = (1 if task.titles else 0) + (1 if task.keywords else 0)
            task_id = on_translation_start(locale, total) if on_translation_start else None
            all_results[locale] = {"titles": {}, "keywords": {}}

            # Translate titles
            if task.titles:
                titles_dict = {s.key: s.value for s in task.titles}
                prompt = build_frameit_prompt(
                    source_strings=titles_dict,
                    src_lang=request.source_locale,
                    tgt_lang=locale,
                    custom_prompt=request.custom_instructions
                )
                resp = await self.translator._call_api(prompt)
                
                # Cleanup JSON if needed
                if resp.startswith("```json"):
                    resp = resp.replace("```json", "").replace("```", "").strip()
                elif resp.startswith("```"):
                    resp = resp.replace("```", "").strip()
                
                try:
                    all_results[locale]["titles"] = json.loads(resp)
                except Exception:
                    # Fallback or error handling
                    pass
                    
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

            # Translate keywords
            if task.keywords:
                keywords_dict = {s.key: s.value for s in task.keywords}
                prompt = build_frameit_prompt(
                    source_strings=keywords_dict,
                    src_lang=request.source_locale,
                    tgt_lang=locale,
                    custom_prompt=request.custom_instructions
                )
                resp = await self.translator._call_api(prompt)
                
                if resp.startswith("```json"):
                    resp = resp.replace("```json", "").replace("```", "").strip()
                elif resp.startswith("```"):
                    resp = resp.replace("```", "").strip()
                
                try:
                    all_results[locale]["keywords"] = json.loads(resp)
                except Exception:
                    pass
                    
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

        if request.preview and on_preview_request:
            preview_items = []
            for locale, res in all_results.items():
                for key, val in res["titles"].items():
                    preview_items.append(FrameitTranslationPreview(locale, key, "title", val))
                for key, val in res["keywords"].items():
                    preview_items.append(FrameitTranslationPreview(locale, key, "keyword", val))
            
            if not on_preview_request(preview_items):
                return result

        # Apply results
        for locale, res in all_results.items():
            locale_data = catalog.get_or_create_locale(locale)
            for key, val in res["titles"].items():
                locale_data.set_title(key, val)
            for key, val in res["keywords"].items():
                locale_data.set_keyword(key, val)

        # Save
        self.repository.write(catalog, request.path)
        result.saved = True
        return result
