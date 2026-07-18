"""Documented public invitation validation and join routes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_invitation_service
from app.api.schemas.conversation import ParticipantWithRoleResponse
from app.api.schemas.invitation import (
    InvitationConversationResponse,
    JoinConversationData,
    JoinConversationRequest,
    JoinConversationResponse,
    JoinedConversationResponse,
    ValidateInvitationData,
    ValidateInvitationResponse,
)
from app.services import InvitationService

router = APIRouter(prefix="/invitations", tags=["invitations"])

InvitationServiceDep = Annotated[InvitationService, Depends(get_invitation_service)]


@router.get("/{invitation_token}", response_model=ValidateInvitationResponse)
async def validate_invitation(
    invitation_token: str,
    service: InvitationServiceDep,
) -> ValidateInvitationResponse:
    validation = await service.validate_invitation(invitation_token)
    return ValidateInvitationResponse(
        data=ValidateInvitationData(
            conversation=InvitationConversationResponse(
                title=validation.title,
                status=validation.status.value,
            )
        )
    )


@router.post(
    "/{invitation_token}/join",
    response_model=JoinConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_conversation(
    invitation_token: str,
    request: JoinConversationRequest,
    service: InvitationServiceDep,
) -> JoinConversationResponse:
    joined = await service.redeem_invitation(
        invitation_token=invitation_token,
        display_name=request.display_name,
        preferred_language=request.preferred_language,
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    return JoinConversationResponse(
        data=JoinConversationData(
            conversation=JoinedConversationResponse(
                id=joined.conversation.id,
                title=joined.conversation.title,
                status=joined.conversation.status.value,
            ),
            participant=ParticipantWithRoleResponse(
                id=joined.participant.id,
                display_name=joined.participant.display_name,
                preferred_language=joined.participant.preferred_language,
                role=joined.participant.role.value,
            ),
            session_token=joined.session_token,
        )
    )
