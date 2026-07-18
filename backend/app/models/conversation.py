"""Conversation model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ConversationStatus, constrained_enum

if TYPE_CHECKING:
    from app.models.guidance import PrivateGuidance
    from app.models.invitation import Invitation
    from app.models.message import Message
    from app.models.participant import Participant
    from app.models.safety import SafetyEvent
    from app.models.summary import ConversationSummary


class Conversation(Base):
    """A private conversation between at most two role-unique participants."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'active', 'ended')",
            name="conversations_status_check",
        ),
        CheckConstraint(
            "activated_at IS NULL OR status IN ('active', 'ended')",
            name="conversations_activated_state_check",
        ),
        CheckConstraint(
            "ended_at IS NULL OR status = 'ended'",
            name="conversations_ended_state_check",
        ),
        Index("conversations_status_idx", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[ConversationStatus] = mapped_column(
        constrained_enum(ConversationStatus, name="conversation_status", length=20),
        nullable=False,
        default=ConversationStatus.WAITING,
        server_default=ConversationStatus.WAITING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    private_guidance: Mapped[list["PrivateGuidance"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["ConversationSummary"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    safety_events: Mapped[list["SafetyEvent"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
