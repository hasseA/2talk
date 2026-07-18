"""Message persistence with sender and recipient-specific query shapes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, case, or_, select, update

from app.models import Message, MessageDelivery, MessageStatus, Participant
from app.repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class SenderMessageProjection:
    """A sender-authorized view that may include the sender's original text."""

    id: UUID
    conversation_id: UUID
    sender_id: UUID
    client_message_id: str
    original_message: str
    original_language: str | None
    mediated_message: str | None
    delivered_language: str | None
    status: MessageStatus
    failure_code: str | None
    retry_count: int
    created_at: datetime
    mediated_at: datetime | None
    delivered_at: datetime | None
    blocked_at: datetime | None


@dataclass(frozen=True, slots=True)
class IncomingMessageProjection:
    """A recipient-safe view that structurally cannot expose original text."""

    id: UUID
    conversation_id: UUID
    sender_id: UUID
    sender_display_name: str
    mediated_message: str
    delivered_language: str | None
    status: MessageStatus
    created_at: datetime
    mediated_at: datetime | None
    delivered_at: datetime
    seen_at: datetime | None


@dataclass(frozen=True, slots=True)
class MediatedContextProjection:
    """A privacy-safe prior turn prepared for the AI mediation context."""

    speaker: str
    mediated_message: str
    language: str


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def create_processing_message(
        self,
        *,
        conversation_id: UUID,
        sender_id: UUID,
        client_message_id: str,
        original_message: str,
        original_language: str | None = None,
    ) -> Message:
        return await self.add(
            Message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                client_message_id=client_message_id,
                original_message=original_message,
                original_language=original_language,
                status=MessageStatus.PROCESSING,
            )
        )

    async def get_by_id_for_update(self, message_id: UUID) -> Message | None:
        statement = select(Message).where(Message.id == message_id).with_for_update()
        return await self.session.scalar(statement)

    async def get_by_client_message_id(
        self, conversation_id: UUID, sender_id: UUID, client_message_id: str
    ) -> Message | None:
        statement = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.sender_id == sender_id,
            Message.client_message_id == client_message_id,
        )
        return await self.session.scalar(statement)

    async def list_for_sender(
        self, conversation_id: UUID, sender_id: UUID
    ) -> list[SenderMessageProjection]:
        statement = (
            select(
                Message.id,
                Message.conversation_id,
                Message.sender_id,
                Message.client_message_id,
                Message.original_message,
                Message.original_language,
                Message.mediated_message,
                Message.delivered_language,
                Message.status,
                Message.failure_code,
                Message.retry_count,
                Message.created_at,
                Message.mediated_at,
                Message.delivered_at,
                Message.blocked_at,
            )
            .where(
                Message.conversation_id == conversation_id,
                Message.sender_id == sender_id,
            )
            .order_by(Message.created_at, Message.id)
        )
        rows = (await self.session.execute(statement)).all()
        return [SenderMessageProjection(*row) for row in rows]

    async def list_incoming_for_recipient(
        self, conversation_id: UUID, recipient_id: UUID
    ) -> list[IncomingMessageProjection]:
        statement = (
            select(
                Message.id,
                Message.conversation_id,
                Message.sender_id,
                Participant.display_name.label("sender_display_name"),
                Message.mediated_message,
                Message.delivered_language,
                Message.status,
                Message.created_at,
                Message.mediated_at,
                Message.delivered_at,
                MessageDelivery.seen_at,
            )
            .join(Participant, Participant.id == Message.sender_id)
            .join(MessageDelivery, MessageDelivery.message_id == Message.id)
            .where(
                Message.conversation_id == conversation_id,
                MessageDelivery.recipient_id == recipient_id,
                Message.status == MessageStatus.DELIVERED,
                Message.mediated_message.is_not(None),
                Message.delivered_at.is_not(None),
            )
            .order_by(Message.created_at, Message.id)
        )
        rows = (await self.session.execute(statement)).all()
        return [IncomingMessageProjection(*row) for row in rows]

    async def list_mediated_context(
        self,
        *,
        conversation_id: UUID,
        perspective_sender_id: UUID,
        before_created_at: datetime,
        before_message_id: UUID,
        limit: int,
    ) -> list[MediatedContextProjection]:
        """Return only prior delivered content, bounded and oldest-first."""
        statement = (
            select(
                case(
                    (Message.sender_id == perspective_sender_id, "sender"),
                    else_="recipient",
                ).label("speaker"),
                Message.mediated_message,
                Message.delivered_language,
            )
            .where(
                Message.conversation_id == conversation_id,
                Message.status == MessageStatus.DELIVERED,
                Message.mediated_message.is_not(None),
                Message.delivered_language.is_not(None),
                or_(
                    Message.created_at < before_created_at,
                    and_(
                        Message.created_at == before_created_at,
                        Message.id < before_message_id,
                    ),
                ),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(statement)).all())
        rows.reverse()
        return [MediatedContextProjection(*row) for row in rows]

    async def mark_delivered(
        self,
        message: Message,
        *,
        mediated_message: str,
        delivered_language: str,
        delivered_at: datetime | None = None,
        mediated_at: datetime | None = None,
        communication_goal: str | None = None,
        detected_emotion: str | None = None,
        requires_pause: bool = False,
    ) -> Message:
        now = datetime.now(UTC)
        message.mediated_message = mediated_message
        message.delivered_language = delivered_language
        message.communication_goal = communication_goal
        message.detected_emotion = detected_emotion
        message.requires_pause = requires_pause
        message.mediated_at = mediated_at or now
        message.delivered_at = delivered_at or now
        message.status = MessageStatus.DELIVERED
        message.failure_code = None
        await self.session.flush()
        return message

    async def mark_failed(self, message: Message, *, failure_code: str) -> Message:
        message.status = MessageStatus.FAILED
        message.failure_code = failure_code
        await self.session.flush()
        return message

    async def mark_blocked(
        self,
        message: Message,
        *,
        failure_code: str | None = None,
        blocked_at: datetime | None = None,
    ) -> Message:
        message.status = MessageStatus.BLOCKED
        message.failure_code = failure_code
        message.blocked_at = blocked_at or datetime.now(UTC)
        await self.session.flush()
        return message

    async def increment_retry_count(self, message_id: UUID) -> Message | None:
        statement = (
            update(Message)
            .where(Message.id == message_id)
            .values(retry_count=Message.retry_count + 1)
            .returning(Message)
        )
        return await self.session.scalar(statement)
