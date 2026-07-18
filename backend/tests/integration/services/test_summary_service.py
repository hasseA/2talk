"""Summary service interface tests without generation behavior."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SummaryStatus
from app.services import SummaryService
from tests.integration.services.conftest import ActiveConversation


@pytest.mark.asyncio
async def test_summary_service_persists_lifecycle_only(
    db_session: AsyncSession, active_conversation: ActiveConversation
) -> None:
    service = SummaryService(db_session)
    summary = await service.create_processing(
        active_conversation.created.conversation.id
    )

    completed = await service.mark_completed(
        summary.id,
        main_topics=["Topic"],
        agreements=[],
        unresolved_issues=[],
        boundaries=[],
        next_steps=[],
    )

    assert completed.status is SummaryStatus.COMPLETED
    assert completed.main_topics == ["Topic"]
