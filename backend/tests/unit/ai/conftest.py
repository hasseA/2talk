"""Shared structured mediation test values."""

from collections.abc import Callable

import pytest

from app.ai import MediationRequest


@pytest.fixture
def mediation_request() -> MediationRequest:
    return MediationRequest(
        original_message="Jag behöver en paus.",
        sender_language="sv",
        recipient_language="en",
        conversation_context=(),
    )


@pytest.fixture
def valid_result_data() -> Callable[[], dict[str, object]]:
    def build() -> dict[str, object]:
        return {
            "status": "delivered",
            "mediated_message": "I need a break.",
            "delivered_language": "en",
            "sender_guidance": {
                "type": "boundary_notice",
                "text": "Your boundary remains clear.",
            },
            "recipient_guidance": None,
            "detected_language": "sv",
            "emotion": "overwhelmed",
            "communication_goal": "request_pause",
            "requires_pause": True,
            "blocking_reason": None,
        }

    return build
