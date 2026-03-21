import json

from localizerx.cli.translate import _process_file
from localizerx.config import Config


def test_remove_language_xcstrings(tmp_path):
    # Create a dummy xcstrings file
    content = {
        "sourceLanguage": "en",
        "strings": {
            "key1": {
                "localizations": {
                    "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                    "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                }
            }
        },
        "version": "1.0",
    }
    file_path = tmp_path / "Localizable.xcstrings"
    file_path.write_text(json.dumps(content))

    # Process removal of 'fr'
    config = Config()
    _process_file(
        file_path=file_path,
        source_lang="en",
        target_langs=[],
        remove_langs=["fr"],
        config=config,
        dry_run=False,
        preview=False,
        overwrite=False,
        backup=False,
        batch_size=None,
        model=None,
        temperature=None,
        custom_prompt=None,
        no_app_context=True,
        refresh=False,
        mark_empty=False,
    )
    # Read back and verify
    with open(file_path, "r") as f:
        updated_content = json.load(f)

    assert "fr" not in updated_content["strings"]["key1"]["localizations"]
    assert "de" in updated_content["strings"]["key1"]["localizations"]
    assert (
        updated_content["strings"]["key1"]["localizations"]["de"]["stringUnit"]["value"] == "Hallo"
    )


def test_remove_multiple_languages_xcstrings(tmp_path):
    # Create a dummy xcstrings file
    content = {
        "sourceLanguage": "en",
        "strings": {
            "key1": {
                "localizations": {
                    "fr": {"stringUnit": {"state": "translated", "value": "Bonjour"}},
                    "de": {"stringUnit": {"state": "translated", "value": "Hallo"}},
                    "it": {"stringUnit": {"state": "translated", "value": "Ciao"}},
                }
            }
        },
        "version": "1.0",
    }
    file_path = tmp_path / "Localizable.xcstrings"
    file_path.write_text(json.dumps(content))

    # Process removal of 'fr' and 'it'
    config = Config()
    _process_file(
        file_path=file_path,
        source_lang="en",
        target_langs=[],
        remove_langs=["fr", "it"],
        config=config,
        dry_run=False,
        preview=False,
        overwrite=False,
        backup=False,
        batch_size=None,
        model=None,
        temperature=None,
        custom_prompt=None,
        no_app_context=True,
        refresh=False,
        mark_empty=False,
    )
    # Read back and verify
    with open(file_path, "r") as f:
        updated_content = json.load(f)

    assert "fr" not in updated_content["strings"]["key1"]["localizations"]
    assert "it" not in updated_content["strings"]["key1"]["localizations"]
    assert "de" in updated_content["strings"]["key1"]["localizations"]
