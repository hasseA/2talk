"""PostgreSQL integration tests for durable mediation jobs and recovery."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.ai.exceptions import AITimeoutError
from app.ai.models import MediationRequest, MediationResult, MediationStatus
from app.models import (
    AIMediationJob,
    MediationJobStatus,
    Message,
    MessageDelivery,
    MessageStatus,
    ProcessingAttemptStatus,
)
from app.repositories import (
    AIMediationJobRepository,
    AIProcessingAttemptRepository,
    MessageDeliveryRepository,
    MessageRepository,
)
from app.services import AIMediationOrchestrationService, MessageLifecycleService
from app.workers.ai_mediation_worker import AIMediationWorker
from tests.integration.services.conftest import ActiveConversation


class FakeProvider:
    def __init__(
        self, result: MediationResult | None = None, *, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[MediationRequest] = []

    async def mediate_message(self, request: MediationRequest) -> MediationResult:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def delivered_result() -> MediationResult:
    return MediationResult(
        status=MediationStatus.DELIVERED,
        mediated_message="durably mediated",
        delivered_language="en",
        sender_guidance=None,
        recipient_guidance=None,
        detected_language="sv",
        emotion=None,
        communication_goal=None,
        requires_pause=False,
        blocking_reason=None,
    )


def blocked_result() -> MediationResult:
    return MediationResult(
        status=MediationStatus.BLOCKED,
        mediated_message=None,
        delivered_language=None,
        sender_guidance=None,
        recipient_guidance=None,
        detected_language="sv",
        emotion=None,
        communication_goal=None,
        requires_pause=True,
        blocking_reason="safety policy",
    )


async def create_message(
    session: AsyncSession,
    active: ActiveConversation,
    client_message_id: str,
) -> Message:
    return await MessageLifecycleService(session).create_processing_message(
        conversation_id=active.created.conversation.id,
        sender_id=active.created.creator.id,
        client_message_id=client_message_id,
        original_message="private original",
        original_language="sv",
    )


@pytest.mark.asyncio
async def test_message_creation_atomically_enqueues_one_job(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(db_session, active_conversation, "atomic-enqueue")

    job = await AIMediationJobRepository(db_session).get_by_message_id(message.id)
    assert job is not None
    assert job.status is MediationJobStatus.QUEUED
    assert job.attempt_count == 0
    assert (
        await db_session.scalar(
            select(func.count(AIMediationJob.id)).where(
                AIMediationJob.message_id == message.id
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_message_and_job_roll_back_together(
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_enqueue(*args, **kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        AIMediationJobRepository, "ensure_job_for_message", fail_enqueue
    )
    with pytest.raises(RuntimeError, match="queue unavailable"):
        await create_message(db_session, active_conversation, "rollback-enqueue")

    assert await db_session.scalar(select(func.count(Message.id))) == 0
    assert await db_session.scalar(select(func.count(AIMediationJob.id))) == 0


@pytest.mark.asyncio
async def test_duplicate_ensure_reuses_database_unique_job(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(db_session, active_conversation, "ensure-once")
    async with db_session.begin():
        repository = AIMediationJobRepository(db_session)
        first = await repository.ensure_job_for_message(message.id)
        second = await repository.ensure_job_for_message(message.id)

    assert first.id == second.id
    assert await db_session.scalar(select(func.count(AIMediationJob.id))) == 1


@pytest.mark.asyncio
async def test_retry_reactivates_same_job_and_increments_product_retry_once(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(db_session, active_conversation, "reactivate-job")
    message_id = message.id
    conversation_id = active_conversation.created.conversation.id
    sender_id = active_conversation.created.creator.id
    original_job = await AIMediationJobRepository(db_session).get_by_message_id(
        message_id
    )
    assert original_job is not None
    original_job_id = original_job.id
    await db_session.rollback()
    await MessageLifecycleService(db_session).mark_failed(
        message_id, failure_code="AI_TIMEOUT"
    )
    async with db_session.begin():
        locked_job = await AIMediationJobRepository(
            db_session
        ).get_by_message_id_for_update(message_id)
        assert locked_job is not None
        locked_job.status = MediationJobStatus.DEAD
        locked_job.completed_at = datetime.now(UTC)

    retried = await MessageLifecycleService(db_session).retry_failed_message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        message_id=message_id,
    )

    job = await AIMediationJobRepository(db_session).get_by_message_id(message_id)
    assert job is not None
    assert job.id == original_job_id
    assert job.status is MediationJobStatus.QUEUED
    assert retried.retry_count == 1


@pytest.mark.asyncio
async def test_claims_are_leased_and_concurrent_sessions_claim_different_jobs(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
) -> None:
    first_message = await create_message(db_session, active_conversation, "claim-1")
    second_message = await create_message(db_session, active_conversation, "claim-2")
    now = datetime.now(UTC)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as first_session, factory() as second_session:
        async with first_session.begin():
            first = await AIMediationJobRepository(
                first_session
            ).claim_next_available_job(now=now, lease_duration=timedelta(seconds=60))
        async with second_session.begin():
            second = await AIMediationJobRepository(
                second_session
            ).claim_next_available_job(now=now, lease_duration=timedelta(seconds=60))

    assert first is not None and second is not None
    assert {first.message_id, second.message_id} == {
        first_message.id,
        second_message.id,
    }
    assert first.id != second.id
    assert first.lease_token is not None
    assert first.lease_expires_at == now + timedelta(seconds=60)
    assert first.attempt_count == 1


@pytest.mark.asyncio
async def test_two_workers_cannot_claim_the_same_job(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
) -> None:
    await create_message(db_session, active_conversation, "single-claim")
    now = datetime.now(UTC)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as first_session, factory() as second_session:
        async with first_session.begin():
            first = await AIMediationJobRepository(
                first_session
            ).claim_next_available_job(now=now, lease_duration=timedelta(seconds=60))
        async with second_session.begin():
            second = await AIMediationJobRepository(
                second_session
            ).claim_next_available_job(now=now, lease_duration=timedelta(seconds=60))

    assert first is not None
    assert second is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected_message_status"),
    [
        (delivered_result(), MessageStatus.DELIVERED),
        (blocked_result(), MessageStatus.BLOCKED),
    ],
)
async def test_worker_completes_delivered_and_blocked_jobs(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
    result: MediationResult,
    expected_message_status: MessageStatus,
) -> None:
    message = await create_message(
        db_session,
        active_conversation,
        f"worker-{expected_message_status.value}",
    )
    message_id = message.id
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    provider = FakeProvider(result)
    worker = AIMediationWorker(factory, provider, service_settings)

    assert await worker.run_once() is True

    db_session.expire_all()
    stored = await db_session.get(Message, message_id)
    job = await AIMediationJobRepository(db_session).get_by_message_id(message_id)
    assert stored is not None and job is not None
    assert stored.status is expected_message_status
    assert job.status is MediationJobStatus.COMPLETED
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_worker_failure_dead_letters_until_explicit_retry(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
) -> None:
    message = await create_message(db_session, active_conversation, "worker-failed")
    message_id = message.id
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    worker = AIMediationWorker(
        factory,
        FakeProvider(error=AITimeoutError("not persisted")),
        service_settings,
    )

    await worker.run_once()

    db_session.expire_all()
    stored = await db_session.get(Message, message_id)
    job = await AIMediationJobRepository(db_session).get_by_message_id(message_id)
    assert stored is not None and job is not None
    assert stored.status is MessageStatus.FAILED
    assert job.status is MediationJobStatus.DEAD
    assert job.last_error_category == "AI_PROCESSING_FAILED"
    assert job.lease_token is None


@pytest.mark.asyncio
async def test_worker_reconciles_already_finalized_message_without_provider_call(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
) -> None:
    message = await create_message(db_session, active_conversation, "already-final")
    message_id = message.id
    await MessageLifecycleService(db_session).mark_delivered(
        message_id=message_id,
        recipient_id=active_conversation.joined.participant.id,
        mediated_message="already done",
        delivered_language="en",
    )
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    provider = FakeProvider(delivered_result())

    worker = AIMediationWorker(factory, provider, service_settings)
    assert await worker.run_once() is True

    db_session.expire_all()
    job = await AIMediationJobRepository(db_session).get_by_message_id(message_id)
    assert job is not None
    assert job.status is MediationJobStatus.COMPLETED
    assert provider.calls == []


@pytest.mark.asyncio
async def test_superseded_lease_token_cannot_finalize_job(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    await create_message(db_session, active_conversation, "stale-token")
    now = datetime.now(UTC)
    async with db_session.begin():
        repository = AIMediationJobRepository(db_session)
        job = await repository.claim_next_available_job(
            now=now, lease_duration=timedelta(seconds=60)
        )
        assert job is not None and job.lease_token is not None
        stale_token = job.lease_token
        replacement_token = uuid4()
        job.lease_token = replacement_token
        assert (
            await repository.mark_completed(
                job, lease_token=stale_token, now=now + timedelta(seconds=1)
            )
            is False
        )
        assert job.status is MediationJobStatus.LEASED


@pytest.mark.asyncio
async def test_expired_empty_lease_is_requeued_but_valid_lease_is_not(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
) -> None:
    message = await create_message(db_session, active_conversation, "lease-recovery")
    message_id = message.id
    now = datetime.now(UTC)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with db_session.begin():
        job = await AIMediationJobRepository(db_session).claim_next_available_job(
            now=now, lease_duration=timedelta(seconds=30)
        )
    assert job is not None
    valid_worker = AIMediationWorker(
        factory,
        FakeProvider(delivered_result()),
        service_settings,
        now_factory=lambda: now,
    )
    assert await valid_worker.recover_expired_leases() == 0

    expired_now = now + timedelta(seconds=31)
    expired_worker = AIMediationWorker(
        factory,
        FakeProvider(delivered_result()),
        service_settings,
        now_factory=lambda: expired_now,
    )
    assert await expired_worker.recover_expired_leases() == 1
    db_session.expire_all()
    recovered = await AIMediationJobRepository(db_session).get_by_message_id(message_id)
    assert recovered is not None
    assert recovered.status is MediationJobStatus.QUEUED
    assert recovered.lease_token is None


@pytest.mark.asyncio
async def test_stale_attempt_recovery_requeues_without_product_retry_increment(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
) -> None:
    message = await create_message(db_session, active_conversation, "stale-recovery")
    message_id = message.id
    old = datetime.now(UTC) - timedelta(minutes=5)
    async with db_session.begin():
        jobs = AIMediationJobRepository(db_session)
        job = await jobs.claim_next_available_job(
            now=datetime.now(UTC), lease_duration=timedelta(seconds=30)
        )
        assert job is not None and job.lease_token is not None
        job.lease_expires_at = old + timedelta(seconds=30)
        attempt = await AIProcessingAttemptRepository(db_session).create_attempt(
            message_id=message_id,
            attempt_number=1,
            provider="fake",
            model="fake-v1",
            execution_lease_token=job.lease_token,
        )
        attempt.request_started_at = old

    now = datetime.now(UTC)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    worker = AIMediationWorker(
        factory,
        FakeProvider(delivered_result()),
        service_settings,
        now_factory=lambda: now,
    )
    assert await worker.recover_expired_leases() == 1

    db_session.expire_all()
    job = await AIMediationJobRepository(db_session).get_by_message_id(message_id)
    attempts = await AIProcessingAttemptRepository(db_session).list_by_message(
        message_id
    )
    stored = await db_session.get(Message, message_id)
    assert job is not None and stored is not None
    assert job.status is MediationJobStatus.QUEUED
    assert attempts[0].status is ProcessingAttemptStatus.REJECTED
    assert attempts[0].error_code == "WORKER_LEASE_EXPIRED"
    assert stored.retry_count == 0

    assert await worker.run_once() is True
    db_session.expire_all()
    attempts = await AIProcessingAttemptRepository(db_session).list_by_message(
        message_id
    )
    assert [item.attempt_number for item in attempts] == [1, 2]
    assert attempts[1].status is ProcessingAttemptStatus.COMPLETED
    stored = await db_session.get(Message, message_id)
    assert stored is not None
    assert stored.retry_count == 0
    assert (
        await db_session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.message_id == message_id
            )
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status", [MessageStatus.DELIVERED, MessageStatus.BLOCKED]
)
async def test_recovery_never_changes_terminal_message_or_started_attempt(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
    terminal_status: MessageStatus,
) -> None:
    message = await create_message(
        db_session, active_conversation, f"terminal-{terminal_status.value}"
    )
    message_id = message.id
    old = datetime.now(UTC) - timedelta(minutes=5)
    async with db_session.begin():
        jobs = AIMediationJobRepository(db_session)
        job = await jobs.claim_next_available_job(
            now=datetime.now(UTC), lease_duration=timedelta(seconds=30)
        )
        assert job is not None and job.lease_token is not None
        job.lease_expires_at = old + timedelta(seconds=30)
        attempt = await AIProcessingAttemptRepository(db_session).create_attempt(
            message_id=message_id,
            attempt_number=1,
            provider="fake",
            model="fake-v1",
            execution_lease_token=job.lease_token,
        )
        attempt.request_started_at = old
        if terminal_status is MessageStatus.DELIVERED:
            await MessageRepository(db_session).mark_delivered(
                message, mediated_message="existing", delivered_language="en"
            )
            await MessageDeliveryRepository(db_session).create(
                message_id=message_id,
                recipient_id=active_conversation.joined.participant.id,
                delivered_at=message.delivered_at,
            )
        else:
            await MessageRepository(db_session).mark_blocked(message)

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    worker = AIMediationWorker(
        factory,
        FakeProvider(delivered_result()),
        service_settings,
        now_factory=lambda: datetime.now(UTC),
    )
    assert await worker.recover_expired_leases() == 1
    db_session.expire_all()
    attempt = await AIProcessingAttemptRepository(db_session).get_latest_for_message(
        message_id
    )
    assert attempt is not None
    assert attempt.status is ProcessingAttemptStatus.STARTED


@pytest.mark.asyncio
async def test_recovery_does_not_reject_newer_attempt(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    active_conversation: ActiveConversation,
    service_settings,
) -> None:
    message = await create_message(db_session, active_conversation, "newer-attempt")
    message_id = message.id
    old = datetime.now(UTC) - timedelta(minutes=5)
    async with db_session.begin():
        job = await AIMediationJobRepository(db_session).claim_next_available_job(
            now=datetime.now(UTC), lease_duration=timedelta(seconds=30)
        )
        assert job is not None and job.lease_token is not None
        job.lease_expires_at = old + timedelta(seconds=30)
        attempts = AIProcessingAttemptRepository(db_session)
        first = await attempts.create_attempt(
            message_id=message_id,
            attempt_number=1,
            provider="fake",
            model="fake-v1",
            execution_lease_token=job.lease_token,
        )
        first.request_started_at = old
        newer = await attempts.create_attempt(
            message_id=message_id,
            attempt_number=2,
            provider="other",
            model="other-v1",
        )
        newer.request_started_at = old

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    worker = AIMediationWorker(
        factory,
        FakeProvider(delivered_result()),
        service_settings,
        now_factory=lambda: datetime.now(UTC),
    )
    assert await worker.recover_expired_leases() == 0
    db_session.expire_all()
    stored_attempts = await AIProcessingAttemptRepository(db_session).list_by_message(
        message_id
    )
    assert [item.status for item in stored_attempts] == [
        ProcessingAttemptStatus.STARTED,
        ProcessingAttemptStatus.STARTED,
    ]


@pytest.mark.asyncio
async def test_expired_lease_holder_cannot_finalize_message_or_job(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    message = await create_message(db_session, active_conversation, "expired-owner")
    message_id = message.id
    old = datetime.now(UTC) - timedelta(minutes=5)
    async with db_session.begin():
        job = await AIMediationJobRepository(db_session).claim_next_available_job(
            now=datetime.now(UTC), lease_duration=timedelta(seconds=1)
        )
        assert job is not None
        job.lease_expires_at = old + timedelta(seconds=1)
    assert job is not None and job.lease_token is not None
    provider = FakeProvider(delivered_result())

    outcome = await AIMediationOrchestrationService(
        db_session,
        provider,
        provider_name="fake",
        model="fake-v1",
        execution_lease_token=job.lease_token,
    ).process_message(message_id)

    assert outcome.status.value == "stale_attempt"
    assert len(provider.calls) == 0
    db_session.expire_all()
    stored = await db_session.get(Message, message_id)
    assert stored is not None
    assert stored.status is MessageStatus.PROCESSING
    assert await db_session.scalar(select(func.count(MessageDelivery.id))) == 0


@pytest.mark.asyncio
async def test_worker_with_pre_set_stop_event_exits_cleanly(
    db_engine: AsyncEngine, service_settings
) -> None:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    worker = AIMediationWorker(
        factory, FakeProvider(delivered_result()), service_settings
    )
    stop_event = asyncio.Event()
    stop_event.set()

    await asyncio.wait_for(worker.run(stop_event), timeout=1)
