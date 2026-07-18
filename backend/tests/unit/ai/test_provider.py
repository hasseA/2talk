"""OpenAI adapter and replaceable provider-interface behavior."""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from app.ai import (
    AIOutputValidationError,
    AIProvider,
    AIProviderError,
    AITimeoutError,
    MediationRequest,
    MediationResult,
    create_ai_provider,
)
from app.ai.providers import OpenAIProvider
from app.config import Settings


class StubResponses:
    def __init__(
        self, *, parsed: object = None, error: Exception | None = None
    ) -> None:
        self.parsed = parsed
        self.error = error
        self.kwargs: dict[str, Any] | None = None

    async def parse(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class StubClient:
    def __init__(self, responses: StubResponses) -> None:
        self.responses = responses


def _provider(responses: StubResponses) -> OpenAIProvider:
    return OpenAIProvider(
        client=StubClient(responses),
        model="test-model",
        system_prompt="approved prompt",
        timeout_seconds=12.0,
        max_output_tokens=800,
    )


@pytest.mark.asyncio
async def test_openai_provider_uses_strict_parsed_output(
    mediation_request: MediationRequest,
    valid_result_data: Callable[[], dict[str, object]],
) -> None:
    parsed = MediationResult.model_validate(valid_result_data())
    responses = StubResponses(parsed=parsed)

    result = await _provider(responses).mediate_message(mediation_request)

    assert result == parsed
    assert responses.kwargs is not None
    assert responses.kwargs["text_format"] is MediationResult
    assert responses.kwargs["store"] is False
    assert responses.kwargs["timeout"] == 12.0


@pytest.mark.asyncio
async def test_timeout_maps_to_ai_timeout_error(
    mediation_request: MediationRequest,
) -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    responses = StubResponses(error=APITimeoutError(request))

    with pytest.raises(AITimeoutError, match="timed out"):
        await _provider(responses).mediate_message(mediation_request)


@pytest.mark.asyncio
async def test_sdk_failure_maps_without_exposing_secret(
    mediation_request: MediationRequest,
) -> None:
    secret = "sk-never-expose-this"
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    responses = StubResponses(
        error=APIConnectionError(message=f"failure {secret}", request=request)
    )

    with pytest.raises(AIProviderError) as raised:
        await _provider(responses).mediate_message(mediation_request)

    assert secret not in str(raised.value)


@pytest.mark.asyncio
async def test_invalid_provider_response_maps_to_output_validation_error(
    mediation_request: MediationRequest,
) -> None:
    responses = StubResponses(parsed={"status": "delivered"})

    with pytest.raises(AIOutputValidationError):
        await _provider(responses).mediate_message(mediation_request)


@pytest.mark.asyncio
async def test_missing_parsed_response_is_invalid(
    mediation_request: MediationRequest,
) -> None:
    with pytest.raises(AIOutputValidationError, match="no structured"):
        await _provider(StubResponses()).mediate_message(mediation_request)


@pytest.mark.asyncio
async def test_provider_interface_can_be_replaced_by_fake(
    mediation_request: MediationRequest,
    valid_result_data: Callable[[], dict[str, object]],
) -> None:
    expected = MediationResult.model_validate(valid_result_data())

    class FakeProvider:
        async def mediate_message(self, request: MediationRequest) -> MediationResult:
            assert request == mediation_request
            return expected

    provider: AIProvider = FakeProvider()
    assert isinstance(provider, AIProvider)
    assert await provider.mediate_message(mediation_request) == expected


def test_factory_uses_typed_settings_and_injected_client(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("approved", encoding="utf-8")
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://unused/unused_test",
        openai_api_key="test-only-key",
        openai_model="test-model",
        openai_timeout_seconds=9,
        openai_max_output_tokens=700,
        session_token_secret="session-secret",
        invitation_token_secret="invitation-secret",
    )

    provider = create_ai_provider(
        settings,
        client=StubClient(StubResponses()),
        prompt_path=prompt_path,
    )

    assert isinstance(provider, AIProvider)
