"""Use cases for translating frontend i18n catalogs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.i18n_model import I18nCatalog, I18nMessage
from localizerx.translator.base import TranslationRequest, Translator

@dataclass
class I18nTranslationTask:
    locale: str
    messages: list[I18nMessage] = field(default_factory=list)

@dataclass
class TranslateI18nRequest:
    path: Path
    source_locale: str
    target_locales: list[str]
    remove_locales: list[str] = field(default_factory=list)
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    backup: bool = False
    update_index: bool = True

@dataclass
class I18nTranslationPreview:
    locale: str
    key: str
    translation: str

@dataclass
class TranslateI18nResult:
    removed_locales: list[str] = field(default_factory=list)
    tasks: dict[str, I18nTranslationTask] = field(default_factory=dict)
    preview_items: list[I18nTranslationPreview] = field(default_factory=list)
    saved: bool = False

class TranslateI18nUseCase:
    """Orchestrates the translation of frontend i18n JSON files."""

    def __init__(self, repository: CatalogRepository[I18nCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self,
        request: TranslateI18nRequest,
        on_remove: Callable[[list[str]], None] | None = None,
        on_task_summary: Callable[[dict[str, I18nTranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None,
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[I18nTranslationPreview]], bool] | None = None,
    ) -> TranslateI18nResult:
        """Execute i18n JSON translation workflow."""
        from localizerx.io.i18n import update_index_ts
        
        # Handle removal
        actually_removed = []
        if request.remove_locales:
            from localizerx.io.i18n import delete_i18n_locale
            for loc in request.remove_locales:
                if loc == request.source_locale:
                    continue
                if request.dry_run:
                    actually_removed.append(loc)
                elif delete_i18n_locale(request.path, loc):
                    actually_removed.append(loc)
            
            if on_remove and actually_removed:
                on_remove(actually_removed)

        catalog = self.repository.read(request.path, source_locale=request.source_locale)
        
        tasks = {}
        for target_locale in request.target_locales:
            task = I18nTranslationTask(locale=target_locale)
            task.messages = catalog.get_messages_needing_translation(target_locale, overwrite=request.overwrite)
            if task.messages:
                tasks[target_locale] = task

        result = TranslateI18nResult(removed_locales=actually_removed, tasks=tasks)
        
        if not tasks:
            if actually_removed and request.update_index and not request.dry_run:
                update_index_ts(request.path, catalog)
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_results = {} # locale -> {key: translation}

        for locale, task in tasks.items():
            task_id = on_translation_start(locale, len(task.messages)) if on_translation_start else None
            all_results[locale] = {}

            reqs = [
                TranslationRequest(key=m.key, text=m.value) 
                for m in task.messages
            ]
            batch_results = await self.translator.translate_batch(reqs, request.source_locale, locale)
            
            for res in batch_results:
                if res.success and res.translated:
                    all_results[locale][res.key] = res.translated
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

        if request.preview and on_preview_request:
            preview_items = []
            for locale, res in all_results.items():
                for key, value in res.items():
                    preview_items.append(I18nTranslationPreview(locale, key, value))
            
            if not on_preview_request(preview_items):
                return result

        # Apply results
        for locale, res in all_results.items():
            locale_data = catalog.get_or_create_locale(locale)
            for key, value in res.items():
                locale_data.set_message(key, value)

        # Save
        self.repository.write(
            catalog, 
            request.path, 
            backup=request.backup, 
            locales=list(all_results.keys()),
            update_index=request.update_index
        )
        result.saved = True
        return result
