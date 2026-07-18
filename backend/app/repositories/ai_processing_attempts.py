"""AI processing-attempt persistence without AI behavior."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models import AIProcessingAttempt, ProcessingAttemptStatus
from app.repositories.base import BaseRepository


class AIProcessingAttemptRepository(BaseRepository[AIProcessingAttempt]):
    model = AIProcessingAttempt

    async def create_attempt(
        self,
        *,
        message_id: UUID,
        attempt_number: int,
        provider: str,
        model: str,
        execution_lease_token: UUID | None = None,
    ) -> AIProcessingAttempt:
        return await self.add(
            AIProcessingAttempt(
                message_id=message_id,
                attempt_number=attempt_number,
                provider=provider,
                model=model,
                status=ProcessingAttemptStatus.STARTED,
                execution_lease_token=execution_lease_token,
            )
        )

    async def get_latest_for_message(
        self, message_id: UUID
    ) -> AIProcessingAttempt | None:
        statement = (
            select(AIProcessingAttempt)
            .where(AIProcessingAttempt.message_id == message_id)
            .order_by(AIProcessingAttempt.attempt_number.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def get_by_id_for_update(
        self, attempt_id: UUID
    ) -> AIProcessingAttempt | None:
        statement = (
            select(AIProcessingAttempt)
            .where(AIProcessingAttempt.id == attempt_id)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def get_latest_for_message_for_update(
        self, message_id: UUID
    ) -> AIProcessingAttempt | None:
        statement = (
            select(AIProcessingAttempt)
            .where(AIProcessingAttempt.message_id == message_id)
            .order_by(AIProcessingAttempt.attempt_number.desc())
            .limit(1)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def list_by_message(self, message_id: UUID) -> list[AIProcessingAttempt]:
        statement = (
            select(AIProcessingAttempt)
            .where(AIProcessingAttempt.message_id == message_id)
            .order_by(AIProcessingAttempt.attempt_number)
        )
        return list((await self.session.scalars(statement)).all())

    async def mark_completed(
        self,
        attempt: AIProcessingAttempt,
        *,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        completed_at: datetime | None = None,
    ) -> AIProcessingAttempt:
        attempt.status = ProcessingAttemptStatus.COMPLETED
        attempt.prompt_tokens = prompt_tokens
        attempt.completion_tokens = completion_tokens
        attempt.total_tokens = total_tokens
        attempt.request_completed_at = completed_at or datetime.now(UTC)
        attempt.error_code = None
        attempt.error_message = None
        await self.session.flush()
        return attempt

    async def mark_failed(
        self,
        attempt: AIProcessingAttempt,
        *,
        error_code: str,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> AIProcessingAttempt:
        return await self._mark_unsuccessful(
            attempt,
            status=ProcessingAttemptStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            completed_at=completed_at,
        )

    async def mark_rejected(
        self,
        attempt: AIProcessingAttempt,
        *,
        error_code: str,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> AIProcessingAttempt:
        return await self._mark_unsuccessful(
            attempt,
            status=ProcessingAttemptStatus.REJECTED,
            error_code=error_code,
            error_message=error_message,
            completed_at=completed_at,
        )

    async def _mark_unsuccessful(
        self,
        attempt: AIProcessingAttempt,
        *,
        status: ProcessingAttemptStatus,
        error_code: str,
        error_message: str | None,
        completed_at: datetime | None,
    ) -> AIProcessingAttempt:
        attempt.status = status
        attempt.error_code = error_code
        attempt.error_message = error_message
        attempt.request_completed_at = completed_at or datetime.now(UTC)
        await self.session.flush()
        return attempt
