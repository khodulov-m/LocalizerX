"""Tests for fastlane frameit CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from localizerx.cli import app

runner = CliRunner()


def test_frameit_init(tmp_path):
    """Test that frameit creates a template if source locale is missing."""
    # Move to tmp_path to test relative path detection or pass it explicitly
    screenshots_dir = tmp_path / "fastlane" / "screenshots"

    result = runner.invoke(app, ["frameit", "--path", str(screenshots_dir), "--to", "fr-FR"])

    assert "Creating template..." in result.stdout
    assert (screenshots_dir / "Framefile.json").exists()
    assert (screenshots_dir / "en-US" / "title.strings").exists()
    assert (screenshots_dir / "en-US" / "keyword.strings").exists()


def test_frameit_detect_path(tmp_path, monkeypatch):
    """Test path detection for frameit."""
    # Create the directory structure
    screenshots_dir = tmp_path / "fastlane" / "screenshots"
    screenshots_dir.mkdir(parents=True)
    (screenshots_dir / "Framefile.json").write_text("{}")

    # Create source locale dir so it doesn't trigger "Creating template" logic
    en_dir = screenshots_dir / "en-US"
    en_dir.mkdir()
    (en_dir / "title.strings").write_text('"S1" = "Hello";')

    # Change current working directory to tmp_path
    monkeypatch.chdir(tmp_path)

    # Use a mock GEMINI_API_KEY so config loading doesn't fail
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")

    result = runner.invoke(app, ["frameit", "--to", "fr-FR"])
    
    # Check for Frameit path without being too strict about newlines
    assert "Frameit path:" in result.stdout
    assert "fastlane/screenshots" in result.stdout.replace("\n", "")
    assert "Source locale: en-US" in result.stdout
