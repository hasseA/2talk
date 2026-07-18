"""Construction of the configured provider behind its abstraction."""

from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.ai.exceptions import AIConfigurationError
from app.ai.prompt_loader import load_system_prompt
from app.ai.provider import AIProvider
from app.ai.providers import OpenAIProvider
from app.config import Settings


def create_ai_provider(
    settings: Settings,
    *,
    client: Any | None = None,
    prompt_path: Path | None = None,
) -> AIProvider:
    """Build the configured OpenAI adapter without HTTP or database wiring."""
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key.strip():
        raise AIConfigurationError("OPENAI_API_KEY is required.")
    if not settings.openai_model.strip():
        raise AIConfigurationError("OPENAI_MODEL is required.")

    openai_client = client or AsyncOpenAI(
        api_key=api_key,
        timeout=settings.openai_timeout_seconds,
    )
    return OpenAIProvider(
        client=openai_client,
        model=settings.openai_model,
        system_prompt=load_system_prompt(prompt_path),
        timeout_seconds=settings.openai_timeout_seconds,
        max_output_tokens=settings.openai_max_output_tokens,
    )
