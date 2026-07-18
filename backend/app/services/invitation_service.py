"""Invitation validation and redemption entry points."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_token
from app.config import Settings
from app.models import ConversationStatus, Invitation
from app.repositories import (
    ConversationRepository,
    InvitationRepository,
    ParticipantRepository,
)
from app.services.exceptions import (
    ConversationEndedError,
    ConversationFullError,
    ConversationNotFoundError,
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationRevokedError,
)
from app.services.participant_service import JoinedConversation, ParticipantService


@dataclass(frozen=True, slots=True)
class InvitationValidation:
    """Safe invitation state without token hashes or participant identities."""

    conversation_id: UUID
    title: str | None
    status: ConversationStatus
    expires_at: datetime | None


class InvitationService:
    """Apply invitation validity rules and delegate atomic joining."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def validate_invitation(self, invitation_token: str) -> InvitationValidation:
        token_hash = self._hash_invitation_token(invitation_token)
        async with self.session.begin():
            invitations = InvitationRepository(self.session)
            conversations = ConversationRepository(self.session)
            participants = ParticipantRepository(self.session)

            invitation = await invitations.get_by_token_hash(token_hash)
            if invitation is None:
                raise InvitationNotFoundError
            self._validate_token_state(invitation)

            conversation = await conversations.get_by_id(invitation.conversation_id)
            if conversation is None:
                raise ConversationNotFoundError
            if conversation.status is ConversationStatus.ENDED:
                raise ConversationEndedError
            if conversation.status is not ConversationStatus.WAITING:
                raise ConversationFullError
            if await participants.count_by_conversation(conversation.id) >= 2:
                raise ConversationFullError

        return InvitationValidation(
            conversation_id=conversation.id,
            title=conversation.title,
            status=conversation.status,
            expires_at=invitation.expires_at,
        )

    async def redeem_invitation(
        self,
        *,
        invitation_token: str,
        conversation_id: UUID | None = None,
        display_name: str,
        preferred_language: str,
        session_expires_at: datetime,
    ) -> JoinedConversation:
        participant_service = ParticipantService(self.session, self.settings)
        return await participant_service.join_conversation(
            invitation_token_hash=self._hash_invitation_token(invitation_token),
            expected_conversation_id=conversation_id,
            display_name=display_name,
            preferred_language=preferred_language,
            session_expires_at=session_expires_at,
        )

    def _hash_invitation_token(self, invitation_token: str) -> str:
        return hash_token(
            invitation_token,
            self.settings.invitation_token_secret.get_secret_value(),
        )

    @staticmethod
    def _validate_token_state(invitation: Invitation) -> None:
        if invitation.revoked_at is not None:
            raise InvitationRevokedError
        if invitation.used_at is not None:
            raise InvitationAlreadyUsedError
        if invitation.expires_at is not None and invitation.expires_at <= datetime.now(
            UTC
        ):
            raise InvitationExpiredError
