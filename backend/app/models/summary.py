"""Conversation summary model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import SummaryStatus, constrained_enum

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class ConversationSummary(Base):
    """One structured current summary for a conversation."""

    __tablename__ = "conversation_summaries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="conversation_summaries_status_check",
        ),
        UniqueConstraint(
            "conversation_id", name="conversation_summaries_one_per_conversation"
        ),
        Index("conversation_summaries_status_idx", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
            name="conversation_summaries_conversation_fk",
        ),
        nullable=False,
    )
    status: Mapped[SummaryStatus] = mapped_column(
        constrained_enum(SummaryStatus, name="summary_status", length=20),
        nullable=False,
        default=SummaryStatus.PROCESSING,
        server_default=SummaryStatus.PROCESSING.value,
    )
    main_topics: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    agreements: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    unresolved_issues: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    boundaries: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    next_steps: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    notice: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    conversation: Mapped["Conversation"] = relationship(back_populates="summaries")
