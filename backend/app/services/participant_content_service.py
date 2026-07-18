"""Privacy-safe participant content reads for the REST boundary."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, ConversationSummary, Participant, PrivateGuidance
from app.repositories import (
    ConversationRepository,
    ConversationSummaryRepository,
    IncomingMessageProjection,
    MessageRepository,
    ParticipantRepository,
    PrivateGuidanceRepository,
    SenderMessageProjection,
)
from app.services.exceptions import (
    InvalidCursorError,
    MessageNotFoundError,
    ParticipantNotFoundError,
    SummaryNotFoundError,
)


@dataclass(frozen=True, slots=True)
class ConversationDetails:
    conversation: Conversation
    current_participant: Participant
    other_participant: Participant | None


@dataclass(frozen=True, slots=True)
class MessagePage:
    messages: tuple[SenderMessageProjection | IncomingMessageProjection, ...]
    has_more: bool
    next_cursor: UUID | None


@dataclass(frozen=True, slots=True)
class GuidancePage:
    guidance: tuple[PrivateGuidance, ...]


class ParticipantContentService:
    """Return only content authorized for one conversation participant."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_conversation(
        self, *, conversation_id: UUID, participant_id: UUID
    ) -> ConversationDetails:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            conversation = await ConversationRepository(self.session).get_by_id(
                conversation_id
            )
            current = await ParticipantRepository(self.session).get_by_id(
                participant_id
            )
            if conversation is None or current is None:
                raise ParticipantNotFoundError
            other = await ParticipantRepository(self.session).get_other_participant(
                conversation_id, participant_id
            )
            return ConversationDetails(conversation, current, other)

    async def list_outgoing_messages(
        self, *, conversation_id: UUID, participant_id: UUID
    ) -> list[SenderMessageProjection]:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            return await MessageRepository(self.session).list_for_sender(
                conversation_id, participant_id
            )

    async def list_incoming_messages(
        self, *, conversation_id: UUID, participant_id: UUID
    ) -> list[IncomingMessageProjection]:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            return await MessageRepository(self.session).list_incoming_for_recipient(
                conversation_id, participant_id
            )

    async def list_messages(
        self,
        *,
        conversation_id: UUID,
        participant_id: UUID,
        after: UUID | None,
        limit: int,
    ) -> MessagePage:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            repository = MessageRepository(self.session)
            outgoing = await repository.list_for_sender(conversation_id, participant_id)
            incoming = await repository.list_incoming_for_recipient(
                conversation_id, participant_id
            )
            visible = sorted(
                [*outgoing, *incoming], key=lambda item: (item.created_at, item.id)
            )
            page, has_more, next_cursor = self._paginate(visible, after, limit)
            return MessagePage(tuple(page), has_more, next_cursor)

    async def get_outgoing_message(
        self, *, conversation_id: UUID, participant_id: UUID, message_id: UUID
    ) -> SenderMessageProjection:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            repository = MessageRepository(self.session)
            stored = await repository.get_by_id(message_id)
            if stored is None or stored.conversation_id != conversation_id:
                raise MessageNotFoundError
            if stored.sender_id != participant_id:
                raise ParticipantNotFoundError
            outgoing = await repository.list_for_sender(conversation_id, participant_id)
            for message in outgoing:
                if message.id == message_id:
                    return message
            raise MessageNotFoundError

    async def list_private_guidance(
        self,
        *,
        conversation_id: UUID,
        participant_id: UUID,
        after: UUID | None,
        limit: int,
    ) -> GuidancePage:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            guidance = await PrivateGuidanceRepository(
                self.session
            ).list_for_participant(participant_id)
            visible = [
                item for item in guidance if item.conversation_id == conversation_id
            ]
            page, _, _ = self._paginate(visible, after, limit)
            return GuidancePage(tuple(page))

    async def get_summary(
        self, *, conversation_id: UUID, participant_id: UUID
    ) -> ConversationSummary:
        async with self.session.begin():
            await self._require_membership(conversation_id, participant_id)
            summary = await ConversationSummaryRepository(
                self.session
            ).get_by_conversation(conversation_id)
            if summary is None:
                raise SummaryNotFoundError
            return summary

    async def _require_membership(
        self, conversation_id: UUID, participant_id: UUID
    ) -> None:
        belongs = await ParticipantRepository(
            self.session
        ).participant_belongs_to_conversation(participant_id, conversation_id)
        if not belongs:
            raise ParticipantNotFoundError

    @staticmethod
    def _paginate(
        items: list[Any], after: UUID | None, limit: int
    ) -> tuple[list[Any], bool, UUID | None]:
        start = 0
        if after is not None:
            for index, item in enumerate(items):
                if item.id == after:
                    start = index + 1
                    break
            else:
                raise InvalidCursorError
        selected = items[start : start + limit]
        has_more = start + len(selected) < len(items)
        next_cursor = selected[-1].id if selected and has_more else None
        return selected, has_more, next_cursor
