"""Transactional participant joining and preference changes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_session_token, hash_token
from app.config import Settings
from app.models import (
    Conversation,
    ConversationStatus,
    Invitation,
    Participant,
    ParticipantRole,
    ParticipantSession,
)
from app.repositories import (
    ConversationRepository,
    InvitationRepository,
    ParticipantRepository,
    ParticipantSessionRepository,
)
from app.services.exceptions import (
    ConversationEndedError,
    ConversationFullError,
    ConversationNotFoundError,
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationRevokedError,
    ParticipantNotFoundError,
)


@dataclass(frozen=True, slots=True)
class JoinedConversation:
    """Entities and the one-time session credential created during a join."""

    conversation: Conversation
    participant: Participant
    participant_session: ParticipantSession
    session_token: str


class ParticipantService:
    """Own participant authorization, capacity rules, and join transactions."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def join_conversation(
        self,
        *,
        invitation_token_hash: str,
        expected_conversation_id: UUID | None = None,
        display_name: str,
        preferred_language: str,
        session_expires_at: datetime,
    ) -> JoinedConversation:
        session_token = generate_session_token()

        async with self.session.begin():
            invitations = InvitationRepository(self.session)
            conversations = ConversationRepository(self.session)
            participants = ParticipantRepository(self.session)
            participant_sessions = ParticipantSessionRepository(self.session)

            invitation = await invitations.get_by_token_hash(invitation_token_hash)
            if invitation is None:
                raise InvitationNotFoundError

            conversation = await conversations.get_by_id_for_update(
                invitation.conversation_id
            )
            if conversation is None:
                raise ConversationNotFoundError
            if (
                expected_conversation_id is not None
                and conversation.id != expected_conversation_id
            ):
                raise ConversationNotFoundError

            # A competing join may have changed the invitation while this
            # transaction waited for the conversation row lock.
            await invitations.refresh(invitation)
            self._validate_join_state(invitation, conversation)

            if await participants.count_by_conversation(conversation.id) >= 2:
                raise ConversationFullError

            participant = await participants.create(
                conversation_id=conversation.id,
                display_name=display_name,
                preferred_language=preferred_language,
                role=ParticipantRole.INVITEE,
            )
            participant_session = await participant_sessions.create(
                participant_id=participant.id,
                token_hash=hash_token(
                    session_token,
                    self._secret_value(self.settings.session_token_secret),
                ),
                expires_at=session_expires_at,
            )
            await invitations.mark_used(invitation)
            await conversations.set_active(conversation)

        return JoinedConversation(
            conversation=conversation,
            participant=participant,
            participant_session=participant_session,
            session_token=session_token,
        )

    async def update_language(
        self,
        *,
        conversation_id: UUID,
        participant_id: UUID,
        preferred_language: str,
    ) -> Participant:
        async with self.session.begin():
            repository = ParticipantRepository(self.session)
            participant = await repository.get_by_id(participant_id)
            if participant is None or participant.conversation_id != conversation_id:
                raise ParticipantNotFoundError
            await repository.update_preferred_language(participant, preferred_language)
        return participant

    @staticmethod
    def _validate_join_state(
        invitation: Invitation, conversation: Conversation
    ) -> None:
        now = datetime.now(UTC)
        if invitation.revoked_at is not None:
            raise InvitationRevokedError
        if invitation.used_at is not None:
            raise InvitationAlreadyUsedError
        if invitation.expires_at is not None and invitation.expires_at <= now:
            raise InvitationExpiredError
        if conversation.status is ConversationStatus.ENDED:
            raise ConversationEndedError
        if conversation.status is not ConversationStatus.WAITING:
            raise ConversationFullError

    @staticmethod
    def _secret_value(secret: SecretStr) -> str:
        return secret.get_secret_value()
