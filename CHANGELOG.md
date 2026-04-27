# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `--on-limit retry` option for `lrx metadata` and `lrx chrome`: when an App Store / Chrome Web Store field overflows its character limit (common for German, Russian, Polish), the model is re-prompted up to 2 times to rewrite the translation shorter while preserving meaning, tone, and structure. Falls back to `truncate` if retries still don't fit. `retry` is now the default action; the previous default (`warn`) remains available explicitly.

### Fixed
- Fixed `NameError: name 'asyncio' is not defined` in `lrx metadata` command during non-dry-run translation.
- Plural translation now produces grammatically correct forms for languages whose CLDR plural system differs from the source. Previously each plural form was translated in isolation against the same source text, so going from English (`one`/`other`) to Russian, Polish, or Arabic produced incorrect or duplicated forms and could leave required CLDR categories missing entirely. The translator now sends all source forms in a single API call together with the target language's CLDR categories and number-range rules, and expands the output to every category the target language requires.
- Android `<plurals>` translation now uses the same CLDR-aware path instead of treating each `<item quantity="...">` as an unrelated string, so target languages get all their required quantity entries even when the source provides only `one` and `other`.
- Plural-translation cache key now includes the developer comment, custom instructions, and app context. Previously a cached plural translation could be reused even after the user changed their custom instructions or the surrounding context.

### Added
- Comprehensive test suite for metadata translation scenarios, covering character limits (warn/truncate/error), interactive previews, overwrite behavior, and untranslatable file copying.
- `localizerx/utils/plural_rules.py`: CLDR plural categories and number-range descriptions for ~50 languages (Slavic four-form, Arabic six-form, French/Brazilian Portuguese three-form, single-form CJK, etc.), used to build plural-translation prompts.
- Placeholder masking now also protects HTML/XML tags, `<![CDATA[...]]>` blocks, common backslash escape sequences (`\n`, `\t`, `\u00A0`, ...), and the URL portion of Markdown links (`[text](url)` — the link text stays translatable). This prevents the model from rewriting Android rich-text markup, JSON escapes, and link targets.

## [0.1.2] - 2026-03-21

### Added
- `--mark-empty` option to translate command to mark empty or whitespace-only strings as translated.
- Modern SPDX license format in `pyproject.toml`.

### Changed
- Updated default Gemini model to `gemini-3-flash-preview`.
- Updated default `batch_size` to 180 for better throughput.
- Increased maximum allowed `batch_size` to 500.
- Updated default `temperature` to 1.0.

### Fixed
- Regression in CLI where `mark_empty` parameter was missing from `main` callback.
- Test failures due to missing `mark_empty` parameter in `_process_file` calls.
- Mismatch between tests and new default configuration values.
- Linting issues (long lines) in CLI and IO modules.

## [0.1.1] - 2026-03-20

### Added
- Fastlane Frameit screenshot text translation support (`lrx frameit`).
- Command-specific configuration sections in `config.toml`.
- Improved placeholder masking for more complex variables.

### Fixed
- Bug in `.xcstrings` plural parsing for certain locales.
- Issue with character limit enforcement in metadata translation.

## [0.1.0] - 2026-03-15

### Added
- Initial release of LocalizerX.
- Support for Xcode String Catalogs (.xcstrings).
- Support for App Store metadata (fastlane).
- Support for Android strings.xml.
- Support for Chrome Extension locales.
- Support for frontend i18n JSON files.
- Support for screenshot text generation and translation.
