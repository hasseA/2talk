"""Approved prompt loading behavior."""

from pathlib import Path

import pytest

from app.ai import AIConfigurationError, load_system_prompt


def test_prompt_loads_independently_of_current_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    prompt = load_system_prompt()

    assert "You are the AI communication mediator for 2talk." in prompt
    assert "Preserve meaning." in prompt


def test_missing_prompt_raises_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(AIConfigurationError, match="unavailable"):
        load_system_prompt(tmp_path / "missing.md")


def test_empty_prompt_is_rejected(tmp_path: Path) -> None:
    prompt_path = tmp_path / "empty.md"
    prompt_path.write_text("  \n", encoding="utf-8")

    with pytest.raises(AIConfigurationError, match="empty"):
        load_system_prompt(prompt_path)
