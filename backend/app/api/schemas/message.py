"""Privacy-distinct schemas for documented message and guidance routes."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.common import SuccessResponse


class CreateMessageRequest(BaseModel):
    client_message_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=5000)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class MessageResponse(BaseModel):
    id: UUID
    client_message_id: str
    status: str
    created_at: datetime


class CreateMessageData(BaseModel):
    message: MessageResponse


class CreateMessageResponse(SuccessResponse[CreateMessageData]):
    pass


class OutgoingMessageResponse(BaseModel):
    id: UUID
    sender_id: UUID
    sender_display_name: str
    direction: Literal["outgoing"] = "outgoing"
    original_message: str
    mediated_message: str | None
    status: str
    created_at: datetime
    delivered_at: datetime | None


class IncomingMessageResponse(BaseModel):
    id: UUID
    sender_id: UUID
    sender_display_name: str
    direction: Literal["incoming"] = "incoming"
    mediated_message: str
    status: str
    created_at: datetime
    delivered_at: datetime


class ConversationMessagesData(BaseModel):
    messages: list[OutgoingMessageResponse | IncomingMessageResponse]
    has_more: bool
    next_cursor: UUID | None


class ConversationMessagesResponse(SuccessResponse[ConversationMessagesData]):
    pass


class MessageStatusResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime | None = None
    failure_code: str | None = None
    retry_allowed: bool | None = None


class MessageStatusData(BaseModel):
    message: MessageStatusResponse


class GetMessageStatusResponse(SuccessResponse[MessageStatusData]):
    pass


class RetryMessageResponse(BaseModel):
    id: UUID
    status: str


class RetryMessageData(BaseModel):
    message: RetryMessageResponse


class RetryMessageSuccessResponse(SuccessResponse[RetryMessageData]):
    pass


class GuidanceResponse(BaseModel):
    id: UUID
    message_id: UUID
    audience: str
    text: str
    type: str
    created_at: datetime


class GuidanceData(BaseModel):
    guidance: list[GuidanceResponse]


class GuidanceListResponse(SuccessResponse[GuidanceData]):
    pass
