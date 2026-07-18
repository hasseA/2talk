"""Participant persistence and membership queries."""

from uuid import UUID

from sqlalchemy import func, select

from app.models import Participant, ParticipantRole
from app.repositories.base import BaseRepository


class ParticipantRepository(BaseRepository[Participant]):
    model = Participant

    async def create(
        self,
        *,
        conversation_id: UUID,
        display_name: str,
        preferred_language: str,
        role: ParticipantRole,
    ) -> Participant:
        return await self.add(
            Participant(
                conversation_id=conversation_id,
                display_name=display_name,
                preferred_language=preferred_language,
                role=role,
            )
        )

    async def get_by_conversation_and_role(
        self, conversation_id: UUID, role: ParticipantRole
    ) -> Participant | None:
        return await self.session.scalar(
            select(Participant).where(
                Participant.conversation_id == conversation_id,
                Participant.role == role,
            )
        )

    async def list_by_conversation(self, conversation_id: UUID) -> list[Participant]:
        statement = (
            select(Participant)
            .where(Participant.conversation_id == conversation_id)
            .order_by(Participant.joined_at, Participant.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def count_by_conversation(self, conversation_id: UUID) -> int:
        statement = select(func.count(Participant.id)).where(
            Participant.conversation_id == conversation_id
        )
        return int((await self.session.scalar(statement)) or 0)

    async def participant_belongs_to_conversation(
        self, participant_id: UUID, conversation_id: UUID
    ) -> bool:
        statement = select(
            select(Participant.id)
            .where(
                Participant.id == participant_id,
                Participant.conversation_id == conversation_id,
            )
            .exists()
        )
        return bool(await self.session.scalar(statement))

    async def get_other_participant(
        self, conversation_id: UUID, participant_id: UUID
    ) -> Participant | None:
        statement = select(Participant).where(
            Participant.conversation_id == conversation_id,
            Participant.id != participant_id,
        )
        return await self.session.scalar(statement)

    async def update_preferred_language(
        self, participant: Participant, preferred_language: str
    ) -> Participant:
        participant.preferred_language = preferred_language
        await self.session.flush()
        return participant
