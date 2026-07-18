"""Invitation hash lookups and lifecycle persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select

from app.models import Invitation
from app.repositories.base import BaseRepository


class InvitationRepository(BaseRepository[Invitation]):
    model = Invitation

    async def create(
        self,
        *,
        conversation_id: UUID,
        token_hash: str,
        expires_at: datetime | None = None,
    ) -> Invitation:
        return await self.add(
            Invitation(
                conversation_id=conversation_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        return await self.session.scalar(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )

    async def get_valid_by_token_hash(
        self, token_hash: str, *, now: datetime | None = None
    ) -> Invitation | None:
        current_time = now or datetime.now(UTC)
        statement = select(Invitation).where(
            Invitation.token_hash == token_hash,
            Invitation.used_at.is_(None),
            Invitation.revoked_at.is_(None),
            or_(Invitation.expires_at.is_(None), Invitation.expires_at > current_time),
        )
        return await self.session.scalar(statement)

    async def mark_used(
        self, invitation: Invitation, *, used_at: datetime | None = None
    ) -> Invitation:
        invitation.used_at = used_at or datetime.now(UTC)
        await self.session.flush()
        return invitation

    async def revoke(
        self, invitation: Invitation, *, revoked_at: datetime | None = None
    ) -> Invitation:
        invitation.revoked_at = revoked_at or datetime.now(UTC)
        await self.session.flush()
        return invitation
