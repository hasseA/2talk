"""OpenAI Responses API adapter for strict mediation output."""

import json
from typing import Any

from openai import APITimeoutError, OpenAIError
from pydantic import ValidationError

from app.ai.exceptions import AIOutputValidationError, AIProviderError, AITimeoutError
from app.ai.models import MediationRequest, MediationResult
from app.ai.validation import validate_mediation_result


class OpenAIProvider:
    """Translate the provider-independent contract to the OpenAI SDK."""

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        system_prompt: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens

    async def mediate_message(self, request: MediationRequest) -> MediationResult:
        """Request a strict Pydantic response and validate domain invariants."""
        request_json = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=self._system_prompt,
                input=[{"role": "user", "content": request_json}],
                text_format=MediationResult,
                max_output_tokens=self._max_output_tokens,
                store=False,
                timeout=self._timeout_seconds,
            )
        except APITimeoutError as exc:
            raise AITimeoutError("The AI provider request timed out.") from exc
        except ValidationError as exc:
            raise AIOutputValidationError(
                "AI output failed mediation validation."
            ) from exc
        except OpenAIError as exc:
            raise AIProviderError("The AI provider request failed.") from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise AIOutputValidationError(
                "The AI provider returned no structured mediation result."
            )
        return validate_mediation_result(parsed, request=request)
