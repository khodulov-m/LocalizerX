# Changelog

All notable changes to this project will be documented in this file.

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
