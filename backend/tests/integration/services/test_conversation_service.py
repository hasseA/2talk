"""Conversation transaction and state tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_token
from app.config import Settings
from app.models import Conversation, ConversationStatus, Invitation, ParticipantRole
from app.repositories import ConversationRepository, ParticipantRepository
from app.services import ConversationService


@pytest.mark.asyncio
async def test_create_conversation_commits_all_required_entities(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    result = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        title="Created atomically",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    assert result.conversation.status is ConversationStatus.WAITING
    assert result.creator.role is ParticipantRole.CREATOR
    assert result.invitation.conversation_id == result.conversation.id
    assert result.participant_session.participant_id == result.creator.id
    assert result.invitation_token not in result.invitation.token_hash
    assert result.session_token not in result.participant_session.token_hash
    assert verify_token(
        result.invitation_token,
        result.invitation.token_hash,
        service_settings.invitation_token_secret.get_secret_value(),
    )


@pytest.mark.asyncio
async def test_create_conversation_rolls_back_everything_on_failure(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    service = ConversationService(db_session, service_settings)

    with pytest.raises(IntegrityError):
        await service.create_conversation(
            display_name="   ",
            preferred_language="en",
            session_expires_at=datetime.now(UTC) + timedelta(days=1),
        )

    conversation_count = await db_session.scalar(select(func.count(Conversation.id)))
    invitation_count = await db_session.scalar(select(func.count(Invitation.id)))
    assert conversation_count == 0
    assert invitation_count == 0


@pytest.mark.asyncio
async def test_activate_conversation_requires_two_participants(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    async with db_session.begin():
        conversations = ConversationRepository(db_session)
        participants = ParticipantRepository(db_session)
        conversation = await conversations.create()
        await participants.create(
            conversation_id=conversation.id,
            display_name="Creator",
            preferred_language="sv",
            role=ParticipantRole.CREATOR,
        )
        await participants.create(
            conversation_id=conversation.id,
            display_name="Invitee",
            preferred_language="en",
            role=ParticipantRole.INVITEE,
        )

    activated = await ConversationService(
        db_session, service_settings
    ).activate_conversation(conversation.id)

    assert activated.status is ConversationStatus.ACTIVE
    assert activated.activated_at is not None


@pytest.mark.asyncio
async def test_end_conversation_commits_ended_state(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="en",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    ended = await ConversationService(db_session, service_settings).end_conversation(
        created.conversation.id
    )

    assert ended.status is ConversationStatus.ENDED
    assert ended.ended_at is not None
