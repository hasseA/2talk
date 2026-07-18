"""Create the complete MVP database foundation.

Revision ID: 20260718_0001
Revises:
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the MVP tables, constraints, and indexes."""
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default="waiting", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('waiting', 'active', 'ended')",
            name="conversations_status_check",
        ),
        sa.CheckConstraint(
            "activated_at IS NULL OR status IN ('active', 'ended')",
            name="conversations_activated_state_check",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR status = 'ended'",
            name="conversations_ended_state_check",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
    )
    op.create_index("conversations_status_idx", "conversations", ["status"])

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="invitations_conversation_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invitations"),
        sa.UniqueConstraint("token_hash", name="invitations_token_hash_unique"),
    )
    op.create_index(
        "invitations_conversation_id_idx", "invitations", ["conversation_id"]
    )
    op.create_index("invitations_expires_at_idx", "invitations", ["expires_at"])

    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("preferred_language", sa.String(length=20), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('creator', 'invitee')", name="participants_role_check"
        ),
        sa.CheckConstraint(
            "LENGTH(TRIM(display_name)) > 0",
            name="participants_display_name_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="participants_conversation_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_participants"),
        sa.UniqueConstraint(
            "conversation_id",
            "role",
            name="participants_unique_role_per_conversation",
        ),
    )
    op.create_index(
        "participants_conversation_id_idx", "participants", ["conversation_id"]
    )

    op.create_table(
        "participant_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="participant_sessions_participant_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_participant_sessions"),
        sa.UniqueConstraint(
            "token_hash", name="participant_sessions_token_hash_unique"
        ),
    )
    op.create_index(
        "participant_sessions_participant_id_idx",
        "participant_sessions",
        ["participant_id"],
    )
    op.create_index(
        "participant_sessions_expires_at_idx", "participant_sessions", ["expires_at"]
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_message_id", sa.String(length=100), nullable=False),
        sa.Column("original_message", sa.Text(), nullable=False),
        sa.Column("original_language", sa.String(length=20), nullable=True),
        sa.Column("mediated_message", sa.Text(), nullable=True),
        sa.Column("delivered_language", sa.String(length=20), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default="processing", nullable=False
        ),
        sa.Column("communication_goal", sa.String(length=100), nullable=True),
        sa.Column("detected_emotion", sa.String(length=100), nullable=True),
        sa.Column(
            "requires_pause",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column(
            "retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("mediated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'delivered', 'failed', 'blocked')",
            name="messages_status_check",
        ),
        sa.CheckConstraint(
            "LENGTH(TRIM(original_message)) > 0",
            name="messages_original_not_empty",
        ),
        sa.CheckConstraint("retry_count >= 0", name="messages_retry_count_nonnegative"),
        sa.CheckConstraint(
            "status <> 'delivered' OR "
            "(mediated_message IS NOT NULL AND delivered_at IS NOT NULL)",
            name="messages_delivery_content_check",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="messages_conversation_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["participants.id"],
            name="messages_sender_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint(
            "conversation_id",
            "sender_id",
            "client_message_id",
            name="messages_client_id_unique",
        ),
    )
    op.create_index(
        "messages_conversation_created_idx",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("messages_sender_id_idx", "messages", ["sender_id"])
    op.create_index("messages_status_idx", "messages", ["status"])

    op.create_table(
        "message_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="message_deliveries_message_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["participants.id"],
            name="message_deliveries_recipient_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_message_deliveries"),
        sa.UniqueConstraint(
            "message_id", "recipient_id", name="message_deliveries_unique"
        ),
    )
    op.create_index(
        "message_deliveries_recipient_idx",
        "message_deliveries",
        ["recipient_id", "delivered_at"],
    )

    op.create_table(
        "ai_processing_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "request_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("request_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'rejected')",
            name="ai_processing_attempts_status_check",
        ),
        sa.CheckConstraint(
            "attempt_number > 0", name="ai_processing_attempts_number_positive"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="ai_processing_attempts_message_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_processing_attempts"),
        sa.UniqueConstraint(
            "message_id", "attempt_number", name="ai_processing_attempts_unique"
        ),
    )
    op.create_index(
        "ai_processing_attempts_message_id_idx",
        "ai_processing_attempts",
        ["message_id"],
    )

    op.create_table(
        "private_guidance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("guidance_type", sa.String(length=40), nullable=False),
        sa.Column("guidance_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "audience IN ('sender', 'recipient')",
            name="private_guidance_audience_check",
        ),
        sa.CheckConstraint(
            "guidance_type IN ('communication_support', 'clarification', "
            "'de_escalation', 'pause_suggestion', 'boundary_notice', 'safety_notice')",
            name="private_guidance_type_check",
        ),
        sa.CheckConstraint(
            "LENGTH(TRIM(guidance_text)) > 0",
            name="private_guidance_text_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="private_guidance_conversation_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="private_guidance_message_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="private_guidance_participant_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_private_guidance"),
    )
    op.create_index(
        "private_guidance_participant_created_idx",
        "private_guidance",
        ["participant_id", "created_at"],
    )
    op.create_index(
        "private_guidance_message_id_idx", "private_guidance", ["message_id"]
    )

    op.create_table(
        "conversation_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="processing", nullable=False
        ),
        sa.Column(
            "main_topics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "agreements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "unresolved_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "boundaries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "next_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("notice", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="conversation_summaries_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="conversation_summaries_conversation_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversation_summaries"),
        sa.UniqueConstraint(
            "conversation_id", name="conversation_summaries_one_per_conversation"
        ),
    )
    op.create_index(
        "conversation_summaries_status_idx", "conversation_summaries", ["status"]
    )

    op.create_table(
        "safety_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("action_taken", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="safety_events_conversation_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="safety_events_message_fk",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="safety_events_participant_fk",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_safety_events"),
    )


def downgrade() -> None:
    """Drop the MVP database foundation in dependency-safe order."""
    op.drop_table("safety_events")
    op.drop_index(
        "conversation_summaries_status_idx", table_name="conversation_summaries"
    )
    op.drop_table("conversation_summaries")
    op.drop_index("private_guidance_message_id_idx", table_name="private_guidance")
    op.drop_index(
        "private_guidance_participant_created_idx", table_name="private_guidance"
    )
    op.drop_table("private_guidance")
    op.drop_index(
        "ai_processing_attempts_message_id_idx", table_name="ai_processing_attempts"
    )
    op.drop_table("ai_processing_attempts")
    op.drop_index("message_deliveries_recipient_idx", table_name="message_deliveries")
    op.drop_table("message_deliveries")
    op.drop_index("messages_status_idx", table_name="messages")
    op.drop_index("messages_sender_id_idx", table_name="messages")
    op.drop_index("messages_conversation_created_idx", table_name="messages")
    op.drop_table("messages")
    op.drop_index(
        "participant_sessions_expires_at_idx", table_name="participant_sessions"
    )
    op.drop_index(
        "participant_sessions_participant_id_idx", table_name="participant_sessions"
    )
    op.drop_table("participant_sessions")
    op.drop_index("participants_conversation_id_idx", table_name="participants")
    op.drop_table("participants")
    op.drop_index("invitations_expires_at_idx", table_name="invitations")
    op.drop_index("invitations_conversation_id_idx", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("conversations_status_idx", table_name="conversations")
    op.drop_table("conversations")
