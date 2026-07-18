"""Documented conversation creation, retrieval, and end routes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    AuthorizationContext,
    get_authorization_context,
    get_content_service,
    get_conversation_service,
)
from app.api.schemas.conversation import (
    ConversationDetailData,
    ConversationDetailView,
    CreateConversationData,
    CreateConversationRequest,
    CreateConversationResponse,
    CreatedConversationView,
    EndConversationData,
    EndConversationRequest,
    EndConversationResponse,
    EndedConversationView,
    GetConversationResponse,
    InvitationResponse,
    ParticipantProfileResponse,
    ParticipantWithRoleResponse,
)
from app.models import Participant
from app.services import ConversationService, ParticipantContentService

router = APIRouter(prefix="/conversations", tags=["conversations"])

ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]
ContentService = Annotated[ParticipantContentService, Depends(get_content_service)]
Authorization = Annotated[AuthorizationContext, Depends(get_authorization_context)]


@router.post(
    "",
    response_model=CreateConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: CreateConversationRequest,
    service: ConversationServiceDep,
) -> CreateConversationResponse:
    created = await service.create_conversation(
        display_name=request.display_name,
        preferred_language=request.preferred_language,
        title=request.title,
        description=request.description,
        invitation_expires_at=datetime.now(UTC) + timedelta(days=1),
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    return CreateConversationResponse(
        data=CreateConversationData(
            conversation=CreatedConversationView(
                id=created.conversation.id,
                title=created.conversation.title,
                description=created.conversation.description,
                status=created.conversation.status.value,
                created_at=created.conversation.created_at,
            ),
            participant=_participant_with_role(created.creator),
            invitation=InvitationResponse(
                token=created.invitation_token,
                url=f"/join/{created.invitation_token}",
            ),
            session_token=created.session_token,
        )
    )


@router.get("/{conversation_id}", response_model=GetConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    authorization: Authorization,
    service: ContentService,
) -> GetConversationResponse:
    await authorization.require_conversation(conversation_id)
    details = await service.get_conversation(
        conversation_id=conversation_id,
        participant_id=authorization.participant.id,
    )
    return GetConversationResponse(
        data=ConversationDetailData(
            conversation=ConversationDetailView(
                id=details.conversation.id,
                title=details.conversation.title,
                description=details.conversation.description,
                status=details.conversation.status.value,
                created_at=details.conversation.created_at,
                ended_at=details.conversation.ended_at,
            ),
            current_participant=_participant_profile(details.current_participant),
            other_participant=(
                _participant_profile(details.other_participant)
                if details.other_participant is not None
                else None
            ),
        )
    )


@router.post(
    "/{conversation_id}/end",
    response_model=EndConversationResponse,
    response_model_exclude_none=True,
)
async def end_conversation(
    conversation_id: UUID,
    request: EndConversationRequest,
    authorization: Authorization,
    service: ConversationServiceDep,
) -> EndConversationResponse:
    await authorization.require_conversation(conversation_id)
    ended = await service.end_conversation_request(
        conversation_id, generate_summary=request.generate_summary
    )
    assert ended.conversation.ended_at is not None
    return EndConversationResponse(
        data=EndConversationData(
            conversation=EndedConversationView(
                id=ended.conversation.id,
                status=ended.conversation.status.value,
                ended_at=ended.conversation.ended_at,
            ),
            summary_status=(ended.summary.status.value if ended.summary else None),
        )
    )


def _participant_with_role(participant: Participant) -> ParticipantWithRoleResponse:
    return ParticipantWithRoleResponse(
        id=participant.id,
        display_name=participant.display_name,
        preferred_language=participant.preferred_language,
        role=participant.role.value,
    )


def _participant_profile(participant: Participant) -> ParticipantProfileResponse:
    return ParticipantProfileResponse(
        id=participant.id,
        display_name=participant.display_name,
        preferred_language=participant.preferred_language,
    )
