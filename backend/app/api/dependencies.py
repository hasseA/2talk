"""Explicit FastAPI dependency graph and reusable authorization context."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_authenticated_participant
from app.api.database import get_db_session
from app.config import Settings, get_settings
from app.models import Participant
from app.repositories import ConversationRepository, ParticipantRepository
from app.services import (
    ConversationService,
    InvitationService,
    MessageLifecycleService,
    ParticipantContentService,
    ParticipantService,
)

Session = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AuthenticatedParticipant = Annotated[
    Participant, Depends(get_authenticated_participant)
]


def get_conversation_service(
    session: Session,
    settings: AppSettings,
) -> ConversationService:
    return ConversationService(session, settings)


def get_invitation_service(
    session: Session,
    settings: AppSettings,
) -> InvitationService:
    return InvitationService(session, settings)


def get_participant_service(
    session: Session,
    settings: AppSettings,
) -> ParticipantService:
    return ParticipantService(session, settings)


def get_message_service(session: Session) -> MessageLifecycleService:
    return MessageLifecycleService(session)


def get_content_service(session: Session) -> ParticipantContentService:
    return ParticipantContentService(session)


@dataclass(slots=True)
class AuthorizationContext:
    """Reusable authorization operations for the authenticated participant."""

    participant: Participant
    session: AsyncSession

    async def require_conversation(self, conversation_id: UUID) -> None:
        async with self.session.begin():
            if (
                await ConversationRepository(self.session).get_by_id(conversation_id)
                is None
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "CONVERSATION_NOT_FOUND",
                        "message": "Conversation not found.",
                    },
                )
            belongs = await ParticipantRepository(
                self.session
            ).participant_belongs_to_conversation(self.participant.id, conversation_id)
            if not belongs:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": "Access to this conversation is forbidden.",
                    },
                )


def get_authorization_context(
    participant: AuthenticatedParticipant,
    session: Session,
) -> AuthorizationContext:
    return AuthorizationContext(participant=participant, session=session)
