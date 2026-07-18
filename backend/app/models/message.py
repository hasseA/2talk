"""Mediated message model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import MessageStatus, constrained_enum

if TYPE_CHECKING:
    from app.models.attempt import AIProcessingAttempt
    from app.models.conversation import Conversation
    from app.models.delivery import MessageDelivery
    from app.models.guidance import PrivateGuidance
    from app.models.mediation_job import AIMediationJob
    from app.models.participant import Participant
    from app.models.safety import SafetyEvent


class Message(Base):
    """Original and mediated forms of one participant message."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'delivered', 'failed', 'blocked')",
            name="messages_status_check",
        ),
        CheckConstraint(
            "LENGTH(TRIM(original_message)) > 0", name="messages_original_not_empty"
        ),
        CheckConstraint("retry_count >= 0", name="messages_retry_count_nonnegative"),
        UniqueConstraint(
            "conversation_id",
            "sender_id",
            "client_message_id",
            name="messages_client_id_unique",
        ),
        CheckConstraint(
            "status <> 'delivered' OR "
            "(mediated_message IS NOT NULL AND delivered_at IS NOT NULL)",
            name="messages_delivery_content_check",
        ),
        Index("messages_conversation_created_idx", "conversation_id", "created_at"),
        Index("messages_sender_id_idx", "sender_id"),
        Index("messages_status_idx", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "conversations.id", ondelete="CASCADE", name="messages_conversation_fk"
        ),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE", name="messages_sender_fk"),
        nullable=False,
    )
    client_message_id: Mapped[str] = mapped_column(String(100), nullable=False)
    original_message: Mapped[str] = mapped_column(Text, nullable=False)
    original_language: Mapped[str | None] = mapped_column(String(20))
    mediated_message: Mapped[str | None] = mapped_column(Text)
    delivered_language: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[MessageStatus] = mapped_column(
        constrained_enum(MessageStatus, name="message_status", length=20),
        nullable=False,
        default=MessageStatus.PROCESSING,
        server_default=MessageStatus.PROCESSING.value,
    )
    communication_goal: Mapped[str | None] = mapped_column(String(100))
    detected_emotion: Mapped[str | None] = mapped_column(String(100))
    requires_pause: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    failure_code: Mapped[str | None] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    mediated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["Participant"] = relationship(
        back_populates="sent_messages", foreign_keys=[sender_id]
    )
    deliveries: Mapped[list["MessageDelivery"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    processing_attempts: Mapped[list["AIProcessingAttempt"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    mediation_job: Mapped["AIMediationJob | None"] = relationship(
        back_populates="message", cascade="all, delete-orphan", uselist=False
    )
    private_guidance: Mapped[list["PrivateGuidance"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="message")
