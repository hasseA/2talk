"""Participant bearer-session authentication dependency."""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.database import get_db_session
from app.auth import hash_token
from app.config import Settings, get_settings
from app.models import Participant
from app.repositories import ParticipantRepository, ParticipantSessionRepository

bearer_scheme = HTTPBearer(auto_error=False)

Credentials = Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)]
Session = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_authenticated_participant(
    credentials: Credentials,
    session: Session,
    settings: AppSettings,
) -> Participant:
    """Resolve a valid opaque bearer token to its participant identity."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    token_hash = hash_token(
        credentials.credentials,
        settings.session_token_secret.get_secret_value(),
    )
    async with session.begin():
        sessions = ParticipantSessionRepository(session)
        participant_sessions = await sessions.get_valid_by_token_hash(token_hash)
        if participant_sessions is None:
            raise _unauthorized()
        participant = await ParticipantRepository(session).get_by_id(
            participant_sessions.participant_id
        )
        if participant is None:
            raise _unauthorized()
        await sessions.update_last_used(participant_sessions)
    return participant


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Invalid session token."},
        headers={"WWW-Authenticate": "Bearer"},
    )
