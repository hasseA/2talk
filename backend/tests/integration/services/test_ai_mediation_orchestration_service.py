"""PostgreSQL-backed tests for the three-phase mediation workflow."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.ai.exceptions import AIOutputValidationError, AIProviderError, AITimeoutError
from app.ai.models import (
    GuidanceType as AIGuidanceType,
)
from app.ai.models import (
    MediationRequest,
    MediationResult,
    MediationStatus,
    PrivateGuidanceResult,
)
from app.models import (
    AIProcessingAttempt,
    GuidanceAudience,
    GuidanceType,
    Message,
    MessageDelivery,
    MessageStatus,
    PrivateGuidance,
    ProcessingAttemptStatus,
)
from app.repositories import (
    AIProcessingAttemptRepository,
    MessageDeliveryRepository,
    MessageRepository,
    PrivateGuidanceRepository,
)
from app.services import (
    AIMediationOrchestrationService,
    MediationOutcomeStatus,
    MessageLifecycleService,
)
from tests.integration.services.conftest import ActiveConversation


class FakeAIProvider:
    def __init__(
        self,
        result: MediationResult | None = None,
        *,
        error: Exception | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.session = session
        self.calls: list[MediationRequest] = []
        self.called_outside_transaction: bool | None = None

    async def mediate_message(self, request: MediationRequest) -> MediationResult:
        self.calls.append(request)
        if self.session is not None:
            self.called_outside_transaction = not self.session.in_transaction()
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class BlockingAIProvider(FakeAIProvider):
    def __init__(self, result: MediationResult, *, session: AsyncSession) -> None:
        super().__init__(result, session=session)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def mediate_message(self, request: MediationRequest) -> MediationResult:
        self.calls.append(request)
        self.called_outside_transaction = not self.session.in_transaction()
        self.entered.set()
        await self.release.wait()
        assert self.result is not None
        return self.result


def delivered_result(
    *,
    mediated_message: str = "A calm mediated message",
    sender_guidance: PrivateGuidanceResult | None = None,
    recipient_guidance: PrivateGuidanceResult | None = None,
) -> MediationResult:
    return MediationResult(
        status=MediationStatus.DELIVERED,
        mediated_message=mediated_message,
        delivered_language="en",
        sender_guidance=sender_guidance,
        recipient_guidance=recipient_guidance,
        detected_language="sv",
        emotion="frustrated",
        communication_goal="be understood",
        requires_pause=False,
        blocking_reason=None,
    )


def blocked_result() -> MediationResult:
    return MediationResult(
        status=MediationStatus.BLOCKED,
        mediated_message=None,
        delivered_language=None,
        sender_guidance=PrivateGuidanceResult(
            type=AIGuidanceType.SAFETY_NOTICE,
            text="This message was not delivered for safety reasons.",
        ),
        recipient_guidance=None,
        detected_language="sv",
        emotion="threatening",
        communication_goal=None,
        requires_pause=True,
        blocking_reason="credible threat",
    )


async def create_message(
    session: AsyncSession,
    active: ActiveConversation,
    *,
    client_message_id: str,
    original_message: str = "A raw private message",
) -> Message:
    return await MessageLifecycleService(session).create_processing_message(
        conversation_id=active.created.conversation.id,
        sender_id=active.created.creator.id,
        client_message_id=client_message_id,
        original_message=original_message,
        original_language="sv",
    )


def orchestration(
    session: AsyncSession, provider: FakeAIProvider
) -> AIMediationOrchestrationService:
    return AIMediationOrchestrationService(
        session,
        provider,
        provider_name="fake",
        model="fake-mediation-v1",
    )


@pytest.mark.asyncio
async def test_delivered_outcome_is_atomic_private_and_recipient_safe(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="orchestrated-delivery"
    )
    provider = FakeAIProvider(
        delivered_result(
            sender_guidance=PrivateGuidanceResult(
                type=AIGuidanceType.COMMUNICATION_SUPPORT,
                text="Sender-only support",
            ),
            recipient_guidance=PrivateGuidanceResult(
                type=AIGuidanceType.CLARIFICATION,
                text="Recipient-only clarification",
            ),
        ),
        session=db_session,
    )

    outcome = await orchestration(db_session, provider).process_message(message.id)

    assert outcome.status is MediationOutcomeStatus.DELIVERED
    assert provider.called_outside_transaction is True
    stored = await db_session.get(Message, message.id)
    assert stored is not None
    assert stored.status is MessageStatus.DELIVERED
    assert stored.mediated_message == "A calm mediated message"
    assert stored.delivered_language == "en"
    assert stored.communication_goal == "be understood"
    assert stored.detected_emotion == "frustrated"
    assert stored.delivered_at is not None

    deliveries = await MessageDeliveryRepository(db_session).list_for_recipient(
        active_conversation.joined.participant.id
    )
    assert len(deliveries) == 1
    sender_guidance = await PrivateGuidanceRepository(db_session).list_for_participant(
        active_conversation.created.creator.id
    )
    recipient_guidance = await PrivateGuidanceRepository(
        db_session
    ).list_for_participant(active_conversation.joined.participant.id)
    assert [item.guidance_text for item in sender_guidance] == ["Sender-only support"]
    assert [item.guidance_text for item in recipient_guidance] == [
        "Recipient-only clarification"
    ]
    incoming = await MessageRepository(db_session).list_incoming_for_recipient(
        active_conversation.created.conversation.id,
        active_conversation.joined.participant.id,
    )
    assert len(incoming) == 1
    assert not hasattr(incoming[0], "original_message")


@pytest.mark.asyncio
async def test_blocked_outcome_has_sender_guidance_but_no_recipient_artifacts(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="orchestrated-block"
    )

    outcome = await orchestration(
        db_session, FakeAIProvider(blocked_result())
    ).process_message(message.id)

    assert outcome.status is MediationOutcomeStatus.BLOCKED
    stored = await db_session.get(Message, message.id)
    assert stored is not None
    assert stored.status is MessageStatus.BLOCKED
    assert stored.mediated_message is None
    assert stored.blocked_at is not None
    assert await db_session.scalar(select(func.count(MessageDelivery.id))) == 0
    guidance = list((await db_session.scalars(select(PrivateGuidance))).all())
    assert len(guidance) == 1
    assert guidance[0].participant_id == active_conversation.created.creator.id
    assert guidance[0].audience is GuidanceAudience.SENDER
    attempt = await AIProcessingAttemptRepository(db_session).get_latest_for_message(
        message.id
    )
    assert attempt is not None
    assert attempt.status is ProcessingAttemptStatus.REJECTED
    assert attempt.error_code == "AI_BLOCKED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_factory", "expected_code"),
    [
        (lambda: AITimeoutError("secret timeout detail"), "AI_TIMEOUT"),
        (lambda: AIProviderError("secret SDK detail"), "AI_PROVIDER_ERROR"),
        (
            lambda: AIOutputValidationError("secret invalid output"),
            "AI_RESPONSE_INVALID",
        ),
    ],
)
async def test_expected_provider_failure_is_sanitized_and_undelivered(
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    error_factory: Callable[[], Exception],
    expected_code: str,
) -> None:
    message = await create_message(
        db_session,
        active_conversation,
        client_message_id=f"failure-{expected_code}",
    )

    outcome = await orchestration(
        db_session, FakeAIProvider(error=error_factory())
    ).process_message(message.id)

    assert outcome.status is MediationOutcomeStatus.FAILED
    stored = await db_session.get(Message, message.id)
    assert stored is not None
    assert stored.status is MessageStatus.FAILED
    assert stored.failure_code == expected_code
    attempt = await AIProcessingAttemptRepository(db_session).get_latest_for_message(
        message.id
    )
    assert attempt is not None
    assert attempt.status is ProcessingAttemptStatus.FAILED
    assert attempt.error_code == expected_code
    assert attempt.error_message is None
    assert await db_session.scalar(select(func.count(MessageDelivery.id))) == 0
    assert await db_session.scalar(select(func.count(PrivateGuidance.id))) == 0


@pytest.mark.asyncio
async def test_phase_three_error_rolls_back_every_outcome_write(
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="phase-three-rollback"
    )
    message_id = message.id
    original_mark_completed = AIProcessingAttemptRepository.mark_completed

    async def fail_after_outcome_writes(*args, **kwargs):
        await original_mark_completed(*args, **kwargs)
        raise RuntimeError("simulated finalization failure")

    monkeypatch.setattr(
        AIProcessingAttemptRepository, "mark_completed", fail_after_outcome_writes
    )

    with pytest.raises(RuntimeError, match="simulated finalization failure"):
        await orchestration(
            db_session,
            FakeAIProvider(
                delivered_result(
                    sender_guidance=PrivateGuidanceResult(
                        type=AIGuidanceType.CLARIFICATION,
                        text="Must roll back",
                    )
                )
            ),
        ).process_message(message_id)

    db_session.expire_all()
    stored = await db_session.get(Message, message_id)
    assert stored is not None
    assert stored.status is MessageStatus.PROCESSING
    assert stored.mediated_message is None
    assert await db_session.scalar(select(func.count(MessageDelivery.id))) == 0
    assert await db_session.scalar(select(func.count(PrivateGuidance.id))) == 0
    attempt = await AIProcessingAttemptRepository(db_session).get_latest_for_message(
        message_id
    )
    assert attempt is not None
    assert attempt.status is ProcessingAttemptStatus.STARTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "terminal_status"),
    [
        (delivered_result(), MessageStatus.DELIVERED),
        (blocked_result(), MessageStatus.BLOCKED),
    ],
)
async def test_finalized_message_is_idempotent(
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    result: MediationResult,
    terminal_status: MessageStatus,
) -> None:
    message = await create_message(
        db_session,
        active_conversation,
        client_message_id=f"idempotent-{terminal_status.value}",
    )
    provider = FakeAIProvider(result)
    service = orchestration(db_session, provider)

    await service.process_message(message.id)
    second = await service.process_message(message.id)

    assert second.status is MediationOutcomeStatus.ALREADY_FINALIZED
    assert second.message_status is terminal_status
    assert len(provider.calls) == 1
    assert await db_session.scalar(
        select(func.count(MessageDelivery.id)).where(
            MessageDelivery.message_id == message.id
        )
    ) == (1 if terminal_status is MessageStatus.DELIVERED else 0)


@pytest.mark.asyncio
async def test_concurrent_processing_makes_one_provider_call_and_one_delivery(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="concurrent-claim"
    )
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as first_session, session_factory() as second_session:
        provider = BlockingAIProvider(delivered_result(), session=first_session)
        first_task = asyncio.create_task(
            orchestration(first_session, provider).process_message(message.id)
        )
        await asyncio.wait_for(provider.entered.wait(), timeout=5)

        second = await orchestration(second_session, provider).process_message(
            message.id
        )
        provider.release.set()
        first = await asyncio.wait_for(first_task, timeout=5)

    assert first.status is MediationOutcomeStatus.DELIVERED
    assert second.status is MediationOutcomeStatus.ALREADY_PROCESSING
    assert len(provider.calls) == 1
    assert provider.called_outside_transaction is True
    assert (
        await db_session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.message_id == message.id
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_stale_attempt_cannot_overwrite_a_newer_final_outcome(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="stale-attempt"
    )
    message_id = message.id
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with (
        session_factory() as worker_session,
        session_factory() as control_session,
    ):
        provider = BlockingAIProvider(delivered_result(), session=worker_session)
        task = asyncio.create_task(
            orchestration(worker_session, provider).process_message(message_id)
        )
        await asyncio.wait_for(provider.entered.wait(), timeout=5)
        async with control_session.begin():
            attempt_repository = AIProcessingAttemptRepository(control_session)
            replacement = await attempt_repository.create_attempt(
                message_id=message_id,
                attempt_number=2,
                provider="replacement",
                model="replacement-v1",
            )
            stored = await MessageRepository(control_session).get_by_id_for_update(
                message_id
            )
            assert stored is not None
            await MessageRepository(control_session).mark_delivered(
                stored,
                mediated_message="newer final outcome",
                delivered_language="en",
            )
            await MessageDeliveryRepository(control_session).create(
                message_id=message_id,
                recipient_id=active_conversation.joined.participant.id,
                delivered_at=stored.delivered_at,
            )
            await attempt_repository.mark_completed(replacement)
        provider.release.set()
        outcome = await asyncio.wait_for(task, timeout=5)

    assert outcome.status is MediationOutcomeStatus.ALREADY_FINALIZED
    db_session.expire_all()
    stored = await db_session.get(Message, message_id)
    assert stored is not None
    assert stored.status is MessageStatus.DELIVERED
    assert stored.mediated_message == "newer final outcome"
    assert await db_session.scalar(select(func.count(MessageDelivery.id))) == 1
    attempts = await AIProcessingAttemptRepository(db_session).list_by_message(
        message_id
    )
    assert [item.status for item in attempts] == [
        ProcessingAttemptStatus.REJECTED,
        ProcessingAttemptStatus.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_retry_creates_next_attempt_once_and_can_deliver(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="successful-retry"
    )
    failed = await orchestration(
        db_session, FakeAIProvider(error=AITimeoutError("timeout"))
    ).process_message(message.id)
    assert failed.status is MediationOutcomeStatus.FAILED

    retried = await MessageLifecycleService(db_session).retry_failed_message(
        conversation_id=active_conversation.created.conversation.id,
        sender_id=active_conversation.created.creator.id,
        message_id=message.id,
    )
    assert retried.retry_count == 1
    delivered = await orchestration(
        db_session, FakeAIProvider(delivered_result())
    ).process_message(message.id)

    assert delivered.status is MediationOutcomeStatus.DELIVERED
    attempts = await AIProcessingAttemptRepository(db_session).list_by_message(
        message.id
    )
    assert [item.attempt_number for item in attempts] == [1, 2]
    assert [item.status for item in attempts] == [
        ProcessingAttemptStatus.FAILED,
        ProcessingAttemptStatus.COMPLETED,
    ]
    stored = await db_session.get(Message, message.id)
    assert stored is not None
    assert stored.retry_count == 1
    assert (
        await db_session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.message_id == message.id
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_context_is_mediated_bounded_chronological_and_guidance_free(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    conversation_id = active_conversation.created.conversation.id
    creator_id = active_conversation.created.creator.id
    invitee_id = active_conversation.joined.participant.id
    base_time = datetime.now(UTC) - timedelta(days=1)
    async with db_session.begin():
        messages = MessageRepository(db_session)
        deliveries = MessageDeliveryRepository(db_session)
        guidance = PrivateGuidanceRepository(db_session)
        for index in range(52):
            sender_id = creator_id if index % 2 == 0 else invitee_id
            recipient_id = invitee_id if index % 2 == 0 else creator_id
            message = await messages.create_processing_message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                client_message_id=f"context-{index:02d}",
                original_message=f"RAW SECRET {index}",
                original_language="sv" if sender_id == creator_id else "en",
            )
            message.created_at = base_time + timedelta(seconds=index)
            await messages.mark_delivered(
                message,
                mediated_message=f"mediated-{index:02d}",
                delivered_language="en" if recipient_id == invitee_id else "sv",
            )
            await deliveries.create(
                message_id=message.id,
                recipient_id=recipient_id,
                delivered_at=message.delivered_at,
            )
            await guidance.create(
                conversation_id=conversation_id,
                message_id=message.id,
                participant_id=sender_id,
                audience=GuidanceAudience.SENDER,
                guidance_type=GuidanceType.CLARIFICATION,
                guidance_text=f"GUIDANCE SECRET {index}",
            )

    current = await create_message(
        db_session,
        active_conversation,
        client_message_id="context-current",
        original_message="Current raw message",
    )
    provider = FakeAIProvider(blocked_result())

    await orchestration(db_session, provider).process_message(current.id)

    assert len(provider.calls) == 1
    context = provider.calls[0].conversation_context
    assert len(context) == 50
    assert [item.mediated_message for item in context] == [
        f"mediated-{index:02d}" for index in range(2, 52)
    ]
    assert context[0].speaker == "sender"
    assert context[1].speaker == "recipient"
    serialized = provider.calls[0].model_dump_json()
    assert "RAW SECRET" not in serialized
    assert "GUIDANCE SECRET" not in serialized


@pytest.mark.asyncio
async def test_failure_finalization_never_creates_partial_delivery_or_guidance(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(
        db_session, active_conversation, client_message_id="no-partial-failure"
    )
    await orchestration(
        db_session, FakeAIProvider(error=AIProviderError("provider failed"))
    ).process_message(message.id)

    assert await db_session.scalar(select(func.count(MessageDelivery.id))) == 0
    assert await db_session.scalar(select(func.count(PrivateGuidance.id))) == 0
    attempt_count = await db_session.scalar(
        select(func.count(AIProcessingAttempt.id)).where(
            AIProcessingAttempt.message_id == message.id
        )
    )
    assert attempt_count == 1
