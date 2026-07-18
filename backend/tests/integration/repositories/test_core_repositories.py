"""Conversation, invitation, participant, and session repository tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationStatus, ParticipantRole
from app.repositories import (
    ConversationRepository,
    InvitationRepository,
    ParticipantRepository,
    ParticipantSessionRepository,
)
from tests.integration.repositories.conftest import RepositoryGraph


@pytest.mark.asyncio
async def test_conversation_creation_retrieval_and_row_lock(
    db_session: AsyncSession,
) -> None:
    repository = ConversationRepository(db_session)
    conversation = await repository.create(title="Locked conversation")

    retrieved = await repository.get_by_id(conversation.id)
    locked = await repository.get_by_id_for_update(conversation.id)

    assert retrieved is conversation
    assert locked is conversation
    assert conversation.status is ConversationStatus.WAITING


@pytest.mark.asyncio
async def test_conversation_state_updates_are_flushed_without_commit(
    db_session: AsyncSession,
) -> None:
    repository = ConversationRepository(db_session)
    conversation = await repository.create()

    await repository.set_active(conversation)
    assert conversation.status is ConversationStatus.ACTIVE
    assert conversation.activated_at is not None

    await repository.set_ended(conversation)
    assert conversation.status is ConversationStatus.ENDED
    assert conversation.ended_at is not None


@pytest.mark.asyncio
async def test_invitation_lookup_by_hash(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = InvitationRepository(db_session)
    invitation = await repository.create(
        conversation_id=repository_graph.conversation.id,
        token_hash="invitation-hash",
    )

    assert await repository.get_by_token_hash("invitation-hash") is invitation
    assert await repository.get_valid_by_token_hash("invitation-hash") is invitation


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_state", ["expired", "used", "revoked"])
async def test_invalid_invitation_is_excluded_from_valid_lookup(
    db_session: AsyncSession,
    repository_graph: RepositoryGraph,
    invalid_state: str,
) -> None:
    repository = InvitationRepository(db_session)
    now = datetime.now(UTC)
    invitation = await repository.create(
        conversation_id=repository_graph.conversation.id,
        token_hash=f"{invalid_state}-hash",
        expires_at=now + timedelta(hours=1),
    )
    if invalid_state == "expired":
        invitation.expires_at = now - timedelta(seconds=1)
    elif invalid_state == "used":
        await repository.mark_used(invitation, used_at=now)
    else:
        await repository.revoke(invitation, revoked_at=now)
    await db_session.flush()

    assert (
        await repository.get_valid_by_token_hash(invitation.token_hash, now=now) is None
    )


@pytest.mark.asyncio
async def test_participant_count_membership_other_participant_and_language_update(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = ParticipantRepository(db_session)

    assert await repository.count_by_conversation(repository_graph.conversation.id) == 2
    assert await repository.participant_belongs_to_conversation(
        repository_graph.creator.id, repository_graph.conversation.id
    )
    assert (
        await repository.get_by_conversation_and_role(
            repository_graph.conversation.id, ParticipantRole.CREATOR
        )
        is repository_graph.creator
    )
    assert (
        await repository.get_other_participant(
            repository_graph.conversation.id, repository_graph.creator.id
        )
        is repository_graph.invitee
    )

    await repository.update_preferred_language(repository_graph.creator, "fa")
    assert repository_graph.creator.preferred_language == "fa"


@pytest.mark.asyncio
async def test_valid_session_lookup(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = ParticipantSessionRepository(db_session)
    participant_session = await repository.create(
        participant_id=repository_graph.creator.id,
        token_hash="valid-session-hash",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    assert (
        await repository.get_valid_by_token_hash("valid-session-hash")
        is participant_session
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_state", ["expired", "revoked"])
async def test_invalid_session_is_excluded(
    db_session: AsyncSession,
    repository_graph: RepositoryGraph,
    invalid_state: str,
) -> None:
    repository = ParticipantSessionRepository(db_session)
    now = datetime.now(UTC)
    participant_session = await repository.create(
        participant_id=repository_graph.creator.id,
        token_hash=f"{invalid_state}-session-hash",
        expires_at=now + timedelta(hours=1),
    )
    if invalid_state == "expired":
        participant_session.expires_at = now - timedelta(seconds=1)
        await db_session.flush()
    else:
        await repository.revoke(participant_session, revoked_at=now)

    assert (
        await repository.get_valid_by_token_hash(
            participant_session.token_hash, now=now
        )
        is None
    )


@pytest.mark.asyncio
async def test_session_last_used_can_be_updated(
    db_session: AsyncSession, repository_graph: RepositoryGraph
) -> None:
    repository = ParticipantSessionRepository(db_session)
    participant_session = await repository.create(
        participant_id=repository_graph.creator.id,
        token_hash="used-session-hash",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    used_at = datetime.now(UTC)

    await repository.update_last_used(participant_session, last_used_at=used_at)

    assert participant_session.last_used_at == used_at
