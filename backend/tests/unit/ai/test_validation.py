"""Strict mediation output validation."""

from collections.abc import Callable

import pytest

from app.ai import (
    AIOutputValidationError,
    GuidanceType,
    MediationRequest,
    MediationStatus,
    validate_mediation_result,
)


def test_valid_structured_result_is_accepted(
    mediation_request: MediationRequest,
    valid_result_data: Callable[[], dict[str, object]],
) -> None:
    result = validate_mediation_result(valid_result_data(), request=mediation_request)

    assert result.status is MediationStatus.DELIVERED
    assert result.sender_guidance is not None
    assert result.sender_guidance.type is GuidanceType.BOUNDARY_NOTICE


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data.update({"unexpected": "field"}),
        lambda data: data.pop("detected_language"),
        lambda data: data.update({"status": "unknown"}),
        lambda data: data.update({"mediated_message": None}),
        lambda data: data.update({"mediated_message": "x" * 5001}),
        lambda data: data.update(
            {"sender_guidance": {"type": "clarification", "text": "   "}}
        ),
    ],
)
def test_invalid_delivered_output_is_rejected(
    change: Callable[[dict[str, object]], object],
    valid_result_data: Callable[[], dict[str, object]],
) -> None:
    data = valid_result_data()
    change(data)

    with pytest.raises(AIOutputValidationError):
        validate_mediation_result(data)


def test_delivered_language_must_match_recipient(
    mediation_request: MediationRequest,
    valid_result_data: Callable[[], dict[str, object]],
) -> None:
    data = valid_result_data()
    data["delivered_language"] = "fa"

    with pytest.raises(AIOutputValidationError, match="recipient language"):
        validate_mediation_result(data, request=mediation_request)


def test_valid_blocked_result_is_accepted() -> None:
    result = validate_mediation_result(
        {
            "status": "blocked",
            "mediated_message": None,
            "delivered_language": None,
            "sender_guidance": {
                "type": "safety_notice",
                "text": "This message cannot be delivered safely.",
            },
            "recipient_guidance": None,
            "detected_language": "en",
            "emotion": None,
            "communication_goal": None,
            "requires_pause": True,
            "blocking_reason": "credible_threat",
        }
    )

    assert result.status is MediationStatus.BLOCKED
    assert result.mediated_message is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mediated_message", "must not be delivered"),
        ("delivered_language", "en"),
        ("blocking_reason", None),
        (
            "recipient_guidance",
            {"type": "safety_notice", "text": "recipient guidance"},
        ),
        (
            "sender_guidance",
            {"type": "clarification", "text": "wrong guidance type"},
        ),
    ],
)
def test_blocked_result_consistency_is_enforced(field: str, value: object) -> None:
    data: dict[str, object] = {
        "status": "blocked",
        "mediated_message": None,
        "delivered_language": None,
        "sender_guidance": None,
        "recipient_guidance": None,
        "detected_language": "en",
        "emotion": None,
        "communication_goal": None,
        "requires_pause": True,
        "blocking_reason": "safety_policy",
    }
    data[field] = value

    with pytest.raises(AIOutputValidationError):
        validate_mediation_result(data)
