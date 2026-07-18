"""Documented authenticated message and guidance routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    AuthorizationContext,
    get_authorization_context,
    get_content_service,
    get_message_service,
)
from app.api.schemas.message import (
    ConversationMessagesData,
    ConversationMessagesResponse,
    CreateMessageData,
    CreateMessageRequest,
    CreateMessageResponse,
    GetMessageStatusResponse,
    GuidanceData,
    GuidanceListResponse,
    GuidanceResponse,
    IncomingMessageResponse,
    MessageResponse,
    MessageStatusData,
    MessageStatusResponse,
    OutgoingMessageResponse,
    RetryMessageData,
    RetryMessageResponse,
    RetryMessageSuccessResponse,
)
from app.models import MessageStatus
from app.repositories import IncomingMessageProjection, SenderMessageProjection
from app.services import MessageLifecycleService, ParticipantContentService

router = APIRouter(prefix="/conversations", tags=["messages"])

Authorization = Annotated[AuthorizationContext, Depends(get_authorization_context)]
MessageService = Annotated[MessageLifecycleService, Depends(get_message_service)]
ContentService = Annotated[ParticipantContentService, Depends(get_content_service)]
AfterCursor = Annotated[UUID | None, Query()]
PageLimit = Annotated[int, Query(ge=1, le=100)]


@router.post(
    "/{conversation_id}/messages",
    response_model=CreateMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_message(
    conversation_id: UUID,
    request: CreateMessageRequest,
    authorization: Authorization,
    service: MessageService,
) -> CreateMessageResponse:
    await authorization.require_conversation(conversation_id)
    message = await service.create_processing_message(
        conversation_id=conversation_id,
        sender_id=authorization.participant.id,
        client_message_id=request.client_message_id,
        original_message=request.message,
        original_language=authorization.participant.preferred_language,
    )
    return CreateMessageResponse(
        data=CreateMessageData(
            message=MessageResponse(
                id=message.id,
                client_message_id=message.client_message_id,
                status=message.status.value,
                created_at=message.created_at,
            )
        )
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
async def conversation_messages(
    conversation_id: UUID,
    authorization: Authorization,
    service: ContentService,
    after: AfterCursor = None,
    limit: PageLimit = 50,
) -> ConversationMessagesResponse:
    await authorization.require_conversation(conversation_id)
    page = await service.list_messages(
        conversation_id=conversation_id,
        participant_id=authorization.participant.id,
        after=after,
        limit=limit,
    )
    messages: list[OutgoingMessageResponse | IncomingMessageResponse] = []
    for message in page.messages:
        if isinstance(message, SenderMessageProjection):
            messages.append(
                _outgoing_message(message, authorization.participant.display_name)
            )
        else:
            messages.append(_incoming_message(message))
    return ConversationMessagesResponse(
        data=ConversationMessagesData(
            messages=messages,
            has_more=page.has_more,
            next_cursor=page.next_cursor,
        )
    )


@router.get(
    "/{conversation_id}/messages/{message_id}",
    response_model=GetMessageStatusResponse,
    response_model_exclude_none=True,
)
async def get_message_status(
    conversation_id: UUID,
    message_id: UUID,
    authorization: Authorization,
    service: ContentService,
) -> GetMessageStatusResponse:
    await authorization.require_conversation(conversation_id)
    message = await service.get_outgoing_message(
        conversation_id=conversation_id,
        participant_id=authorization.participant.id,
        message_id=message_id,
    )
    failed = message.status is MessageStatus.FAILED
    return GetMessageStatusResponse(
        data=MessageStatusData(
            message=MessageStatusResponse(
                id=message.id,
                status=message.status.value,
                created_at=None if failed else message.created_at,
                failure_code=message.failure_code if failed else None,
                retry_allowed=True if failed else None,
            )
        )
    )


@router.post(
    "/{conversation_id}/messages/{message_id}/retry",
    response_model=RetryMessageSuccessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_message(
    conversation_id: UUID,
    message_id: UUID,
    authorization: Authorization,
    service: MessageService,
) -> RetryMessageSuccessResponse:
    await authorization.require_conversation(conversation_id)
    message = await service.retry_failed_message(
        conversation_id=conversation_id,
        sender_id=authorization.participant.id,
        message_id=message_id,
    )
    return RetryMessageSuccessResponse(
        data=RetryMessageData(
            message=RetryMessageResponse(id=message.id, status=message.status.value)
        )
    )


@router.get(
    "/{conversation_id}/guidance",
    response_model=GuidanceListResponse,
)
async def private_guidance(
    conversation_id: UUID,
    authorization: Authorization,
    service: ContentService,
    after: AfterCursor = None,
    limit: PageLimit = 50,
) -> GuidanceListResponse:
    await authorization.require_conversation(conversation_id)
    page = await service.list_private_guidance(
        conversation_id=conversation_id,
        participant_id=authorization.participant.id,
        after=after,
        limit=limit,
    )
    return GuidanceListResponse(
        data=GuidanceData(
            guidance=[
                GuidanceResponse(
                    id=item.id,
                    message_id=item.message_id,
                    audience=item.audience.value,
                    text=item.guidance_text,
                    type=item.guidance_type.value,
                    created_at=item.created_at,
                )
                for item in page.guidance
            ]
        )
    )


def _outgoing_message(
    message: SenderMessageProjection, sender_display_name: str
) -> OutgoingMessageResponse:
    return OutgoingMessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        sender_display_name=sender_display_name,
        original_message=message.original_message,
        mediated_message=message.mediated_message,
        status=message.status.value,
        created_at=message.created_at,
        delivered_at=message.delivered_at,
    )


def _incoming_message(
    message: IncomingMessageProjection,
) -> IncomingMessageResponse:
    return IncomingMessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        sender_display_name=message.sender_display_name,
        mediated_message=message.mediated_message,
        status=message.status.value,
        created_at=message.created_at,
        delivered_at=message.delivered_at,
    )
