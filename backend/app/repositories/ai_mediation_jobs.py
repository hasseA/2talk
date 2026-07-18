"""PostgreSQL-backed durable mediation job queue operations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models import AIMediationJob, MediationJobStatus
from app.repositories.base import BaseRepository


class AIMediationJobRepository(BaseRepository[AIMediationJob]):
    model = AIMediationJob

    async def ensure_job_for_message(
        self, message_id: UUID, *, available_at: datetime | None = None
    ) -> AIMediationJob:
        existing = await self.get_by_message_id(message_id)
        if existing is not None:
            return existing
        return await self.add(
            AIMediationJob(
                message_id=message_id,
                status=MediationJobStatus.QUEUED,
                available_at=available_at or datetime.now(UTC),
            )
        )

    async def get_by_message_id(self, message_id: UUID) -> AIMediationJob | None:
        return await self.session.scalar(
            select(AIMediationJob).where(AIMediationJob.message_id == message_id)
        )

    async def get_by_message_id_for_update(
        self, message_id: UUID
    ) -> AIMediationJob | None:
        statement = (
            select(AIMediationJob)
            .where(AIMediationJob.message_id == message_id)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def reactivate_for_message(
        self, message_id: UUID, *, available_at: datetime | None = None
    ) -> AIMediationJob:
        job = await self.get_by_message_id_for_update(message_id)
        if job is None:
            return await self.ensure_job_for_message(
                message_id, available_at=available_at
            )
        self._set_queued(job, available_at=available_at or datetime.now(UTC))
        await self.session.flush()
        return job

    async def claim_next_available_job(
        self,
        *,
        now: datetime,
        lease_duration: timedelta,
        lease_token: UUID | None = None,
    ) -> AIMediationJob | None:
        statement = (
            select(AIMediationJob)
            .where(
                AIMediationJob.status == MediationJobStatus.QUEUED,
                AIMediationJob.available_at <= now,
            )
            .order_by(AIMediationJob.available_at, AIMediationJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = await self.session.scalar(statement)
        if job is None:
            return None
        job.status = MediationJobStatus.LEASED
        job.lease_token = lease_token or uuid4()
        job.lease_expires_at = now + lease_duration
        job.attempt_count += 1
        job.updated_at = now
        job.completed_at = None
        await self.session.flush()
        return job

    async def list_expired_leases_for_update(
        self, *, now: datetime, limit: int = 100
    ) -> list[AIMediationJob]:
        statement = (
            select(AIMediationJob)
            .where(
                AIMediationJob.status == MediationJobStatus.LEASED,
                AIMediationJob.lease_expires_at <= now,
            )
            .order_by(AIMediationJob.lease_expires_at, AIMediationJob.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await self.session.scalars(statement)).all())

    async def mark_completed(
        self, job: AIMediationJob, *, lease_token: UUID, now: datetime
    ) -> bool:
        if not self._has_current_lease(job, lease_token, now):
            return False
        self._set_terminal(job, MediationJobStatus.COMPLETED, now=now)
        await self.session.flush()
        return True

    async def mark_cancelled(
        self,
        job: AIMediationJob,
        *,
        now: datetime,
        error_category: str | None = None,
    ) -> AIMediationJob:
        self._set_terminal(job, MediationJobStatus.CANCELLED, now=now)
        job.last_error_category = error_category
        await self.session.flush()
        return job

    async def mark_dead(
        self,
        job: AIMediationJob,
        *,
        lease_token: UUID,
        now: datetime,
        error_category: str,
    ) -> bool:
        if not self._has_current_lease(job, lease_token, now):
            return False
        self._set_terminal(job, MediationJobStatus.DEAD, now=now)
        job.last_error_category = error_category
        await self.session.flush()
        return True

    async def release_for_retry(
        self,
        job: AIMediationJob,
        *,
        available_at: datetime,
        error_category: str | None = None,
    ) -> AIMediationJob:
        self._set_queued(job, available_at=available_at)
        job.last_error_category = error_category
        await self.session.flush()
        return job

    async def renew_lease(
        self,
        job: AIMediationJob,
        *,
        lease_token: UUID,
        now: datetime,
        lease_duration: timedelta,
    ) -> bool:
        if not self._has_current_lease(job, lease_token, now):
            return False
        job.lease_expires_at = now + lease_duration
        job.updated_at = now
        await self.session.flush()
        return True

    @staticmethod
    def lease_is_current(
        job: AIMediationJob, *, lease_token: UUID, now: datetime
    ) -> bool:
        return AIMediationJobRepository._has_current_lease(job, lease_token, now)

    @staticmethod
    def _has_current_lease(
        job: AIMediationJob, lease_token: UUID, now: datetime
    ) -> bool:
        return bool(
            job.status is MediationJobStatus.LEASED
            and job.lease_token == lease_token
            and job.lease_expires_at is not None
            and job.lease_expires_at > now
        )

    @staticmethod
    def _set_queued(job: AIMediationJob, *, available_at: datetime) -> None:
        job.status = MediationJobStatus.QUEUED
        job.available_at = available_at
        job.lease_token = None
        job.lease_expires_at = None
        job.completed_at = None
        job.updated_at = available_at

    @staticmethod
    def _set_terminal(
        job: AIMediationJob, status: MediationJobStatus, *, now: datetime
    ) -> None:
        job.status = status
        job.lease_token = None
        job.lease_expires_at = None
        job.completed_at = now
        job.updated_at = now
