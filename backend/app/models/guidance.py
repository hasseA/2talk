"""Participant-private guidance model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import GuidanceAudience, GuidanceType, constrained_enum

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.participant import Participant


class PrivateGuidance(Base):
    """Guidance visible to exactly one participant."""

    __tablename__ = "private_guidance"
    __table_args__ = (
        CheckConstraint(
            "audience IN ('sender', 'recipient')",
            name="private_guidance_audience_check",
        ),
        CheckConstraint(
            "guidance_type IN ('communication_support', 'clarification', "
            "'de_escalation', 'pause_suggestion', 'boundary_notice', 'safety_notice')",
            name="private_guidance_type_check",
        ),
        CheckConstraint(
            "LENGTH(TRIM(guidance_text)) > 0",
            name="private_guidance_text_not_empty",
        ),
        Index(
            "private_guidance_participant_created_idx", "participant_id", "created_at"
        ),
        Index("private_guidance_message_id_idx", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
            name="private_guidance_conversation_fk",
        ),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "messages.id", ondelete="CASCADE", name="private_guidance_message_fk"
        ),
        nullable=False,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "participants.id",
            ondelete="CASCADE",
            name="private_guidance_participant_fk",
        ),
        nullable=False,
    )
    audience: Mapped[GuidanceAudience] = mapped_column(
        constrained_enum(GuidanceAudience, name="guidance_audience", length=20),
        nullable=False,
    )
    guidance_type: Mapped[GuidanceType] = mapped_column(
        constrained_enum(GuidanceType, name="guidance_type", length=40), nullable=False
    )
    guidance_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    conversation: Mapped["Conversation"] = relationship(
        back_populates="private_guidance"
    )
    message: Mapped["Message"] = relationship(back_populates="private_guidance")
    participant: Mapped["Participant"] = relationship(back_populates="private_guidance")
