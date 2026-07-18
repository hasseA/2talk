"""Transactional message lifecycle and rollback tests."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    GuidanceAudience,
    GuidanceType,
    MessageDelivery,
    MessageStatus,
    PrivateGuidance,
)
from app.services import GuidanceInput, MessageLifecycleService, MessageStateError
from tests.integration.services.conftest import ActiveConversation


@pytest.mark.asyncio
async def test_create_processing_message(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)

    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="processing-message",
        original_message="Original message",
        original_language="sv",
    )

    assert message.status is MessageStatus.PROCESSING
    assert message.original_message == "Original message"


@pytest.mark.asyncio
async def test_mark_delivered_commits_message_delivery_and_guidance(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)
    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="delivered-message",
        original_message="Original message",
    )
    delivered_at = datetime.now(UTC)

    delivered = await service.mark_delivered(
        message_id=message.id,
        recipient_id=active_conversation.joined.participant.id,
        mediated_message="Mediated message",
        delivered_language="en",
        delivered_at=delivered_at,
        guidance=(
            GuidanceInput(
                participant_id=active_conversation.created.creator.id,
                audience=GuidanceAudience.SENDER,
                guidance_type=GuidanceType.COMMUNICATION_SUPPORT,
                guidance_text="Sender guidance",
            ),
            GuidanceInput(
                participant_id=active_conversation.joined.participant.id,
                audience=GuidanceAudience.RECIPIENT,
                guidance_type=GuidanceType.CLARIFICATION,
                guidance_text="Recipient guidance",
            ),
        ),
    )

    assert delivered.status is MessageStatus.DELIVERED
    assert delivered.mediated_message == "Mediated message"
    assert delivered.delivered_at == delivered_at
    assert (
        await db_session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.message_id == message.id
            )
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(PrivateGuidance.id)).where(
                PrivateGuidance.message_id == message.id
            )
        )
        == 2
    )


@pytest.mark.asyncio
async def test_mark_failed_leaves_message_undelivered(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)
    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="failed-message",
        original_message="Original message",
    )

    failed = await service.mark_failed(message.id, failure_code="AI_UNAVAILABLE")

    assert failed.status is MessageStatus.FAILED
    assert failed.failure_code == "AI_UNAVAILABLE"
    assert (
        await db_session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.message_id == message.id
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_mark_blocked_sets_block_timestamp(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)
    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="blocked-message",
        original_message="Original message",
    )

    blocked = await service.mark_blocked(message.id, failure_code="SAFETY_BLOCK")

    assert blocked.status is MessageStatus.BLOCKED
    assert blocked.failure_code == "SAFETY_BLOCK"
    assert blocked.blocked_at is not None


@pytest.mark.asyncio
async def test_retry_increments_counter_and_returns_to_processing(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)
    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="retry-message",
        original_message="Original message",
    )
    await service.mark_failed(message.id, failure_code="TEMPORARY_FAILURE")

    retried = await service.increment_retry(message.id)

    assert retried.retry_count == 1
    assert retried.status is MessageStatus.PROCESSING
    assert retried.failure_code is None


@pytest.mark.asyncio
async def test_invalid_message_transition_rolls_back(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)
    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="invalid-transition",
        original_message="Original message",
    )
    await service.mark_blocked(message.id)

    with pytest.raises(MessageStateError):
        await service.mark_delivered(
            message_id=message.id,
            recipient_id=active_conversation.joined.participant.id,
            mediated_message="Must not deliver",
            delivered_language="en",
        )

    await db_session.refresh(message)
    assert message.status is MessageStatus.BLOCKED
    assert message.mediated_message is None


@pytest.mark.asyncio
async def test_delivery_failure_rolls_back_message_and_delivery(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = MessageLifecycleService(db_session)
    message = await service.create_processing_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        client_message_id="rollback-delivery",
        original_message="Original message",
    )

    with pytest.raises(IntegrityError):
        await service.mark_delivered(
            message_id=message.id,
            recipient_id=active_conversation.joined.participant.id,
            mediated_message="Mediated message",
            delivered_language="en",
            guidance=(
                GuidanceInput(
                    participant_id=active_conversation.created.creator.id,
                    audience=GuidanceAudience.SENDER,
                    guidance_type=GuidanceType.CLARIFICATION,
                    guidance_text="   ",
                ),
            ),
        )

    await db_session.refresh(message)
    assert message.status is MessageStatus.PROCESSING
    assert message.mediated_message is None
    assert (
        await db_session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.message_id == message.id
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_processing_message_rejects_inactive_conversation(
    db_session: AsyncSession, service_settings
) -> None:
    from datetime import timedelta

    from app.services import ConversationService

    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="en",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    with pytest.raises(MessageStateError):
        await MessageLifecycleService(db_session).create_processing_message(
            conversation_id=created.conversation.id,
            sender_id=created.creator.id,
            client_message_id="waiting-conversation",
            original_message="Not allowed yet",
        )
