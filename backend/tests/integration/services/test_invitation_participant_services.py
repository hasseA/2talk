"""Invitation redemption, participant rules, and race-condition tests."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import ConversationStatus, ParticipantRole
from app.repositories import InvitationRepository, ParticipantRepository
from app.services import (
    ConversationFullError,
    ConversationService,
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationRevokedError,
    InvitationService,
    ParticipantService,
    ServiceError,
)


@pytest.mark.asyncio
async def test_validate_and_redeem_invitation_joins_and_activates(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service = InvitationService(db_session, service_settings)

    validation = await service.validate_invitation(created.invitation_token)
    joined = await service.redeem_invitation(
        invitation_token=created.invitation_token,
        display_name="Invitee",
        preferred_language="en",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    assert validation.conversation_id == created.conversation.id
    assert not hasattr(validation, "token_hash")
    assert joined.participant.role is ParticipantRole.INVITEE
    assert joined.conversation.status is ConversationStatus.ACTIVE
    assert created.invitation.used_at is not None


@pytest.mark.asyncio
async def test_room_full_is_rejected(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    async with db_session.begin():
        await ParticipantRepository(db_session).create(
            conversation_id=created.conversation.id,
            display_name="Existing invitee",
            preferred_language="en",
            role=ParticipantRole.INVITEE,
        )

    with pytest.raises(ConversationFullError):
        await InvitationService(db_session, service_settings).redeem_invitation(
            invitation_token=created.invitation_token,
            display_name="Third participant",
            preferred_language="en",
            session_expires_at=datetime.now(UTC) + timedelta(days=1),
        )


@pytest.mark.asyncio
async def test_used_invitation_is_rejected(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service = InvitationService(db_session, service_settings)
    await service.redeem_invitation(
        invitation_token=created.invitation_token,
        display_name="Invitee",
        preferred_language="en",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    with pytest.raises(InvitationAlreadyUsedError):
        await service.redeem_invitation(
            invitation_token=created.invitation_token,
            display_name="Another",
            preferred_language="en",
            session_expires_at=datetime.now(UTC) + timedelta(days=1),
        )


@pytest.mark.asyncio
async def test_expired_invitation_is_rejected(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        invitation_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    with pytest.raises(InvitationExpiredError):
        await InvitationService(db_session, service_settings).validate_invitation(
            created.invitation_token
        )


@pytest.mark.asyncio
async def test_revoked_invitation_is_rejected(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    async with db_session.begin():
        await InvitationRepository(db_session).revoke(created.invitation)

    with pytest.raises(InvitationRevokedError):
        await InvitationService(db_session, service_settings).validate_invitation(
            created.invitation_token
        )


@pytest.mark.asyncio
async def test_concurrent_join_allows_exactly_one_invitee(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
    service_settings: Settings,
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def attempt_join(name: str):
        async with session_factory() as session:
            try:
                return await InvitationService(
                    session, service_settings
                ).redeem_invitation(
                    invitation_token=created.invitation_token,
                    display_name=name,
                    preferred_language="en",
                    session_expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            except ServiceError as error:
                return error

    results = await asyncio.gather(attempt_join("First"), attempt_join("Second"))

    successes = [result for result in results if not isinstance(result, ServiceError)]
    failures = [result for result in results if isinstance(result, ServiceError)]
    assert len(successes) == 1
    assert len(failures) == 1

    async with session_factory() as verification_session:
        count = await ParticipantRepository(verification_session).count_by_conversation(
            created.conversation.id
        )
    assert count == 2


@pytest.mark.asyncio
async def test_update_participant_language_is_conversation_scoped(
    db_session: AsyncSession, service_settings: Settings
) -> None:
    created = await ConversationService(
        db_session, service_settings
    ).create_conversation(
        display_name="Creator",
        preferred_language="sv",
        session_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    updated = await ParticipantService(db_session, service_settings).update_language(
        conversation_id=created.conversation.id,
        participant_id=created.creator.id,
        preferred_language="fa",
    )

    assert updated.preferred_language == "fa"
