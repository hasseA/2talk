"""Conversation summary response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.common import SuccessResponse


class ConversationSummaryResponse(BaseModel):
    id: UUID
    status: str
    main_topics: list[Any]
    agreements: list[Any]
    unresolved_issues: list[Any]
    boundaries: list[Any]
    next_steps: list[Any]
    notice: str | None
    created_at: datetime


class ConversationSummaryData(BaseModel):
    summary: ConversationSummaryResponse


class GetConversationSummaryResponse(SuccessResponse[ConversationSummaryData]):
    pass
