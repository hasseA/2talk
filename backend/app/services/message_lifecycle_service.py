"""Transactional message state transitions without AI behavior."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConversationStatus,
    GuidanceAudience,
    GuidanceType,
    Message,
    MessageStatus,
)
from app.repositories import (
    ConversationRepository,
    MessageDeliveryRepository,
    MessageRepository,
    ParticipantRepository,
    PrivateGuidanceRepository,
)
from app.services.exceptions import (
    ConversationNotFoundError,
    DuplicateMessageError,
    MessageNotFoundError,
    MessageStateError,
    ParticipantNotFoundError,
)


@dataclass(frozen=True, slots=True)
class GuidanceInput:
    """Participant-specific guidance to persist with a delivery."""

    participant_id: UUID
    audience: GuidanceAudience
    guidance_type: GuidanceType
    guidance_text: str


class MessageLifecycleService:
    """Own message authorization, transitions, and atomic delivery writes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_processing_message(
        self,
        *,
        conversation_id: UUID,
        sender_id: UUID,
        client_message_id: str,
        original_message: str,
        original_language: str | None = None,
    ) -> Message:
        async with self.session.begin():
            conversations = ConversationRepository(self.session)
            participants = ParticipantRepository(self.session)
            messages = MessageRepository(self.session)

            conversation = await conversations.get_by_id(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError
            if conversation.status is not ConversationStatus.ACTIVE:
                raise MessageStateError
            if not await participants.participant_belongs_to_conversation(
                sender_id, conversation_id
            ):
                raise ParticipantNotFoundError
            if (
                await messages.get_by_client_message_id(
                    conversation_id, sender_id, client_message_id
                )
                is not None
            ):
                raise DuplicateMessageError
            message = await messages.create_processing_message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                client_message_id=client_message_id,
                original_message=original_message,
                original_language=original_language,
            )
        return message

    async def mark_delivered(
        self,
        *,
        message_id: UUID,
        recipient_id: UUID,
        mediated_message: str,
        delivered_language: str,
        guidance: tuple[GuidanceInput, ...] = (),
        delivered_at: datetime | None = None,
        mediated_at: datetime | None = None,
        communication_goal: str | None = None,
        detected_emotion: str | None = None,
        requires_pause: bool = False,
    ) -> Message:
        async with self.session.begin():
            messages = MessageRepository(self.session)
            participants = ParticipantRepository(self.session)
            deliveries = MessageDeliveryRepository(self.session)
            guidance_repository = PrivateGuidanceRepository(self.session)

            message = await messages.get_by_id_for_update(message_id)
            self._require_message_status(message, MessageStatus.PROCESSING)
            assert message is not None

            recipient = await participants.get_by_id(recipient_id)
            if (
                recipient is None
                or recipient.conversation_id != message.conversation_id
                or recipient.id == message.sender_id
            ):
                raise ParticipantNotFoundError
            self._validate_guidance(guidance, message.sender_id, recipient_id)

            await messages.mark_delivered(
                message,
                mediated_message=mediated_message,
                delivered_language=delivered_language,
                delivered_at=delivered_at,
                mediated_at=mediated_at,
                communication_goal=communication_goal,
                detected_emotion=detected_emotion,
                requires_pause=requires_pause,
            )
            await deliveries.create(
                message_id=message.id,
                recipient_id=recipient_id,
                delivered_at=message.delivered_at,
            )
            for item in guidance:
                await guidance_repository.create(
                    conversation_id=message.conversation_id,
                    message_id=message.id,
                    participant_id=item.participant_id,
                    audience=item.audience,
                    guidance_type=item.guidance_type,
                    guidance_text=item.guidance_text,
                )
        return message

    async def mark_failed(self, message_id: UUID, *, failure_code: str) -> Message:
        async with self.session.begin():
            repository = MessageRepository(self.session)
            message = await repository.get_by_id_for_update(message_id)
            self._require_message_status(message, MessageStatus.PROCESSING)
            assert message is not None
            await repository.mark_failed(message, failure_code=failure_code)
        return message

    async def mark_blocked(
        self, message_id: UUID, *, failure_code: str | None = None
    ) -> Message:
        async with self.session.begin():
            repository = MessageRepository(self.session)
            message = await repository.get_by_id_for_update(message_id)
            self._require_message_status(message, MessageStatus.PROCESSING)
            assert message is not None
            await repository.mark_blocked(message, failure_code=failure_code)
        return message

    async def increment_retry(self, message_id: UUID) -> Message:
        async with self.session.begin():
            repository = MessageRepository(self.session)
            message = await repository.get_by_id_for_update(message_id)
            self._require_message_status(message, MessageStatus.FAILED)
            updated = await repository.increment_retry_count(message_id)
            if updated is None:
                raise MessageNotFoundError
            updated.status = MessageStatus.PROCESSING
            updated.failure_code = None
            await repository.flush()
        return updated

    @staticmethod
    def _require_message_status(
        message: Message | None, required_status: MessageStatus
    ) -> None:
        if message is None:
            raise MessageNotFoundError
        if message.status is not required_status:
            raise MessageStateError

    @staticmethod
    def _validate_guidance(
        guidance: tuple[GuidanceInput, ...], sender_id: UUID, recipient_id: UUID
    ) -> None:
        for item in guidance:
            expected_participant = (
                sender_id if item.audience is GuidanceAudience.SENDER else recipient_id
            )
            if item.participant_id != expected_participant:
                raise ParticipantNotFoundError
