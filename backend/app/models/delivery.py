"""Recipient-specific message delivery model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.participant import Participant


class MessageDelivery(Base):
    """Delivery state for one mediated message recipient."""

    __tablename__ = "message_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "recipient_id", name="message_deliveries_unique"
        ),
        Index("message_deliveries_recipient_idx", "recipient_id", "delivered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "messages.id", ondelete="CASCADE", name="message_deliveries_message_fk"
        ),
        nullable=False,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "participants.id",
            ondelete="CASCADE",
            name="message_deliveries_recipient_fk",
        ),
        nullable=False,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    message: Mapped["Message"] = relationship(back_populates="deliveries")
    recipient: Mapped["Participant"] = relationship(back_populates="deliveries")
