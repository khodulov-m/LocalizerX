"""Tests for fastlane frameit I/O operations."""

from __future__ import annotations

from localizerx.io.frameit import (
    ensure_framefile,
    read_frameit_catalog,
    read_strings_file,
    write_strings_file,
)


def test_read_strings_file(tmp_path):
    """Test reading a .strings file."""
    strings_file = tmp_path / "title.strings"
    content = '"Screen-1" = "Hello";\n"Screen-2" = "World";\n'
    strings_file.write_text(content, encoding="utf-8")

    data = read_strings_file(strings_file)
    assert data == {"Screen-1": "Hello", "Screen-2": "World"}


def test_write_strings_file(tmp_path):
    """Test writing a .strings file."""
    strings_file = tmp_path / "keyword.strings"
    data = {"Key-1": "Value 1", "Key-2": "Value 2"}

    write_strings_file(strings_file, data)
    content = strings_file.read_text(encoding="utf-8")

    assert '"Key-1" = "Value 1";' in content
    assert '"Key-2" = "Value 2";' in content


def test_ensure_framefile(tmp_path):
    """Test creating Framefile.json template."""
    ensure_framefile(tmp_path)
    framefile = tmp_path / "Framefile.json"

    assert framefile.exists()
    content = framefile.read_text()
    assert '"default":' in content
    assert '"data":' in content


def test_read_frameit_catalog(tmp_path):
    """Test reading the full frameit directory structure."""
    # Create structure
    en_dir = tmp_path / "en-US"
    en_dir.mkdir()
    (en_dir / "title.strings").write_text('"S1" = "Title";', encoding="utf-8")
    (en_dir / "keyword.strings").write_text('"S1" = "Keyword";', encoding="utf-8")

    fr_dir = tmp_path / "fr-FR"
    fr_dir.mkdir()
    (fr_dir / "title.strings").write_text('"S1" = "Titre";', encoding="utf-8")

    catalog = read_frameit_catalog(tmp_path, source_locale="en-US")

    assert catalog.source_locale == "en-US"
    en = catalog.get_locale("en-US")
    assert en is not None
    assert en.title_strings["S1"].value == "Title"
    assert en.keyword_strings["S1"].value == "Keyword"

    fr = catalog.get_locale("fr-FR")
    assert fr is not None
    assert fr.title_strings["S1"].value == "Titre"
    assert "S1" not in fr.keyword_strings
