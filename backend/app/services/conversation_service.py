"""Transactional conversation creation and state transitions."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_invitation_token, generate_session_token, hash_token
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
    ConversationNotFoundError,
    ConversationStateError,
)


@dataclass(frozen=True, slots=True)
class CreatedConversation:
    """Entities and one-time raw credentials created atomically."""

    conversation: Conversation
    creator: Participant
    invitation: Invitation
    participant_session: ParticipantSession
    invitation_token: str
    session_token: str


class ConversationService:
    """Own conversation-level transactions and state rules."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def create_conversation(
        self,
        *,
        display_name: str,
        preferred_language: str,
        session_expires_at: datetime,
        title: str | None = None,
        description: str | None = None,
        invitation_expires_at: datetime | None = None,
    ) -> CreatedConversation:
        invitation_token = generate_invitation_token()
        session_token = generate_session_token()

        async with self.session.begin():
            conversations = ConversationRepository(self.session)
            participants = ParticipantRepository(self.session)
            invitations = InvitationRepository(self.session)
            participant_sessions = ParticipantSessionRepository(self.session)

            conversation = await conversations.create(
                title=title, description=description
            )
            creator = await participants.create(
                conversation_id=conversation.id,
                display_name=display_name,
                preferred_language=preferred_language,
                role=ParticipantRole.CREATOR,
            )
            invitation = await invitations.create(
                conversation_id=conversation.id,
                token_hash=hash_token(
                    invitation_token,
                    self._secret_value(self.settings.invitation_token_secret),
                ),
                expires_at=invitation_expires_at,
            )
            participant_session = await participant_sessions.create(
                participant_id=creator.id,
                token_hash=hash_token(
                    session_token,
                    self._secret_value(self.settings.session_token_secret),
                ),
                expires_at=session_expires_at,
            )

        return CreatedConversation(
            conversation=conversation,
            creator=creator,
            invitation=invitation,
            participant_session=participant_session,
            invitation_token=invitation_token,
            session_token=session_token,
        )

    async def activate_conversation(self, conversation_id: UUID) -> Conversation:
        async with self.session.begin():
            repository = ConversationRepository(self.session)
            participants = ParticipantRepository(self.session)
            conversation = await repository.get_by_id_for_update(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError
            if conversation.status is ConversationStatus.ENDED:
                raise ConversationEndedError
            if conversation.status is not ConversationStatus.WAITING:
                raise ConversationStateError
            if await participants.count_by_conversation(conversation_id) != 2:
                raise ConversationStateError
            await repository.set_active(conversation)
        return conversation

    async def end_conversation(self, conversation_id: UUID) -> Conversation:
        async with self.session.begin():
            repository = ConversationRepository(self.session)
            conversation = await repository.get_by_id_for_update(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError
            if conversation.status is ConversationStatus.ENDED:
                raise ConversationEndedError
            await repository.set_ended(conversation)
        return conversation

    @staticmethod
    def _secret_value(secret: SecretStr) -> str:
        return secret.get_secret_value()
