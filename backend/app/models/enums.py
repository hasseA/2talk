"""Application enums stored as constrained strings in PostgreSQL."""

from enum import StrEnum

from sqlalchemy import Enum as SQLAlchemyEnum


class ConversationStatus(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    ENDED = "ended"


class ParticipantRole(StrEnum):
    CREATOR = "creator"
    INVITEE = "invitee"


class MessageStatus(StrEnum):
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    BLOCKED = "blocked"


class ProcessingAttemptStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class MediationJobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEAD = "dead"


class GuidanceAudience(StrEnum):
    SENDER = "sender"
    RECIPIENT = "recipient"


class GuidanceType(StrEnum):
    COMMUNICATION_SUPPORT = "communication_support"
    CLARIFICATION = "clarification"
    DE_ESCALATION = "de_escalation"
    PAUSE_SUGGESTION = "pause_suggestion"
    BOUNDARY_NOTICE = "boundary_notice"
    SAFETY_NOTICE = "safety_notice"


class SummaryStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def constrained_enum(enum_class: type[StrEnum], *, name: str, length: int):
    """Map a Python enum to a validated VARCHAR without a native enum type."""
    return SQLAlchemyEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
        length=length,
    )
