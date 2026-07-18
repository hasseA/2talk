"""Recipient-specific delivery persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models import MessageDelivery
from app.repositories.base import BaseRepository


class MessageDeliveryRepository(BaseRepository[MessageDelivery]):
    model = MessageDelivery

    async def create(
        self,
        *,
        message_id: UUID,
        recipient_id: UUID,
        delivered_at: datetime | None = None,
    ) -> MessageDelivery:
        return await self.add(
            MessageDelivery(
                message_id=message_id,
                recipient_id=recipient_id,
                delivered_at=delivered_at,
            )
        )

    async def get_for_message_and_recipient(
        self, message_id: UUID, recipient_id: UUID
    ) -> MessageDelivery | None:
        return await self.session.scalar(
            select(MessageDelivery).where(
                MessageDelivery.message_id == message_id,
                MessageDelivery.recipient_id == recipient_id,
            )
        )

    async def mark_seen(
        self, delivery: MessageDelivery, *, seen_at: datetime | None = None
    ) -> MessageDelivery:
        delivery.seen_at = seen_at or datetime.now(UTC)
        await self.session.flush()
        return delivery

    async def list_for_recipient(self, recipient_id: UUID) -> list[MessageDelivery]:
        statement = (
            select(MessageDelivery)
            .where(MessageDelivery.recipient_id == recipient_id)
            .order_by(MessageDelivery.delivered_at, MessageDelivery.id)
        )
        return list((await self.session.scalars(statement)).all())
