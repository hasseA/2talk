"""Provider-independent structured mediation input and output types."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LanguageCode = Literal["en", "sv", "fa"]


class MediationStatus(StrEnum):
    DELIVERED = "delivered"
    BLOCKED = "blocked"


class GuidanceType(StrEnum):
    COMMUNICATION_SUPPORT = "communication_support"
    CLARIFICATION = "clarification"
    DE_ESCALATION = "de_escalation"
    PAUSE_SUGGESTION = "pause_suggestion"
    BOUNDARY_NOTICE = "boundary_notice"
    SAFETY_NOTICE = "safety_notice"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConversationContextMessage(StrictModel):
    """One prior mediated message in chronological conversation context."""

    speaker: Literal["sender", "recipient"]
    mediated_message: str = Field(min_length=1, max_length=5000)
    language: LanguageCode

    @field_validator("mediated_message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("mediated_message must not be blank")
        return value


class MediationRequest(StrictModel):
    """Content-only request safe to pass to an AI provider."""

    original_message: str = Field(min_length=1, max_length=5000)
    sender_language: LanguageCode
    recipient_language: LanguageCode
    conversation_context: tuple[ConversationContextMessage, ...] = Field(
        default=(), max_length=50
    )

    @field_validator("original_message")
    @classmethod
    def reject_blank_original(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("original_message must not be blank")
        return value


class PrivateGuidanceResult(StrictModel):
    """One participant-private guidance item with documented vocabulary."""

    type: GuidanceType
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def reject_blank_guidance(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("guidance text must not be blank")
        return value


class MediationResult(StrictModel):
    """Strict structured output returned by a mediation provider."""

    status: MediationStatus
    mediated_message: str | None = Field(max_length=5000)
    delivered_language: LanguageCode | None
    sender_guidance: PrivateGuidanceResult | None
    recipient_guidance: PrivateGuidanceResult | None
    detected_language: str = Field(min_length=1, max_length=20)
    emotion: str | None = Field(max_length=100)
    communication_goal: str | None = Field(max_length=100)
    requires_pause: bool
    blocking_reason: str | None = Field(max_length=500)

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "MediationResult":
        if self.status is MediationStatus.DELIVERED:
            if self.mediated_message is None or not self.mediated_message.strip():
                raise ValueError("delivered results require mediated_message")
            if self.delivered_language is None:
                raise ValueError("delivered results require delivered_language")
            if self.blocking_reason is not None:
                raise ValueError("delivered results cannot include blocking_reason")
            return self

        if self.mediated_message is not None:
            raise ValueError("blocked results cannot include mediated_message")
        if self.delivered_language is not None:
            raise ValueError("blocked results cannot include delivered_language")
        if self.blocking_reason is None or not self.blocking_reason.strip():
            raise ValueError("blocked results require blocking_reason")
        if self.recipient_guidance is not None:
            raise ValueError("blocked results cannot include recipient_guidance")
        if (
            self.sender_guidance is not None
            and self.sender_guidance.type is not GuidanceType.SAFETY_NOTICE
        ):
            raise ValueError("blocked sender guidance must be a safety_notice")
        return self
