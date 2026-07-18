"""Minimal safety-event audit persistence."""

from uuid import UUID

from sqlalchemy import select

from app.models import SafetyEvent
from app.repositories.base import BaseRepository


class SafetyEventRepository(BaseRepository[SafetyEvent]):
    model = SafetyEvent

    async def create(
        self,
        *,
        conversation_id: UUID,
        category: str,
        severity: str,
        action_taken: str,
        message_id: UUID | None = None,
        participant_id: UUID | None = None,
    ) -> SafetyEvent:
        return await self.add(
            SafetyEvent(
                conversation_id=conversation_id,
                message_id=message_id,
                participant_id=participant_id,
                category=category,
                severity=severity,
                action_taken=action_taken,
            )
        )

    async def list_by_conversation(self, conversation_id: UUID) -> list[SafetyEvent]:
        statement = (
            select(SafetyEvent)
            .where(SafetyEvent.conversation_id == conversation_id)
            .order_by(SafetyEvent.created_at, SafetyEvent.id)
        )
        return list((await self.session.scalars(statement)).all())
