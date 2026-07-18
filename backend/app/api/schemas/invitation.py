"""Documented invitation validation and redemption schemas."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from app.api.schemas.common import SuccessResponse
from app.api.schemas.conversation import (
    DisplayName,
    LanguageCode,
    ParticipantWithRoleResponse,
)

InvitationToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class InvitationConversationResponse(BaseModel):
    title: str | None
    status: str


class ValidateInvitationData(BaseModel):
    valid: Literal[True] = True
    conversation: InvitationConversationResponse


class ValidateInvitationResponse(SuccessResponse[ValidateInvitationData]):
    pass


class JoinConversationRequest(BaseModel):
    display_name: DisplayName
    preferred_language: LanguageCode


class JoinedConversationResponse(BaseModel):
    id: UUID
    title: str | None
    status: str


class JoinConversationData(BaseModel):
    conversation: JoinedConversationResponse
    participant: ParticipantWithRoleResponse
    session_token: str


class JoinConversationResponse(SuccessResponse[JoinConversationData]):
    pass
