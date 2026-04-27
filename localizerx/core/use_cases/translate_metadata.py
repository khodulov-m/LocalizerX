"""Use cases for translating App Store metadata."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from localizerx.core.ports.repository import CatalogRepository
from localizerx.parser.app_context import AppContext
from localizerx.parser.metadata_model import MetadataCatalog, MetadataFieldType
from localizerx.translator.base import TranslationRequest, Translator


@dataclass
class MetadataTranslationTask:
    locale: str
    field_types: list[MetadataFieldType] = field(default_factory=list)


from localizerx.utils.limits import (
    SHORTEN_MAX_RETRIES,
    LimitAction,
    build_shorten_prompt,
    truncate_to_limit,
    validate_limit,
)


@dataclass
class TranslateMetadataRequest:
    path: Path
    source_locale: str
    target_locales: list[str]
    field_types: list[MetadataFieldType] | None = None
    dry_run: bool = False
    preview: bool = False
    overwrite: bool = False
    limit_action: LimitAction = LimitAction.WARN
    backup: bool = False


@dataclass
class MetadataTranslationPreview:
    locale: str
    field_type: MetadataFieldType
    translation: str
    chars: int = 0
    limit: int = 0
    is_over_limit: bool = False


@dataclass
class TranslateMetadataResult:
    tasks: dict[str, MetadataTranslationTask] = field(default_factory=dict)
    preview_items: list[MetadataTranslationPreview] = field(default_factory=list)
    limit_warnings: list[str] = field(default_factory=list)
    saved: bool = False


class TranslateMetadataUseCase:
    """Orchestrates the translation of App Store metadata."""

    def __init__(self, repository: CatalogRepository[MetadataCatalog], translator: Translator):
        self.repository = repository
        self.translator = translator

    async def execute(
        self,
        request: TranslateMetadataRequest,
        on_task_summary: Callable[[dict[str, MetadataTranslationTask]], None] | None = None,
        on_translation_start: Callable[[str, int], Any] | None = None,
        on_translation_progress: Callable[[Any, int], None] | None = None,
        on_preview_request: Callable[[list[MetadataTranslationPreview]], bool] | None = None,
    ) -> TranslateMetadataResult:
        """Execute App Store metadata translation workflow."""
        from localizerx.translator.metadata_prompts import (
            build_batch_metadata_prompt,
            build_keywords_prompt,
            build_metadata_prompt,
            parse_batch_metadata_response,
        )

        catalog = self.repository.read(request.path, source_locale=request.source_locale)

        tasks = {}
        for target_locale in request.target_locales:
            fields = catalog.get_fields_needing_translation(
                target_locale, field_types=request.field_types, overwrite=request.overwrite
            )
            if fields:
                tasks[target_locale] = MetadataTranslationTask(
                    locale=target_locale, field_types=fields
                )

        result = TranslateMetadataResult(tasks=tasks)

        if not tasks:
            return result

        if on_task_summary:
            on_task_summary(tasks)

        if request.dry_run:
            return result

        all_results = {}  # locale -> {field_type: translation}
        limit_warnings = []
        source_meta = catalog.get_source_metadata()
        app_context = AppContext.from_metadata(source_meta) if source_meta else None

        semaphore = asyncio.Semaphore(5)

        async def _translate_locale(
            target_locale: str, field_types: list[MetadataFieldType]
        ) -> dict[MetadataFieldType, str]:
            async with semaphore:
                keyword_item: tuple[MetadataFieldType, str] | None = None
                batch_items: list[tuple[MetadataFieldType, str]] = []
                for ft in field_types:
                    f = source_meta.get_field(ft)
                    if not f:
                        continue
                    if ft == MetadataFieldType.KEYWORDS:
                        keyword_item = (ft, f.content)
                    else:
                        batch_items.append((ft, f.content))

                total = (1 if keyword_item else 0) + len(batch_items)
                if total == 0:
                    return {}

                task_id = (
                    on_translation_start(target_locale, total) if on_translation_start else None
                )

                res_dict: dict[MetadataFieldType, str] = {}

                if keyword_item:
                    ft, text = keyword_item
                    prompt = build_keywords_prompt(
                        text,
                        request.source_locale,
                        target_locale,
                        app_context=app_context,
                    )
                    translated = await self.translator._call_api(prompt)
                    res_dict[ft] = translated.strip()
                    if on_translation_progress and task_id:
                        on_translation_progress(task_id, 1)

                if len(batch_items) == 1:
                    ft, text = batch_items[0]
                    prompt = build_metadata_prompt(text, ft, request.source_locale, target_locale)
                    translated = await self.translator._call_api(prompt)
                    res_dict[ft] = translated.strip()
                    if on_translation_progress and task_id:
                        on_translation_progress(task_id, 1)
                elif len(batch_items) > 1:
                    prompt = build_batch_metadata_prompt(
                        batch_items, request.source_locale, target_locale
                    )
                    response = await self.translator._call_api(prompt)
                    translations = parse_batch_metadata_response(response, len(batch_items))

                    for (ft, _), translated in zip(batch_items, translations):
                        if translated:
                            res_dict[ft] = translated
                        if on_translation_progress and task_id:
                            on_translation_progress(task_id, 1)

                return res_dict

        # Run locales concurrently
        locale_results = await asyncio.gather(
            *[_translate_locale(loc, t.field_types) for loc, t in tasks.items()],
            return_exceptions=True,
        )

        for loc, res in zip(tasks.keys(), locale_results):
            if isinstance(res, Exception):
                # Handle or log error
                continue
            all_results[loc] = res

        # Validate character limits
        from localizerx.utils.locale import get_fastlane_locale_name

        for target_locale, translations in all_results.items():
            for field_type, translated in list(translations.items()):
                validation = validate_limit(translated, field_type)
                if validation.is_valid:
                    continue

                if request.limit_action == LimitAction.RETRY:
                    target_name = get_fastlane_locale_name(target_locale)
                    field_label = field_type.value.replace("_", " ")
                    current = translated
                    current_validation = validation
                    for _ in range(SHORTEN_MAX_RETRIES):
                        shorten_prompt = build_shorten_prompt(
                            translation=current,
                            field_label=field_label,
                            target_language=target_name,
                            limit=current_validation.limit,
                        )
                        retried = (await self.translator._call_api(shorten_prompt)).strip()
                        if retried:
                            current = retried
                            current_validation = validate_limit(current, field_type)
                            if current_validation.is_valid:
                                break

                    if current_validation.is_valid:
                        all_results[target_locale][field_type] = current
                    else:
                        truncated = truncate_to_limit(current, field_type)
                        all_results[target_locale][field_type] = truncated
                        limit_warnings.append(
                            f"[{target_locale}] {field_type.value}: still over after "
                            f"{SHORTEN_MAX_RETRIES} retries, truncated to {len(truncated)}/"
                            f"{current_validation.limit} chars"
                        )
                    continue

                warning = (
                    f"[{target_locale}] {field_type.value}: "
                    f"{validation.char_count}/{validation.limit} chars "
                    f"(over by {validation.chars_over})"
                )
                limit_warnings.append(warning)

                if request.limit_action == LimitAction.ERROR:
                    raise ValueError(f"Character limit exceeded: {warning}")
                elif request.limit_action == LimitAction.TRUNCATE:
                    all_results[target_locale][field_type] = truncate_to_limit(
                        translated, field_type
                    )

        result.limit_warnings = limit_warnings

        if request.preview and on_preview_request:
            preview_items = []
            for locale, res in all_results.items():
                for field_type, value in res.items():
                    validation = validate_limit(value, field_type)
                    preview_items.append(
                        MetadataTranslationPreview(
                            locale=locale,
                            field_type=field_type,
                            translation=value,
                            chars=validation.char_count,
                            limit=validation.limit,
                            is_over_limit=not validation.is_valid,
                        )
                    )

            if not on_preview_request(preview_items):
                return result

        # Apply results
        for locale, res in all_results.items():
            locale_data = catalog.get_or_create_locale(locale)
            for field_type, value in res.items():
                locale_data.set_field(field_type, value)

        # Save
        self.repository.write(catalog, request.path)

        # Copy untranslatable files
        import shutil

        untranslatable_files = [
            "marketing_url.txt",
            "privacy_url.txt",
            "support_url.txt",
            "apple_tv_privacy_policy.txt",
        ]
        source_dir = request.path / request.source_locale
        if source_dir.exists():
            for target_locale in all_results.keys():
                target_dir = request.path / target_locale
                target_dir.mkdir(parents=True, exist_ok=True)
                for filename in untranslatable_files:
                    src_file = source_dir / filename
                    if src_file.exists():
                        dst_file = target_dir / filename
                        if request.backup and dst_file.exists():
                            backup_path = dst_file.with_suffix(".txt.backup")
                            shutil.copy2(dst_file, backup_path)
                        shutil.copy2(src_file, dst_file)

        result.saved = True
        return result
