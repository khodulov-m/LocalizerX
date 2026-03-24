"""Use cases for translating Android catalogs."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.android_model import AndroidCatalog, AndroidPlural, AndroidString, AndroidStringArray
from localizerx.translator.base import TranslationRequest, Translator

@dataclass
class AndroidTranslationTask:
    locale: str
    strings: list[AndroidString] = field(default_factory=list)
    arrays: list[AndroidStringArray] = field(default_factory=list)
    plurals: list[AndroidPlural] = field(default_factory=list)

@dataclass
class TranslateAndroidRequest:
    path: Path
    source_locale: str
    target_locales: list[str]
    remove_locales: list[str] = field(default_factory=list)
    include_arrays: bool = False
    include_plurals: bool = False
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    backup: bool = False

@dataclass
class AndroidTranslationPreview:
    locale: str
    name: str
    translation: str

@dataclass
class TranslateAndroidResult:
    removed_locales: list[str] = field(default_factory=list)
    tasks: dict[str, AndroidTranslationTask] = field(default_factory=dict)
    preview_items: list[AndroidTranslationPreview] = field(default_factory=list)
    saved: bool = False

class TranslateAndroidUseCase:
    """Orchestrates the translation of Android strings.xml."""

    def __init__(self, repository: CatalogRepository[AndroidCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self,
        request: TranslateAndroidRequest,
        on_remove: Callable[[list[str]], None] | None = None,
        on_task_summary: Callable[[dict[str, AndroidTranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None,
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[AndroidTranslationPreview]], bool] | None = None,
    ) -> TranslateAndroidResult:
        """Execute Android translation workflow."""
        
        # Handle removal first (uses direct IO because it's file based removal)
        # Note: In a pure clean arch, we might have a delete method on Repository
        actually_removed = []
        if request.remove_locales:
            from localizerx.io.android import delete_android_locale
            for loc in request.remove_locales:
                if loc == request.source_locale:
                    continue
                if request.dry_run:
                    actually_removed.append(loc)
                elif delete_android_locale(request.path, loc):
                    actually_removed.append(loc)
            
            if on_remove and actually_removed:
                on_remove(actually_removed)

        catalog = self.repository.read(request.path, source_locale=request.source_locale)
        
        tasks = {}
        for target_locale in request.target_locales:
            task = AndroidTranslationTask(locale=target_locale)
            
            task.strings = catalog.get_strings_needing_translation(target_locale, overwrite=request.overwrite)
            
            if request.include_arrays:
                task.arrays = catalog.get_arrays_needing_translation(target_locale, overwrite=request.overwrite)
                
            if request.include_plurals:
                task.plurals = catalog.get_plurals_needing_translation(target_locale, overwrite=request.overwrite)
                
            if task.strings or task.arrays or task.plurals:
                tasks[target_locale] = task

        result = TranslateAndroidResult(removed_locales=actually_removed, tasks=tasks)
        
        if not tasks:
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_results = {} # locale -> {strings: {}, arrays: {}, plurals: {}}

        for locale, task in tasks.items():
            total = len(task.strings) + len(task.arrays) + len(task.plurals)
            task_id = on_translation_start(locale, total) if on_translation_start else None
            
            all_results[locale] = {"strings": {}, "arrays": {}, "plurals": {}}

            # Translate strings
            if task.strings:
                reqs = [TranslationRequest(key=s.name, text=s.value, comment=s.comment) for s in task.strings]
                batch_results = await self.translator.translate_batch(reqs, request.source_locale, locale)
                for res in batch_results:
                    if res.success and res.translated:
                        all_results[locale]["strings"][res.key] = res.translated
                    if on_translation_progress and task_id:
                        on_translation_progress(task_id, 1)

            # Translate arrays
            for arr in task.arrays:
                reqs = [TranslationRequest(key=f"{arr.name}[{i}]", text=item) for i, item in enumerate(arr.items)]
                batch_results = await self.translator.translate_batch(reqs, request.source_locale, locale)
                translated_items = []
                for res in batch_results:
                    if res.success and res.translated:
                        translated_items.append(res.translated)
                    else:
                        idx = int(res.key.split("[")[1].rstrip("]"))
                        translated_items.append(arr.items[idx])
                all_results[locale]["arrays"][arr.name] = translated_items
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

            # Translate plurals
            for plural in task.plurals:
                reqs = [TranslationRequest(key=f"{plural.name}:{qty}", text=text) for qty, text in plural.items.items()]
                batch_results = await self.translator.translate_batch(reqs, request.source_locale, locale)
                translated_items = {}
                for res in batch_results:
                    if res.success and res.translated:
                        qty = res.key.split(":")[1]
                        translated_items[qty] = res.translated
                all_results[locale]["plurals"][plural.name] = translated_items
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

        if request.preview and on_preview_request:
            preview_items = []
            for locale, res in all_results.items():
                for name, value in res["strings"].items():
                    preview_items.append(AndroidTranslationPreview(locale, name, value))
            
            if not on_preview_request(preview_items):
                return result

        # Apply results to catalog
        for locale, res in all_results.items():
            locale_data = catalog.get_or_create_locale(locale)
            for name, value in res["strings"].items():
                locale_data.strings[name] = AndroidString(name=name, value=value)
            for name, items in res["arrays"].items():
                locale_data.string_arrays[name] = AndroidStringArray(name=name, items=items)
            for name, items in res["plurals"].items():
                locale_data.plurals[name] = AndroidPlural(name=name, items=items)

        # Save
        self.repository.write(catalog, request.path, backup=request.backup, locales=list(all_results.keys()))
        result.saved = True
        return result
