"""Message, delivery, processing-attempt, and guidance repository tests."""

from dataclasses import fields
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuidanceAudience, GuidanceType, MessageStatus
from app.repositories import (
    AIProcessingAttemptRepository,
    IncomingMessageProjection,
    MessageDeliveryRepository,
    MessageRepository,
    PrivateGuidanceRepository,
)
from tests.integration.repositories.conftest import RepositoryGraph


@pytest.mark.asyncio
async def test_message_lookup_by_client_message_id(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = MessageRepository(db_session)
    message = await repository.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="duplicate-protection-id",
        original_message="Original sender text",
        original_language="sv",
    )

    duplicate = await repository.get_by_client_message_id(
        repository_graph.conversation.id,
        repository_graph.creator.id,
        "duplicate-protection-id",
    )

    assert duplicate is message


@pytest.mark.asyncio
async def test_sender_projection_contains_own_original_message(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = MessageRepository(db_session)
    await repository.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="sender-visible-id",
        original_message="Visible only to sender",
    )

    messages = await repository.list_for_sender(
        repository_graph.conversation.id, repository_graph.creator.id
    )

    assert len(messages) == 1
    assert messages[0].original_message == "Visible only to sender"


@pytest.mark.asyncio
async def test_recipient_projection_omits_original_message_structurally(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    messages = MessageRepository(db_session)
    deliveries = MessageDeliveryRepository(db_session)
    message = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="recipient-safe-id",
        original_message="Must never reach recipient",
    )
    await messages.mark_delivered(
        message,
        mediated_message="Recipient-safe mediated text",
        delivered_language="en",
    )
    await deliveries.create(
        message_id=message.id,
        recipient_id=repository_graph.invitee.id,
        delivered_at=message.delivered_at,
    )

    incoming = await messages.list_incoming_for_recipient(
        repository_graph.conversation.id, repository_graph.invitee.id
    )

    assert len(incoming) == 1
    assert incoming[0].mediated_message == "Recipient-safe mediated text"
    assert not hasattr(incoming[0], "original_message")
    assert "original_message" not in {
        field.name for field in fields(IncomingMessageProjection)
    }


@pytest.mark.asyncio
async def test_recipient_sees_only_delivered_messages_intended_for_them(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    messages = MessageRepository(db_session)
    deliveries = MessageDeliveryRepository(db_session)

    delivered = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="delivered-id",
        original_message="Delivered original",
    )
    await messages.mark_delivered(
        delivered, mediated_message="Delivered safely", delivered_language="en"
    )
    await deliveries.create(
        message_id=delivered.id,
        recipient_id=repository_graph.invitee.id,
        delivered_at=delivered.delivered_at,
    )

    processing = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="processing-id",
        original_message="Still processing",
    )
    await deliveries.create(
        message_id=processing.id,
        recipient_id=repository_graph.invitee.id,
    )

    for_creator = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.invitee.id,
        client_message_id="other-recipient-id",
        original_message="For creator",
    )
    await messages.mark_delivered(
        for_creator,
        mediated_message="Only for creator",
        delivered_language="sv",
    )
    await deliveries.create(
        message_id=for_creator.id,
        recipient_id=repository_graph.creator.id,
        delivered_at=for_creator.delivered_at,
    )

    incoming = await messages.list_incoming_for_recipient(
        repository_graph.conversation.id, repository_graph.invitee.id
    )

    assert [item.id for item in incoming] == [delivered.id]
    assert all(item.status is MessageStatus.DELIVERED for item in incoming)


@pytest.mark.asyncio
async def test_message_delivery_can_be_marked_seen(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    messages = MessageRepository(db_session)
    deliveries = MessageDeliveryRepository(db_session)
    message = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="seen-id",
        original_message="Original",
    )
    delivery = await deliveries.create(
        message_id=message.id, recipient_id=repository_graph.invitee.id
    )
    seen_at = datetime.now(UTC)

    await deliveries.mark_seen(delivery, seen_at=seen_at)

    assert delivery.seen_at == seen_at
    assert (
        await deliveries.get_for_message_and_recipient(
            message.id, repository_graph.invitee.id
        )
        is delivery
    )


@pytest.mark.asyncio
async def test_ai_attempts_preserve_attempt_ordering(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    messages = MessageRepository(db_session)
    attempts = AIProcessingAttemptRepository(db_session)
    message = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="attempt-id",
        original_message="Original",
    )
    second = await attempts.create_attempt(
        message_id=message.id,
        attempt_number=2,
        provider="provider",
        model="model",
    )
    first = await attempts.create_attempt(
        message_id=message.id,
        attempt_number=1,
        provider="provider",
        model="model",
    )

    ordered = await attempts.list_by_message(message.id)

    assert ordered == [first, second]
    assert await attempts.get_latest_for_message(message.id) is second


@pytest.mark.asyncio
async def test_guidance_queries_are_isolated_by_participant(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    messages = MessageRepository(db_session)
    guidance = PrivateGuidanceRepository(db_session)
    message = await messages.create_processing_message(
        conversation_id=repository_graph.conversation.id,
        sender_id=repository_graph.creator.id,
        client_message_id="guidance-id",
        original_message="Original",
    )
    creator_guidance = await guidance.create(
        conversation_id=repository_graph.conversation.id,
        message_id=message.id,
        participant_id=repository_graph.creator.id,
        audience=GuidanceAudience.SENDER,
        guidance_type=GuidanceType.COMMUNICATION_SUPPORT,
        guidance_text="Creator-only guidance",
    )
    invitee_guidance = await guidance.create(
        conversation_id=repository_graph.conversation.id,
        message_id=message.id,
        participant_id=repository_graph.invitee.id,
        audience=GuidanceAudience.RECIPIENT,
        guidance_type=GuidanceType.CLARIFICATION,
        guidance_text="Invitee-only guidance",
    )

    creator_results = await guidance.list_for_participant(repository_graph.creator.id)
    invitee_results = await guidance.list_for_participant_and_message(
        repository_graph.invitee.id, message.id
    )

    assert creator_results == [creator_guidance]
    assert invitee_results == [invitee_guidance]
