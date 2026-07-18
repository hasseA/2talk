"""Deterministic validation for provider mediation output."""

from typing import Any

from pydantic import ValidationError

from app.ai.exceptions import AIOutputValidationError
from app.ai.models import MediationRequest, MediationResult, MediationStatus


def validate_mediation_result(
    value: Any, *, request: MediationRequest | None = None
) -> MediationResult:
    """Validate structure plus request-dependent delivery invariants."""
    try:
        result = (
            value
            if isinstance(value, MediationResult)
            else MediationResult.model_validate(value)
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise AIOutputValidationError("AI output failed mediation validation.") from exc

    if (
        request is not None
        and result.status is MediationStatus.DELIVERED
        and result.delivered_language != request.recipient_language
    ):
        raise AIOutputValidationError(
            "AI output language does not match the recipient language."
        )
    return result
