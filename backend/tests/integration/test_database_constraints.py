"""PostgreSQL constraint and default tests."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation,
    ConversationStatus,
    ConversationSummary,
    GuidanceAudience,
    GuidanceType,
    Message,
    MessageStatus,
    Participant,
    ParticipantRole,
    PrivateGuidance,
)


async def add_conversation_with_participants(
    session: AsyncSession,
) -> tuple[Conversation, Participant, Participant]:
    conversation = Conversation()
    creator = Participant(
        conversation=conversation,
        display_name="Creator",
        preferred_language="sv",
        role=ParticipantRole.CREATOR,
    )
    invitee = Participant(
        conversation=conversation,
        display_name="Invitee",
        preferred_language="en",
        role=ParticipantRole.INVITEE,
    )
    session.add_all([conversation, creator, invitee])
    await session.commit()
    return conversation, creator, invitee


@pytest.mark.asyncio
async def test_creator_and_invitee_can_share_a_conversation(
    db_session: AsyncSession,
) -> None:
    conversation, creator, invitee = await add_conversation_with_participants(
        db_session
    )

    assert creator.conversation_id == conversation.id
    assert invitee.conversation_id == conversation.id


@pytest.mark.asyncio
async def test_duplicate_participant_roles_are_rejected(
    db_session: AsyncSession,
) -> None:
    conversation = Conversation()
    db_session.add_all(
        [
            Participant(
                conversation=conversation,
                display_name="First",
                preferred_language="en",
                role=ParticipantRole.CREATOR,
            ),
            Participant(
                conversation=conversation,
                display_name="Second",
                preferred_language="sv",
                role=ParticipantRole.CREATOR,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_client_message_id_is_rejected(
    db_session: AsyncSession,
) -> None:
    conversation, creator, _ = await add_conversation_with_participants(db_session)
    db_session.add_all(
        [
            Message(
                conversation_id=conversation.id,
                sender_id=creator.id,
                client_message_id="same-client-id",
                original_message="First",
            ),
            Message(
                conversation_id=conversation.id,
                sender_id=creator.id,
                client_message_id="same-client-id",
                original_message="Second",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_delivered_message_requires_content_and_timestamp(
    db_session: AsyncSession,
) -> None:
    conversation, creator, _ = await add_conversation_with_participants(db_session)
    db_session.add(
        Message(
            conversation_id=conversation.id,
            sender_id=creator.id,
            client_message_id="delivery-check",
            original_message="Original",
            status=MessageStatus.DELIVERED,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_valid_delivered_message_is_accepted(db_session: AsyncSession) -> None:
    conversation, creator, _ = await add_conversation_with_participants(db_session)
    message = Message(
        conversation_id=conversation.id,
        sender_id=creator.id,
        client_message_id="valid-delivery",
        original_message="Original",
        mediated_message="Mediated",
        status=MessageStatus.DELIVERED,
        delivered_at=datetime.now(UTC),
    )
    db_session.add(message)
    await db_session.commit()

    assert message.status is MessageStatus.DELIVERED


@pytest.mark.asyncio
async def test_invalid_status_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(Conversation(status="invalid"))  # type: ignore[arg-type]

    with pytest.raises((IntegrityError, StatementError)):
        await db_session.commit()


@pytest.mark.asyncio
async def test_private_guidance_requires_participant(db_session: AsyncSession) -> None:
    conversation, creator, _ = await add_conversation_with_participants(db_session)
    message = Message(
        conversation_id=conversation.id,
        sender_id=creator.id,
        client_message_id="guidance-message",
        original_message="Original",
    )
    db_session.add(message)
    await db_session.flush()
    db_session.add(
        PrivateGuidance(
            conversation_id=conversation.id,
            message_id=message.id,
            participant_id=None,  # type: ignore[arg-type]
            audience=GuidanceAudience.SENDER,
            guidance_type=GuidanceType.CLARIFICATION,
            guidance_text="Clarify the request.",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_summary_json_fields_default_to_empty_lists(
    db_session: AsyncSession,
) -> None:
    conversation = Conversation(status=ConversationStatus.ENDED)
    summary = ConversationSummary(conversation=conversation)
    db_session.add(summary)
    await db_session.commit()
    await db_session.refresh(summary)

    assert summary.main_topics == []
    assert summary.agreements == []
    assert summary.unresolved_issues == []
    assert summary.boundaries == []
    assert summary.next_steps == []
