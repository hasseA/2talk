"""Participant session hash lookups and lifecycle persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models import ParticipantSession
from app.repositories.base import BaseRepository


class ParticipantSessionRepository(BaseRepository[ParticipantSession]):
    model = ParticipantSession

    async def create(
        self,
        *,
        participant_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> ParticipantSession:
        return await self.add(
            ParticipantSession(
                participant_id=participant_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

    async def get_by_token_hash(self, token_hash: str) -> ParticipantSession | None:
        return await self.session.scalar(
            select(ParticipantSession).where(
                ParticipantSession.token_hash == token_hash
            )
        )

    async def get_valid_by_token_hash(
        self, token_hash: str, *, now: datetime | None = None
    ) -> ParticipantSession | None:
        current_time = now or datetime.now(UTC)
        statement = select(ParticipantSession).where(
            ParticipantSession.token_hash == token_hash,
            ParticipantSession.revoked_at.is_(None),
            ParticipantSession.expires_at > current_time,
        )
        return await self.session.scalar(statement)

    async def revoke(
        self,
        participant_session: ParticipantSession,
        *,
        revoked_at: datetime | None = None,
    ) -> ParticipantSession:
        participant_session.revoked_at = revoked_at or datetime.now(UTC)
        await self.session.flush()
        return participant_session

    async def update_last_used(
        self,
        participant_session: ParticipantSession,
        *,
        last_used_at: datetime | None = None,
    ) -> ParticipantSession:
        participant_session.last_used_at = last_used_at or datetime.now(UTC)
        await self.session.flush()
        return participant_session
