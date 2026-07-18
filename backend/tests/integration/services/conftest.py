"""Shared transactional service fixtures."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services import (
    ConversationService,
    CreatedConversation,
    InvitationService,
    JoinedConversation,
)


@pytest.fixture
def service_settings(test_database_url: str) -> Settings:
    return Settings(
        app_env="test",
        database_url=test_database_url,
        openai_api_key="not-used",
        session_token_secret="session-service-test-secret",
        invitation_token_secret="invitation-service-test-secret",
    )


@dataclass(slots=True)
class ActiveConversation:
    created: CreatedConversation
    joined: JoinedConversation


@pytest_asyncio.fixture
async def active_conversation(
    db_session: AsyncSession, service_settings: Settings
) -> ActiveConversation:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        title="Active conversation",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    joined = await InvitationService(db_session, service_settings).redeem_invitation(
        invitation_token=created.invitation_token,
        display_name="Invitee",
        preferred_language="en",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    return ActiveConversation(created, joined)
