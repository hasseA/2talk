"""Authenticated shared-summary retrieval route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    AuthorizationContext,
    get_authorization_context,
    get_content_service,
)
from app.api.schemas.summary import (
    ConversationSummaryData,
    ConversationSummaryResponse,
    GetConversationSummaryResponse,
)
from app.services import ParticipantContentService

router = APIRouter(prefix="/conversations", tags=["summaries"])

Authorization = Annotated[AuthorizationContext, Depends(get_authorization_context)]
ContentService = Annotated[ParticipantContentService, Depends(get_content_service)]


@router.get(
    "/{conversation_id}/summary",
    response_model=GetConversationSummaryResponse,
    response_model_exclude_none=True,
)
async def get_summary(
    conversation_id: UUID,
    authorization: Authorization,
    service: ContentService,
) -> GetConversationSummaryResponse:
    await authorization.require_conversation(conversation_id)
    summary = await service.get_summary(
        conversation_id=conversation_id,
        participant_id=authorization.participant.id,
    )
    return GetConversationSummaryResponse(
        data=ConversationSummaryData(
            summary=ConversationSummaryResponse(
                id=summary.id,
                status=summary.status.value,
                main_topics=summary.main_topics,
                agreements=summary.agreements,
                unresolved_issues=summary.unresolved_issues,
                boundaries=summary.boundaries,
                next_steps=summary.next_steps,
                notice=summary.notice,
                created_at=summary.created_at,
            )
        )
    )
