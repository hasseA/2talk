"""Participant-scoped private-guidance persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models import GuidanceAudience, GuidanceType, PrivateGuidance
from app.repositories.base import BaseRepository


class PrivateGuidanceRepository(BaseRepository[PrivateGuidance]):
    model = PrivateGuidance

    async def create(
        self,
        *,
        conversation_id: UUID,
        message_id: UUID,
        participant_id: UUID,
        audience: GuidanceAudience,
        guidance_type: GuidanceType,
        guidance_text: str,
    ) -> PrivateGuidance:
        return await self.add(
            PrivateGuidance(
                conversation_id=conversation_id,
                message_id=message_id,
                participant_id=participant_id,
                audience=audience,
                guidance_type=guidance_type,
                guidance_text=guidance_text,
            )
        )

    async def list_for_participant(self, participant_id: UUID) -> list[PrivateGuidance]:
        statement = (
            select(PrivateGuidance)
            .where(PrivateGuidance.participant_id == participant_id)
            .order_by(PrivateGuidance.created_at, PrivateGuidance.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_for_participant_and_message(
        self, participant_id: UUID, message_id: UUID
    ) -> list[PrivateGuidance]:
        statement = (
            select(PrivateGuidance)
            .where(
                PrivateGuidance.participant_id == participant_id,
                PrivateGuidance.message_id == message_id,
            )
            .order_by(PrivateGuidance.created_at, PrivateGuidance.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def mark_seen(
        self, guidance: PrivateGuidance, *, seen_at: datetime | None = None
    ) -> PrivateGuidance:
        guidance.seen_at = seen_at or datetime.now(UTC)
        await self.session.flush()
        return guidance
