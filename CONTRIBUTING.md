# Contributing to LocalizerX

Thank you for your interest in contributing. This guide covers everything you need to get
started, from environment setup through to submitting a pull request.

---

## 1. Getting Started

**Requirements:** Python 3.10+, macOS.

```bash
# Clone the repository
git clone https://github.com/localizerx/localizerx.git
cd localizerx

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

Dev dependencies (`pytest`, `pytest-asyncio`, `ruff`, `black`) are declared under
`[project.optional-dependencies] dev` in `pyproject.toml`. The editable install above
pulls all of them in.

---

## 2. Project Structure

```
localizerx/
├── cli/                  # Typer CLI command definitions
├── io/                   # File I/O: xcstrings, metadata, extensions, i18n, android
├── parser/               # Data models and parsing logic
├── translator/           # Translation provider interface and adapters
│   ├── base.py           # Abstract Translator interface (see section 5)
│   └── gemini_adapter.py # Gemini API implementation
└── utils/                # Shared utilities (placeholders, locales, limits)

tests/                    # All test files live here
pyproject.toml            # Project metadata, dependencies, and tool configuration
```

Key design invariants that the codebase relies on:

- **Lossless parsing:** a `read` followed by a `write` must preserve the original file
  structure exactly. Only translation entries are added.
- **Placeholder masking:** placeholders (`%@`, `%d`, `{name}`, `$NAME$`, etc.) are
  replaced with neutral tokens (`__PH_1__`, `__PH_2__`, ...) before any text reaches a
  translation API, then restored afterward.
- **SQLite caching:** translations are cached locally with the key
  `(src_lang, tgt_lang, text_hash)` to avoid redundant API calls.

---

## 3. Development Workflow

Three checks must pass before a PR is opened. Run them in this order:

```bash
# 1. Lint
ruff check .

# 2. Format
black .

# 3. Test
pytest
```

All three are configured in `pyproject.toml`. If `ruff` or `black` report issues,
fix them before pushing. CI will enforce the same checks.

To run a single test in isolation:

```bash
pytest tests/test_file.py::TestClassName::test_method
```

---

## 4. Writing Tests

All tests live in the `tests/` directory. The project uses `pytest` with
`asyncio_mode = auto`, so any `async def test_*` function is picked up and run
without an explicit `@pytest.mark.asyncio` decorator (though adding one is harmless
and is done in parts of the existing suite for clarity).

**Tests must not require a live API key.** The `GEMINI_API_KEY` environment variable
should never be read by the test suite. Where a translator instance is needed, either
construct one with a fake key and mock the HTTP call, or mock at a higher level.
Both patterns appear in the existing tests:

```python
# Pattern A: Instantiate with a fake key, then mock the internal API call.
# Useful for testing response-parsing logic in the adapter itself.

from unittest.mock import AsyncMock, patch
from localizerx.translator.gemini_adapter import GeminiTranslator
from localizerx.translator.base import TranslationRequest


def _make_translator() -> GeminiTranslator:
    return GeminiTranslator(api_key="fake-key")


async def test_batch_translation():
    translator = _make_translator()
    requests = [TranslationRequest(key="greeting", text="Hello")]

    with patch.object(translator, "_call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = "1. Bonjour"
        results = await translator.translate_batch(requests, "en", "fr")

    assert results[0].translated == "Bonjour"
```

```python
# Pattern B: Use pytest fixtures to create temporary files on disk.
# Useful for testing I/O round-trips (read -> write -> read).

import json
import tempfile
from pathlib import Path
import pytest
from localizerx.io.xcstrings import read_xcstrings


@pytest.fixture
def xcstrings_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xcstrings", delete=False) as f:
        json.dump({"sourceLanguage": "en", "version": "1.0", "strings": {}}, f)
        f.flush()
        yield Path(f.name)


def test_read_empty_catalog(xcstrings_file):
    catalog = read_xcstrings(xcstrings_file)
    assert catalog.source_language == "en"
    assert len(catalog.strings) == 0
```

Group related assertions into classes (e.g., `TestMaskPlaceholders`,
`TestReadXcstrings`). Name test methods so that a failure message is self-explanatory
without reading the body.

---

## 5. Adding a New Translation Provider

The translator layer is intentionally provider-agnostic. To add a new provider:

1. Read the abstract interface in `localizerx/translator/base.py`. A provider must
   implement three methods:

   - `translate_text` -- translate a single string.
   - `translate_batch` -- translate a list of `TranslationRequest` objects and return a
     same-ordered list of `TranslationResult` objects.
   - `close` -- release any open HTTP connections or other resources.

   `translate_batch_stream` has a default implementation that calls `translate_batch`
   and yields results one at a time. Override it only if your provider supports true
   streaming.

2. Create a new module under `localizerx/translator/` (e.g., `openai_adapter.py`).
   Model your class on `GeminiTranslator` in `gemini_adapter.py`:

```python
from .base import TranslationRequest, TranslationResult, Translator


class OpenAITranslator(Translator):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    async def translate_text(
        self, text: str, source_lang: str, target_lang: str, context: str | None = None
    ) -> str:
        # Call the OpenAI API here.
        ...

    async def translate_batch(
        self,
        requests: list[TranslationRequest],
        source_lang: str,
        target_lang: str,
    ) -> list[TranslationResult]:
        # Translate each request, return results in the same order.
        ...

    async def close(self) -> None:
        # Clean up (e.g., close an httpx.AsyncClient).
        ...
```

3. Wire the new provider into the CLI if you want it selectable via a flag or config
   option. Update `localizerx/cli/` accordingly.

4. Write tests using a fake API key and mocked HTTP calls (see section 4). Do not
   require a live key in CI.

---

## 6. Submitting a Pull Request

1. Fork the repository and create a branch from `master`.

2. Use one of these prefixes for your branch name:

   | Prefix      | Use for                                    |
   |-------------|--------------------------------------------|
   | `feature/*` | New functionality                          |
   | `fix/*`     | Bug fixes                                  |
   | `docs/*`    | Documentation-only changes                 |

   Example: `feature/add-openai-provider`, `fix/placeholder-round-trip`, `docs/update-readme`.

3. Keep commits focused. One logical change per commit. Reference the related GitHub
   issue in the commit message when applicable (e.g., `fix #42`).

4. Before opening the PR, verify that lint, formatting, and tests all pass locally
   (see section 3).

5. Open the PR against `master`. Describe what changed and why. Link the issue if one
   exists.

---

## 7. Code Style

| Tool    | Config location               | Key settings                        |
|---------|-------------------------------|-------------------------------------|
| `ruff`  | `pyproject.toml` `[tool.ruff]`  | line-length 100, rules E/F/I/W, target py310 |
| `black` | `pyproject.toml` `[tool.black]` | line-length 100, target py310       |

Both tools target Python 3.10. Line length is 100 characters across the board. The
`[tool.ruff.lint.per-file-ignores]` section in `pyproject.toml` exempts prompt template
files from E501 (long lines inside triple-quoted strings); do not add similar exemptions
without a clear justification.

Use `from __future__ import annotations` at the top of every module. This is the
convention followed throughout the codebase and allows forward references in type
annotations without quoting.
