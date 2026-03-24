"""Use cases for translating Chrome Extension catalogs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.extension_model import ExtensionCatalog, ExtensionMessage
from localizerx.translator.base import TranslationRequest, Translator
from localizerx.utils.limits import LimitAction, truncate_to_limit, validate_limit

@dataclass
class ExtensionTranslationTask:
    locale: str
    messages: list[ExtensionMessage] = field(default_factory=list)

@dataclass
class TranslateExtensionRequest:
    path: Path
    source_locale: str
    target_locales: list[str]
    remove_locales: list[str] = field(default_factory=list)
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    backup: bool = False
    limit_action: LimitAction = LimitAction.WARN

@dataclass
class ExtensionTranslationPreview:
    locale: str
    key: str
    translation: str
    is_over_limit: bool = False
    chars: int = 0
    limit: int | None = None

@dataclass
class TranslateExtensionResult:
    removed_locales: list[str] = field(default_factory=list)
    tasks: dict[str, ExtensionTranslationTask] = field(default_factory=dict)
    preview_items: list[ExtensionTranslationPreview] = field(default_factory=list)
    limit_warnings: list[str] = field(default_factory=list)
    saved: bool = False

class TranslateExtensionUseCase:
    """Orchestrates the translation of Chrome Extension locales."""

    def __init__(self, repository: CatalogRepository[ExtensionCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self,
        request: TranslateExtensionRequest,
        on_remove: Callable[[list[str]], None] | None = None,
        on_task_summary: Callable[[dict[str, ExtensionTranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None,
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[ExtensionTranslationPreview]], bool] | None = None,
    ) -> TranslateExtensionResult:
        """Execute Chrome Extension translation workflow."""
        from localizerx.parser.extension_model import KNOWN_CWS_KEYS, ExtensionFieldType
        from localizerx.translator.extension_prompts import build_extension_field_prompt
        from localizerx.utils.locale import chrome_to_standard_locale
        
        # Handle removal
        actually_removed = []
        if request.remove_locales:
            from localizerx.io.extension import delete_extension_locale
            for loc in request.remove_locales:
                if loc == request.source_locale:
                    continue
                if request.dry_run:
                    actually_removed.append(loc)
                elif delete_extension_locale(request.path, loc):
                    actually_removed.append(loc)
            
            if on_remove and actually_removed:
                on_remove(actually_removed)

        catalog = self.repository.read(request.path, source_locale=request.source_locale)
        
        tasks = {}
        for target_locale in request.target_locales:
            task = ExtensionTranslationTask(locale=target_locale)
            task.messages = catalog.get_messages_needing_translation(target_locale, overwrite=request.overwrite)
            if task.messages:
                tasks[target_locale] = task

        result = TranslateExtensionResult(removed_locales=actually_removed, tasks=tasks)
        
        if not tasks:
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_results = {} # locale -> {key: translation}
        limit_warnings = []

        for locale, task in tasks.items():
            task_id = on_translation_start(locale, len(task.messages)) if on_translation_start else None
            all_results[locale] = {}

            # Separate CWS fields from regular messages
            cws_messages = [m for m in task.messages if m.key in KNOWN_CWS_KEYS]
            regular_messages = [m for m in task.messages if m.key not in KNOWN_CWS_KEYS]

            src_std = chrome_to_standard_locale(request.source_locale)
            tgt_std = chrome_to_standard_locale(locale)

            # 1. Translate CWS fields one-by-one with specialized prompts
            for msg in cws_messages:
                field_type = ExtensionFieldType(msg.key)
                prompt = build_extension_field_prompt(
                    text=msg.message,
                    key=msg.key,
                    description=msg.description,
                    field_type=field_type,
                    src_lang=request.source_locale,
                    tgt_lang=locale,
                )

                translated = await self.translator._call_api(prompt)
                translated = translated.strip()

                # Validate against limit
                validation = validate_limit(translated, field_type)

                if not validation.is_valid:
                    warning = (
                        f"[{locale}] {msg.key}: "
                        f"{validation.char_count}/{validation.limit} chars "
                        f"(over by {validation.chars_over})"
                    )
                    limit_warnings.append(warning)

                    if request.limit_action == LimitAction.ERROR:
                        raise ValueError(f"Character limit exceeded: {warning}")
                    elif request.limit_action == LimitAction.TRUNCATE:
                        translated = truncate_to_limit(translated, field_type)

                all_results[locale][msg.key] = translated
                if on_translation_progress and task_id:
                    on_translation_progress(task_id, 1)

            # 2. Translate regular messages in batches
            if regular_messages:
                reqs = [
                    TranslationRequest(key=m.key, text=m.message, comment=m.description) 
                    for m in regular_messages
                ]
                batch_results = await self.translator.translate_batch(reqs, src_std, tgt_std)
                
                for res in batch_results:
                    if res.success and res.translated:
                        all_results[locale][res.key] = res.translated
                    if on_translation_progress and task_id:
                        on_translation_progress(task_id, 1)

        result.limit_warnings = limit_warnings

        if request.preview and on_preview_request:
            preview_items = []
            for locale, res in all_results.items():
                for key, value in res.items():
                    src_msg = catalog.get_source_locale().get_message(key)
                    is_over = False
                    limit = None
                    if src_msg and src_msg.field_type:
                        limit = src_msg.limit
                        is_over = len(value) > limit if limit else False
                    
                    preview_items.append(ExtensionTranslationPreview(
                        locale=locale, 
                        key=key, 
                        translation=value,
                        is_over_limit=is_over,
                        chars=len(value),
                        limit=limit
                    ))
            
            if not on_preview_request(preview_items):
                return result

        # Apply results
        source = catalog.get_source_locale()
        for locale, res in all_results.items():
            locale_data = catalog.get_or_create_locale(locale)
            for key, value in res.items():
                src_msg = source.get_message(key)
                locale_data.set_message(
                    key=key,
                    message=value,
                    description=src_msg.description if src_msg else None,
                    placeholders=src_msg.placeholders if src_msg else None,
                )

        # Save
        self.repository.write(catalog, request.path, backup=request.backup, locales=list(all_results.keys()))
        result.saved = True
        return result

