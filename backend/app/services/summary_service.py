"""Summary lifecycle interface without summary generation or AI calls."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationSummary
from app.repositories import ConversationRepository, ConversationSummaryRepository
from app.services.exceptions import ConversationNotFoundError, SummaryNotFoundError


class SummaryService:
    """Persist summary lifecycle state for a future AI implementation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_processing(self, conversation_id: UUID) -> ConversationSummary:
        async with self.session.begin():
            conversations = ConversationRepository(self.session)
            summaries = ConversationSummaryRepository(self.session)
            if await conversations.get_by_id(conversation_id) is None:
                raise ConversationNotFoundError
            summary = await summaries.create_processing(conversation_id)
        return summary

    async def mark_completed(
        self,
        summary_id: UUID,
        *,
        main_topics: list[Any],
        agreements: list[Any],
        unresolved_issues: list[Any],
        boundaries: list[Any],
        next_steps: list[Any],
        notice: str | None = None,
    ) -> ConversationSummary:
        async with self.session.begin():
            repository = ConversationSummaryRepository(self.session)
            summary = await repository.get_by_id(summary_id)
            if summary is None:
                raise SummaryNotFoundError
            await repository.mark_completed(
                summary,
                main_topics=main_topics,
                agreements=agreements,
                unresolved_issues=unresolved_issues,
                boundaries=boundaries,
                next_steps=next_steps,
                notice=notice,
            )
        return summary

    async def mark_failed(
        self, summary_id: UUID, *, failure_code: str
    ) -> ConversationSummary:
        async with self.session.begin():
            repository = ConversationSummaryRepository(self.session)
            summary = await repository.get_by_id(summary_id)
            if summary is None:
                raise SummaryNotFoundError
            await repository.mark_failed(summary, failure_code=failure_code)
        return summary
