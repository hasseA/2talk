"""AI mediation processing-attempt model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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
from app.models.enums import ProcessingAttemptStatus, constrained_enum

if TYPE_CHECKING:
    from app.models.message import Message


class AIProcessingAttempt(Base):
    """Technical metadata for one AI mediation attempt."""

    __tablename__ = "ai_processing_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'rejected')",
            name="ai_processing_attempts_status_check",
        ),
        CheckConstraint(
            "attempt_number > 0", name="ai_processing_attempts_number_positive"
        ),
        UniqueConstraint(
            "message_id", "attempt_number", name="ai_processing_attempts_unique"
        ),
        Index("ai_processing_attempts_message_id_idx", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "messages.id", ondelete="CASCADE", name="ai_processing_attempts_message_fk"
        ),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ProcessingAttemptStatus] = mapped_column(
        constrained_enum(
            ProcessingAttemptStatus, name="processing_attempt_status", length=20
        ),
        nullable=False,
    )
    request_started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    request_completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)

    message: Mapped["Message"] = relationship(back_populates="processing_attempts")
