"""Stable loading of the approved mediation system prompt."""

from pathlib import Path

from app.ai.exceptions import AIConfigurationError

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "05_AI_SYSTEM_PROMPT.md"
)


def load_system_prompt(path: Path | None = None) -> str:
    """Load the approved UTF-8 prompt without relying on the working directory."""
    prompt_path = path or DEFAULT_PROMPT_PATH
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AIConfigurationError(
            f"AI system prompt is unavailable at {prompt_path}."
        ) from exc
    if not prompt.strip():
        raise AIConfigurationError("AI system prompt is empty.")
    return prompt
