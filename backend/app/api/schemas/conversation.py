"""Documented conversation request and response schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.api.schemas.common import SuccessResponse

LanguageCode = Literal["en", "sv", "fa"]
DisplayName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    display_name: DisplayName
    preferred_language: LanguageCode
    description: str | None = Field(default=None, max_length=1000)


class CreatedConversationView(BaseModel):
    id: UUID
    title: str | None
    description: str | None
    status: str
    created_at: datetime


class ParticipantWithRoleResponse(BaseModel):
    id: UUID
    display_name: str
    preferred_language: str
    role: str


class ParticipantProfileResponse(BaseModel):
    id: UUID
    display_name: str
    preferred_language: str


class InvitationResponse(BaseModel):
    token: str
    url: str


class CreateConversationData(BaseModel):
    conversation: CreatedConversationView
    participant: ParticipantWithRoleResponse
    invitation: InvitationResponse
    session_token: str


class CreateConversationResponse(SuccessResponse[CreateConversationData]):
    pass


class ConversationDetailView(BaseModel):
    id: UUID
    title: str | None
    description: str | None
    status: str
    created_at: datetime
    ended_at: datetime | None


class ConversationDetailData(BaseModel):
    conversation: ConversationDetailView
    current_participant: ParticipantProfileResponse
    other_participant: ParticipantProfileResponse | None


class GetConversationResponse(SuccessResponse[ConversationDetailData]):
    pass


class EndConversationRequest(BaseModel):
    generate_summary: bool


class EndedConversationView(BaseModel):
    id: UUID
    status: str
    ended_at: datetime


class EndConversationData(BaseModel):
    conversation: EndedConversationView
    summary_status: str | None


class EndConversationResponse(SuccessResponse[EndConversationData]):
    pass
