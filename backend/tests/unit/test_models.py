"""Fast metadata and mapper tests that do not require a database."""

from sqlalchemy.orm import configure_mappers

from app.database.base import Base
from app.models import (
    AIMediationJob,
    AIProcessingAttempt,
    Conversation,
    ConversationSummary,
    Invitation,
    Message,
    MessageDelivery,
    Participant,
    ParticipantSession,
    PrivateGuidance,
    SafetyEvent,
)

EXPECTED_TABLES = {
    "ai_mediation_jobs",
    "ai_processing_attempts",
    "conversation_summaries",
    "conversations",
    "invitations",
    "message_deliveries",
    "messages",
    "participant_sessions",
    "participants",
    "private_guidance",
    "safety_events",
}


def test_all_models_can_be_imported_and_mapped() -> None:
    configure_mappers()
    assert all(
        model.__table__.name in EXPECTED_TABLES
        for model in (
            AIMediationJob,
            AIProcessingAttempt,
            Conversation,
            ConversationSummary,
            Invitation,
            Message,
            MessageDelivery,
            Participant,
            ParticipantSession,
            PrivateGuidance,
            SafetyEvent,
        )
    )


def test_metadata_contains_all_expected_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_token_tables_never_define_raw_token_columns() -> None:
    assert set(Invitation.__table__.columns.keys()) == {
        "id",
        "conversation_id",
        "token_hash",
        "created_at",
        "expires_at",
        "used_at",
        "revoked_at",
    }
    assert set(ParticipantSession.__table__.columns.keys()) == {
        "id",
        "participant_id",
        "token_hash",
        "created_at",
        "expires_at",
        "revoked_at",
        "last_used_at",
    }
