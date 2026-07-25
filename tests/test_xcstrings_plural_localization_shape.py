"""Regression tests: plural localizations must never carry a stray stringUnit.

In the xcstrings format a localization holds either a `stringUnit` or `variations`.
LocalizerX used to rebuild every localization from its model on write, which injected
an empty `stringUnit` next to `variations` — on every run, even for keys it never
translated — and dropped `substitutions` while at it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from localizerx.adapters.repository import XCStringsRepository
from localizerx.core.use_cases.translate_xcstrings import (
    TranslateCatalogRequest,
    TranslateCatalogUseCase,
)
from localizerx.io.xcstrings import read_xcstrings, write_xcstrings
from localizerx.translator.base import TranslationRequest, TranslationResult, Translator


def _plural_variations(forms: dict[str, str]) -> dict:
    return {
        "plural": {
            name: {"stringUnit": {"state": "translated", "value": value}}
            for name, value in forms.items()
        }
    }


def _write_catalog(path: Path, ru_localization: dict) -> None:
    data = {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "obd.diagnostics.milOnCount": {
                "localizations": {
                    "en": {
                        "variations": _plural_variations(
                            {"one": "%lld fault", "other": "%lld faults"}
                        )
                    },
                    "ru": ru_localization,
                }
            }
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ru_localization(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["strings"]["obd.diagnostics.milOnCount"]["localizations"]["ru"]


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    return tmp_path / "Localizable.xcstrings"


class TestPluralLocalizationShape:
    """A plural localization round-trips without gaining a stringUnit."""

    def test_round_trip_does_not_inject_string_unit(self, catalog_path):
        """Writing a catalog back untouched must not alter plural localizations."""
        ru = {
            "variations": _plural_variations(
                {
                    "one": "%lld ошибка",
                    "few": "%lld ошибки",
                    "many": "%lld ошибок",
                    "other": "%lld ошибки",
                }
            )
        }
        _write_catalog(catalog_path, ru)

        write_xcstrings(read_xcstrings(catalog_path), catalog_path)

        assert _ru_localization(catalog_path) == ru

    def test_write_heals_existing_empty_string_unit(self, catalog_path):
        """An already-corrupted file loses the stray empty stringUnit on write."""
        variations = _plural_variations({"one": "%lld ошибка", "other": "%lld ошибки"})
        _write_catalog(
            catalog_path,
            {"stringUnit": {"state": "translated", "value": ""}, "variations": variations},
        )

        write_xcstrings(read_xcstrings(catalog_path), catalog_path)

        assert _ru_localization(catalog_path) == {"variations": variations}

    def test_non_empty_string_unit_is_preserved(self, catalog_path):
        """A stringUnit written by Xcode alongside variations stays untouched."""
        ru = {
            "stringUnit": {"state": "translated", "value": "%lld ошибки"},
            "variations": _plural_variations({"one": "%lld ошибка", "other": "%lld ошибки"}),
        }
        _write_catalog(catalog_path, ru)

        write_xcstrings(read_xcstrings(catalog_path), catalog_path)

        assert _ru_localization(catalog_path) == ru

    def test_substitutions_are_preserved(self, catalog_path):
        """`substitutions` are not modelled but must survive a write."""
        ru = {
            "stringUnit": {"state": "translated", "value": "%#@faults@"},
            "substitutions": {
                "faults": {
                    "argNum": 1,
                    "formatSpecifier": "lld",
                    "variations": _plural_variations(
                        {"one": "%arg ошибка", "other": "%arg ошибок"}
                    ),
                }
            },
        }
        _write_catalog(catalog_path, ru)

        write_xcstrings(read_xcstrings(catalog_path), catalog_path)

        assert _ru_localization(catalog_path) == ru

    def test_plain_translation_keeps_string_unit(self, catalog_path):
        """Non-plural localizations still round-trip with their stringUnit."""
        ru = {"stringUnit": {"state": "translated", "value": "Привет"}}
        _write_catalog(catalog_path, ru)

        write_xcstrings(read_xcstrings(catalog_path), catalog_path)

        assert _ru_localization(catalog_path) == ru


class _PluralStubTranslator(Translator):
    """Returns fixed Russian plural forms for any request."""

    async def translate_text(self, text, source_lang, target_lang, context=None):  # noqa: D102
        return text

    async def close(self):  # noqa: D102
        return None

    async def translate_batch(self, requests, source_lang, target_lang):  # noqa: D102
        plurals = {
            "one": "%lld ошибка",
            "few": "%lld ошибки",
            "many": "%lld ошибок",
            "other": "%lld ошибки",
        }
        return [
            TranslationResult(
                key=req.key,
                original=req.text,
                translated=plurals["other"] if req.plural_forms else req.text,
                translated_plurals=plurals if req.plural_forms else None,
            )
            for req in requests
        ]


@pytest.mark.asyncio
async def test_translated_plural_gets_no_string_unit(catalog_path):
    """A freshly translated plural entry is written as variations only."""
    _write_catalog(catalog_path, {})
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    del data["strings"]["obd.diagnostics.milOnCount"]["localizations"]["ru"]
    catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    use_case = TranslateCatalogUseCase(
        repository=XCStringsRepository(), translator=_PluralStubTranslator()
    )
    result = await use_case.execute(
        TranslateCatalogRequest(file_path=catalog_path, source_lang="en", target_langs=["ru"])
    )

    assert result.saved
    ru = _ru_localization(catalog_path)
    assert "stringUnit" not in ru
    assert ru["variations"]["plural"]["many"]["stringUnit"]["value"] == "%lld ошибок"


@pytest.mark.asyncio
async def test_translating_one_key_does_not_touch_another(tmp_path):
    """Keys that are already translated stay byte-identical."""
    path = tmp_path / "Localizable.xcstrings"
    untouched = {
        "variations": _plural_variations({"one": "%lld ошибка", "other": "%lld ошибки"})
    }
    data = {
        "sourceLanguage": "en",
        "version": "1.0",
        "strings": {
            "obd.diagnostics.milOnCount": {
                "localizations": {
                    "en": {
                        "variations": _plural_variations(
                            {"one": "%lld fault", "other": "%lld faults"}
                        )
                    },
                    "ru": untouched,
                }
            },
            "greeting": {
                "localizations": {"en": {"stringUnit": {"state": "translated", "value": "Hi"}}}
            },
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    use_case = TranslateCatalogUseCase(
        repository=XCStringsRepository(), translator=_PluralStubTranslator()
    )
    await use_case.execute(
        TranslateCatalogRequest(file_path=path, source_lang="en", target_langs=["ru"])
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["strings"]["obd.diagnostics.milOnCount"]["localizations"]["ru"] == untouched
