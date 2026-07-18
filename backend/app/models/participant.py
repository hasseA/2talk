"""Conversation participant model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ParticipantRole, constrained_enum

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.delivery import MessageDelivery
    from app.models.guidance import PrivateGuidance
    from app.models.message import Message
    from app.models.safety import SafetyEvent
    from app.models.session import ParticipantSession


class Participant(Base):
    """One of the two role-unique people in a conversation."""

    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint(
            "role IN ('creator', 'invitee')", name="participants_role_check"
        ),
        UniqueConstraint(
            "conversation_id", "role", name="participants_unique_role_per_conversation"
        ),
        CheckConstraint(
            "LENGTH(TRIM(display_name)) > 0",
            name="participants_display_name_not_empty",
        ),
        Index("participants_conversation_id_idx", "conversation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "conversations.id", ondelete="CASCADE", name="participants_conversation_fk"
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[ParticipantRole] = mapped_column(
        constrained_enum(ParticipantRole, name="participant_role", length=20),
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    sessions: Mapped[list["ParticipantSession"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    sent_messages: Mapped[list["Message"]] = relationship(
        back_populates="sender",
        cascade="all, delete-orphan",
        foreign_keys="Message.sender_id",
    )
    deliveries: Mapped[list["MessageDelivery"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )
    private_guidance: Mapped[list["PrivateGuidance"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    safety_events: Mapped[list["SafetyEvent"]] = relationship(
        back_populates="participant", foreign_keys="SafetyEvent.participant_id"
    )
