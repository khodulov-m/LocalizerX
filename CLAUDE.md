# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocalizerX (`lrx`, also `localizerx`) is a Python 3.10+ CLI for macOS that translates localization
files through the Gemini API: Xcode `.xcstrings`, fastlane/App Store metadata, App Store screenshot
texts and Frameit strings, Chrome Extension `_locales/`, Android `strings.xml` and frontend i18n
JSON. It keeps placeholders, plural rules and developer comments intact. The package version is in
`pyproject.toml`; `CHANGELOG.md` lists changes under `[Unreleased]`.

The agent skill `skills/localizerx/SKILL.md` (name `use-localizerx`) teaches other agents how to run
the CLI. Keep it in step with the commands and flags you change.

## Commands

```bash
GEMINI_API_KEY=test uv run python -m pytest        # the whole suite; needs any key value, see below
uv run python -m pytest tests/test_file.py::test_function
uv run --extra dev ruff check .                    # dev tools sit in an extra, plain `uv run` lacks them
uv run --extra dev black .                         # line length 100 (ruff and black)
uv run localizerx <command> --help                 # the commands and flags live in the CLI, not here
```

- **Tests need `GEMINI_API_KEY` set to any value**: about 30 CLI tests fail with "Gemini API key
  required" without it. No test may call the real API; mock the translator.
- **Lint is not clean on `master`**: `ruff check .` and `black --check .` report old findings. Do
  not mass-reformat; keep new and changed code clean.
- Real runs need a real `GEMINI_API_KEY`. User config: `~/.config/localizerx/config.toml` (per-command
  sections, `formality`, `custom_instructions`); cache: `~/.cache/localizerx`.

## Architecture

Clean Architecture: CLI (Typer) → use cases → ports → adapters.

- `localizerx/cli/`: one module per format or command group (`translate`, `delete`, `metadata`,
  `android`, `chrome`, `i18n`, `screenshots`, `frameit`, `agent`); commands are registered at the
  bottom of `cli/__init__.py`, which also holds `list`, `use`, `languages`, `cache-clear`.
- `localizerx/core/use_cases/`: per-format orchestrators, framework-agnostic.
  `core/ports/repository.py` is the cache port, `adapters/repository.py` the SQLite cache.
- `localizerx/io/`: lossless read/write per format. `localizerx/parser/`: Pydantic domain models.
- `localizerx/translator/`: `base.py` (abstract translator), `gemini_adapter.py` (async), and
  `*_prompts.py` (ASO prompts for metadata, screenshots, Chrome Web Store, Frameit).
- `localizerx/utils/`: `placeholders.py` (masking), `plural_rules.py` (CLDR categories),
  `formality.py` (T-V address), `limits.py` (App Store and Chrome Web Store character limits),
  `locale.py`, `context.py` (app context for prompts).
- `localizerx/config.py`: TOML config.

## Invariants

- **Lossless I/O**: read then write must reproduce the file exactly, adding only translations.
  Cover every I/O change with a round-trip test.
- **Placeholder masking**: `%@`, `{name}`, `$1`, HTML/XML tags, CDATA, escapes and Markdown link
  URLs are masked to `__PH_n__` before translation and restored after. Extend `placeholders.py`
  (and its tests) for a new syntax instead of patching prompts.
- **CLDR plurals**: for xcstrings and Android `<plurals>` one API call carries all source forms plus
  the target language's categories and number ranges, so `one`/`other` can grow into
  `one`/`few`/`many`/`other`. Do not split plural forms into separate calls.
- **Formality** (`--formality auto|formal|informal`, config field per command) is injected into
  every prompt builder that knows the target language; `auto` must leave prompts byte-identical to
  the pre-setting behaviour.
- **Cache keys** include formality, custom instructions and app context (plurals also the developer
  comment). A new prompt-affecting input must join the key, or old wording comes back stale.
- **Translator stays provider-agnostic** behind `translator/base.py`; keep Gemini specifics in
  `gemini_adapter.py`.
- **Character limits** (App Store, Chrome Web Store) are checked after translation; what happens to
  an over-limit field depends on the limit action (warn, or retry-shorten and truncate as the last
  resort). Keep the warning in the output whenever a field was changed.

## Workspace notes

- The workspace no longer translates its own app repos with `lrx` (the agent does it directly); the
  tool and the skill stay maintained for other users.
- This is a public repo: no personal paths, keys or private project names in code, docs or commits.
- Commits use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
