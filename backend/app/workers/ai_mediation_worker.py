"""Dedicated PostgreSQL-backed worker for durable message mediation."""

import asyncio
import logging
import signal
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.factory import create_ai_provider
from app.ai.provider import AIProvider
from app.config import Settings, get_settings
from app.models import MessageStatus, ProcessingAttemptStatus
from app.repositories import (
    AIMediationJobRepository,
    AIProcessingAttemptRepository,
    MessageDeliveryRepository,
    MessageRepository,
)
from app.services import (
    AIMediationOrchestrationService,
    MediationOutcome,
    MediationOutcomeStatus,
)

logger = logging.getLogger(__name__)


class AIMediationWorker:
    """Claim durable jobs, execute orchestration, and finalize queue state."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: AIProvider,
        settings: Settings,
        *,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.settings = settings
        self.now_factory = now_factory or (lambda: datetime.now(UTC))

    async def run_once(self) -> bool:
        """Recover expired work, then claim and execute at most one job."""
        await self.recover_expired_leases()
        now = self.now_factory()
        async with self.session_factory() as session:
            async with session.begin():
                job = await AIMediationJobRepository(session).claim_next_available_job(
                    now=now,
                    lease_duration=timedelta(
                        seconds=self.settings.ai_job_lease_seconds
                    ),
                )
                if job is None:
                    return False
                job_id = job.id
                message_id = job.message_id
                lease_token = job.lease_token
                attempt_count = job.attempt_count
                lease_expires_at = job.lease_expires_at
        assert lease_token is not None
        logger.info(
            "claimed mediation job job_id=%s message_id=%s attempt_count=%s "
            "lease_expires_at=%s",
            job_id,
            message_id,
            attempt_count,
            lease_expires_at,
        )

        try:
            async with self.session_factory() as session:
                outcome = await AIMediationOrchestrationService(
                    session,
                    self.provider,
                    provider_name="openai",
                    model=self.settings.openai_model,
                    execution_lease_token=lease_token,
                ).process_message(message_id)
        except Exception:
            logger.exception(
                "unexpected mediation worker failure job_id=%s message_id=%s",
                job_id,
                message_id,
            )
            return True

        await self._finalize_job(job_id, lease_token, outcome)
        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        """Poll until graceful shutdown is requested."""
        while not stop_event.is_set():
            processed = await self.run_once()
            if processed:
                continue
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.settings.ai_job_poll_interval_seconds,
                )
            except TimeoutError:
                pass

    async def recover_expired_leases(self) -> int:
        """Recover abandoned leases and stale attempts in one transaction."""
        now = self.now_factory()
        stale_before = now - timedelta(seconds=self.settings.ai_attempt_stale_seconds)
        recovered = 0
        async with self.session_factory() as session:
            async with session.begin():
                jobs = AIMediationJobRepository(session)
                attempts = AIProcessingAttemptRepository(session)
                messages = MessageRepository(session)
                deliveries = MessageDeliveryRepository(session)
                for job in await jobs.list_expired_leases_for_update(now=now):
                    message = await messages.get_by_id_for_update(job.message_id)
                    if message is None:
                        await jobs.mark_cancelled(
                            job, now=now, error_category="MESSAGE_NOT_FOUND"
                        )
                        recovered += 1
                        continue
                    if message.status in (
                        MessageStatus.DELIVERED,
                        MessageStatus.BLOCKED,
                    ):
                        await jobs.mark_cancelled(
                            job, now=now, error_category="ALREADY_FINALIZED"
                        )
                        recovered += 1
                        continue
                    if await deliveries.exists_for_message(message.id):
                        await jobs.mark_cancelled(
                            job, now=now, error_category="DELIVERY_EXISTS"
                        )
                        recovered += 1
                        continue
                    if message.status is MessageStatus.FAILED:
                        await jobs.mark_cancelled(
                            job, now=now, error_category="MESSAGE_FAILED"
                        )
                        recovered += 1
                        continue

                    latest = await attempts.get_latest_for_message_for_update(
                        message.id
                    )
                    if (
                        latest is None
                        or latest.status is not ProcessingAttemptStatus.STARTED
                    ):
                        await jobs.release_for_retry(job, available_at=now)
                        recovered += 1
                        continue
                    if latest.execution_lease_token != job.lease_token:
                        continue
                    if latest.request_started_at > stale_before:
                        continue
                    await attempts.mark_rejected(
                        latest,
                        error_code="WORKER_LEASE_EXPIRED",
                        error_message=None,
                        completed_at=now,
                    )
                    await jobs.release_for_retry(
                        job,
                        available_at=now,
                        error_category="WORKER_LEASE_EXPIRED",
                    )
                    recovered += 1
        return recovered

    async def _finalize_job(
        self, job_id: UUID, lease_token: UUID, outcome: MediationOutcome
    ) -> bool:
        now = self.now_factory()
        async with self.session_factory() as session:
            async with session.begin():
                repository = AIMediationJobRepository(session)
                job = await repository.get_by_id(job_id)
                if job is None:
                    return False
                # Lock the queue row before validating the ownership token.
                job = await repository.get_by_message_id_for_update(job.message_id)
                if job is None:
                    return False
                if outcome.status in (
                    MediationOutcomeStatus.DELIVERED,
                    MediationOutcomeStatus.BLOCKED,
                ):
                    return await repository.mark_completed(
                        job, lease_token=lease_token, now=now
                    )
                if outcome.status is MediationOutcomeStatus.FAILED:
                    return await repository.mark_dead(
                        job,
                        lease_token=lease_token,
                        now=now,
                        error_category="AI_PROCESSING_FAILED",
                    )
                if outcome.status is MediationOutcomeStatus.ALREADY_FINALIZED:
                    if outcome.message_status in (
                        MessageStatus.DELIVERED,
                        MessageStatus.BLOCKED,
                    ):
                        return await repository.mark_completed(
                            job, lease_token=lease_token, now=now
                        )
                    return await repository.mark_dead(
                        job,
                        lease_token=lease_token,
                        now=now,
                        error_category="MESSAGE_ALREADY_FAILED",
                    )
                # already_processing/stale_attempt remain leased. Expiry recovery
                # evaluates the associated started attempt without a hot retry loop.
                return False


async def _run_worker() -> None:
    settings = get_settings()
    provider = create_ai_provider(settings)
    from app.database.session import async_session_factory, dispose_engine

    worker = AIMediationWorker(async_session_factory, provider, settings)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            pass
    try:
        await worker.run(stop_event)
    finally:
        await dispose_engine()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_worker())


if __name__ == "__main__":
    main()
