"""Summary, safety audit, and transaction-boundary repository tests."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SummaryStatus
from app.repositories import (
    ConversationRepository,
    ConversationSummaryRepository,
    SafetyEventRepository,
)
from tests.integration.repositories.conftest import RepositoryGraph


@pytest.mark.asyncio
async def test_summary_can_be_created_and_completed(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = ConversationSummaryRepository(db_session)
    summary = await repository.create_processing(repository_graph.conversation.id)

    await repository.mark_completed(
        summary,
        main_topics=["Topic"],
        agreements=["Agreement"],
        unresolved_issues=[],
        boundaries=["Boundary"],
        next_steps=["Next step"],
    )

    assert summary.status is SummaryStatus.COMPLETED
    assert summary.main_topics == ["Topic"]
    assert summary.completed_at is not None
    assert (
        await repository.get_by_conversation(repository_graph.conversation.id)
        is summary
    )


@pytest.mark.asyncio
async def test_safety_event_query_contains_only_audit_classification(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = SafetyEventRepository(db_session)
    event = await repository.create(
        conversation_id=repository_graph.conversation.id,
        participant_id=repository_graph.creator.id,
        category="policy",
        severity="low",
        action_taken="recorded",
    )

    assert await repository.list_by_conversation(repository_graph.conversation.id) == [
        event
    ]
    assert not hasattr(event, "original_message")


@pytest.mark.asyncio
async def test_repository_method_does_not_commit(db_session: AsyncSession) -> None:
    repository = ConversationRepository(db_session)
    commit = AsyncMock()

    with patch.object(db_session, "commit", commit):
        conversation = await repository.create(title="No implicit commit")
        retrieved = await repository.get_by_id(conversation.id)

    assert retrieved is conversation
    commit.assert_not_awaited()
