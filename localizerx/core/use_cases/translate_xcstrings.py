"""Use cases for translating catalogs."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.model import StringCatalog, Translation
from localizerx.translator.base import TranslationRequest, Translator

@dataclass
class TranslationTask:
    lang: str
    requests: list[TranslationRequest]

@dataclass
class TranslateCatalogRequest:
    file_path: Path
    source_lang: str
    target_langs: list[str]
    remove_langs: list[str] = field(default_factory=list)
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    backup: bool = False
    mark_empty: bool = False
    refresh: bool = False

@dataclass
class TranslationPreview:
    key: str
    source: str
    lang: str
    translation: str
    is_plural: bool = False

@dataclass
class TranslateCatalogResult:
    total_strings: int
    marked_empty_count: int = 0
    removed_languages: list[str] = field(default_factory=list)
    stale_keys_removed: int = 0
    tasks: list[TranslationTask] = field(default_factory=list)
    dry_run: bool = False
    saved: bool = False
    preview_items: list[TranslationPreview] = field(default_factory=list)

class TranslateCatalogUseCase:
    """Orchestrates the translation of a string catalog."""

    def __init__(self, repository: CatalogRepository[StringCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self, 
        request: TranslateCatalogRequest,
        # Callbacks for UI updates
        on_read: Callable[[int], None] | None = None,
        on_task_summary: Callable[[list[TranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None, # returns task_id
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[TranslationPreview]], bool] | None = None, # returns True to apply
    ) -> TranslateCatalogResult:
        """Execute the translation workflow."""
        catalog = self.repository.read(request.file_path)
        
        if on_read:
            on_read(len(catalog.strings))

        working_catalog = catalog.model_copy(deep=True) if request.dry_run else catalog

        marked_count = 0
        if request.mark_empty:
            marked_count = working_catalog.mark_empty_as_translated(
                request.target_langs, overwrite=request.overwrite
            )

        removed_langs = []
        if request.remove_langs:
            removed_langs = working_catalog.remove_languages(request.remove_langs)

        stale_keys = []
        if request.refresh:
            stale_keys = working_catalog.refresh()

        tasks = []
        for target_lang in request.target_langs:
            entries = working_catalog.get_entries_needing_translation(
                target_lang, overwrite=request.overwrite, refresh=request.refresh
            )
            
            if entries:
                requests = []
                for entry in entries:
                    plural_forms = None
                    if entry.source_variations and "plural" in entry.source_variations:
                        plural_forms = {}
                        for form_name, form_data in entry.source_variations["plural"].items():
                            if "stringUnit" in form_data:
                                plural_forms[form_name] = form_data["stringUnit"].get("value", "")
                    
                    requests.append(
                        TranslationRequest(
                            key=entry.key, 
                            text=entry.source_text, 
                            comment=entry.comment,
                            plural_forms=plural_forms
                        )
                    )
                tasks.append(TranslationTask(lang=target_lang, requests=requests))

        result = TranslateCatalogResult(
            total_strings=len(catalog.strings),
            marked_empty_count=marked_count,
            removed_languages=removed_langs,
            stale_keys_removed=len(stale_keys),
            tasks=tasks,
            dry_run=request.dry_run
        )

        if not tasks:
            if (request.refresh and stale_keys) or removed_langs or marked_count > 0:
                if not request.dry_run:
                    self.repository.write(working_catalog, request.file_path, backup=request.backup)
                    result.saved = True
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_translations = {}

        for task in tasks:
            task_id = on_translation_start(task.lang, len(task.requests)) if on_translation_start else None
            
            # Translate using adapter
            batch_results = await self.translator.translate_batch(
                task.requests, request.source_lang, task.lang
            )
            
            for res in batch_results:
                if res.success:
                    if res.key not in all_translations:
                        all_translations[res.key] = {}
                    all_translations[res.key][task.lang] = (
                        res.translated,
                        res.translated_plurals,
                    )
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

        # Generate preview items if needed
        preview_items = []
        if request.preview:
            for key, translations in all_translations.items():
                source = working_catalog.strings[key].source_text if key in working_catalog.strings else ""
                for lang, (trans, plurals) in translations.items():
                    if plurals:
                        plural_preview = ", ".join(
                            f"{k}: {v[:20]}..." if len(v) > 20 else f"{k}: {v}" for k, v in plurals.items()
                        )
                        trans_display = f"[plurals: {plural_preview[:40]}...]"
                        preview_items.append(TranslationPreview(key, source, lang, trans_display, is_plural=True))
                    else:
                        preview_items.append(TranslationPreview(key, source, lang, trans, is_plural=False))

        if request.preview and on_preview_request:
            if not on_preview_request(preview_items):
                return result # Cancelled

        # Apply translations
        for key, translations in all_translations.items():
            if key in working_catalog.strings:
                for lang, (value, translated_plurals) in translations.items():
                    variations = None
                    if translated_plurals:
                        variations = {"plural": {}}
                        for form_name, form_value in translated_plurals.items():
                            variations["plural"][form_name] = {
                                "stringUnit": {"state": "translated", "value": form_value}
                            }
                    
                    working_catalog.strings[key].translations[lang] = Translation(
                        value=value, variations=variations
                    )

        self.repository.write(working_catalog, request.file_path, backup=request.backup)
        result.saved = True
        return result
