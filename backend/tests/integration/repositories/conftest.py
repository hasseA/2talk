"""Shared repository test graph."""

from dataclasses import dataclass

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Participant, ParticipantRole
from app.repositories import ConversationRepository, ParticipantRepository


@dataclass(slots=True)
class RepositoryGraph:
    conversation: Conversation
    creator: Participant
    invitee: Participant


@pytest_asyncio.fixture
async def repository_graph(db_session: AsyncSession) -> RepositoryGraph:
    conversations = ConversationRepository(db_session)
    participants = ParticipantRepository(db_session)

    conversation = await conversations.create(title="Repository test")
    creator = await participants.create(
        conversation_id=conversation.id,
        display_name="Creator",
        preferred_language="sv",
        role=ParticipantRole.CREATOR,
    )
    invitee = await participants.create(
        conversation_id=conversation.id,
        display_name="Invitee",
        preferred_language="en",
        role=ParticipantRole.INVITEE,
    )
    return RepositoryGraph(conversation, creator, invitee)
