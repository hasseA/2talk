"""Conversation persistence and row-locking queries."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models import Conversation, ConversationStatus, Participant
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def create(
        self, *, title: str | None = None, description: str | None = None
    ) -> Conversation:
        return await self.add(Conversation(title=title, description=description))

    async def get_by_id_for_update(self, conversation_id: UUID) -> Conversation | None:
        statement = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def set_active(
        self,
        conversation: Conversation,
        *,
        activated_at: datetime | None = None,
    ) -> Conversation:
        conversation.status = ConversationStatus.ACTIVE
        conversation.activated_at = activated_at or datetime.now(UTC)
        await self.session.flush()
        return conversation

    async def set_ended(
        self, conversation: Conversation, *, ended_at: datetime | None = None
    ) -> Conversation:
        conversation.status = ConversationStatus.ENDED
        conversation.ended_at = ended_at or datetime.now(UTC)
        await self.session.flush()
        return conversation

    async def list_for_participant(self, participant_id: UUID) -> list[Conversation]:
        statement = (
            select(Conversation)
            .join(Participant, Participant.conversation_id == Conversation.id)
            .where(Participant.id == participant_id)
            .order_by(Conversation.created_at, Conversation.id)
        )
        return list((await self.session.scalars(statement)).all())
