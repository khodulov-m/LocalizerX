from pathlib import Path

import pytest
from typer.testing import CliRunner

from localizerx.cli import app
from localizerx.cli.agent import AGENT_INSTRUCTIONS

runner = CliRunner()


def test_init_agent_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that init-agent creates the target file with instructions."""
    monkeypatch.chdir(tmp_path)

    # We use --file to bypass the interactive prompt
    result = runner.invoke(app, ["init-agent", "--file", "AGENT.md"])

    assert result.exit_code == 0
    assert "Created AGENT.md with LocalizerX instructions" in result.stdout

    agent_file = tmp_path / "AGENT.md"
    assert agent_file.exists()
    assert agent_file.read_text() == AGENT_INSTRUCTIONS


def test_init_agent_appends_to_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that init-agent appends to an existing file."""
    monkeypatch.chdir(tmp_path)

    target_file = tmp_path / ".cursorrules"
    target_file.write_text("Existing rules here.")

    result = runner.invoke(app, ["init-agent", "--file", ".cursorrules"])

    assert result.exit_code == 0
    assert "Appended LocalizerX instructions to .cursorrules" in result.stdout

    content = target_file.read_text()
    assert content.startswith("Existing rules here.")
    assert AGENT_INSTRUCTIONS in content


def test_init_agent_prevents_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that init-agent does not append if instructions already exist."""
    monkeypatch.chdir(tmp_path)

    target_file = tmp_path / ".clinerules"
    target_file.write_text(f"Some preamble\n\n{AGENT_INSTRUCTIONS}")

    result = runner.invoke(app, ["init-agent", "--file", ".clinerules"])

    assert result.exit_code == 0
    assert "Instructions already exist in .clinerules" in result.stdout

    # Content should not be doubled
    content = target_file.read_text()
    assert content.count("LocalizerX (lrx) Agent Instructions") == 1
