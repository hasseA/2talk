"""Structured conversation-summary persistence."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models import ConversationSummary, SummaryStatus
from app.repositories.base import BaseRepository


class ConversationSummaryRepository(BaseRepository[ConversationSummary]):
    model = ConversationSummary

    async def create_processing(self, conversation_id: UUID) -> ConversationSummary:
        return await self.add(
            ConversationSummary(
                conversation_id=conversation_id,
                status=SummaryStatus.PROCESSING,
            )
        )

    async def get_by_conversation(
        self, conversation_id: UUID
    ) -> ConversationSummary | None:
        return await self.session.scalar(
            select(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation_id
            )
        )

    async def mark_completed(
        self,
        summary: ConversationSummary,
        *,
        main_topics: list[Any],
        agreements: list[Any],
        unresolved_issues: list[Any],
        boundaries: list[Any],
        next_steps: list[Any],
        notice: str | None = None,
        completed_at: datetime | None = None,
    ) -> ConversationSummary:
        summary.status = SummaryStatus.COMPLETED
        summary.main_topics = main_topics
        summary.agreements = agreements
        summary.unresolved_issues = unresolved_issues
        summary.boundaries = boundaries
        summary.next_steps = next_steps
        summary.notice = notice
        summary.failure_code = None
        summary.completed_at = completed_at or datetime.now(UTC)
        await self.session.flush()
        return summary

    async def mark_failed(
        self, summary: ConversationSummary, *, failure_code: str
    ) -> ConversationSummary:
        summary.status = SummaryStatus.FAILED
        summary.failure_code = failure_code
        await self.session.flush()
        return summary
