"""Documented authenticated participant preference route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    AuthorizationContext,
    get_authorization_context,
    get_participant_service,
)
from app.api.schemas.conversation import ParticipantProfileResponse
from app.api.schemas.participant import (
    UpdateLanguageData,
    UpdateLanguageRequest,
    UpdateLanguageResponse,
)
from app.services import ParticipantService

router = APIRouter(prefix="/conversations", tags=["participants"])

Authorization = Annotated[AuthorizationContext, Depends(get_authorization_context)]
ParticipantServiceDep = Annotated[ParticipantService, Depends(get_participant_service)]


@router.patch(
    "/{conversation_id}/participants/me", response_model=UpdateLanguageResponse
)
async def update_language(
    conversation_id: UUID,
    request: UpdateLanguageRequest,
    authorization: Authorization,
    service: ParticipantServiceDep,
) -> UpdateLanguageResponse:
    await authorization.require_conversation(conversation_id)
    participant = await service.update_language(
        conversation_id=conversation_id,
        participant_id=authorization.participant.id,
        preferred_language=request.preferred_language,
    )
    return UpdateLanguageResponse(
        data=UpdateLanguageData(
            participant=ParticipantProfileResponse(
                id=participant.id,
                display_name=participant.display_name,
                preferred_language=participant.preferred_language,
            )
        )
    )
