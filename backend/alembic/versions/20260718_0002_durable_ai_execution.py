"""Add durable AI mediation jobs and attempt lease ownership.

Revision ID: 20260718_0002
Revises: 20260718_0001
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260718_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the durable queue and associate attempts with worker leases."""
    op.create_table(
        "ai_mediation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="queued", nullable=False
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_error_category", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'leased', 'completed', 'cancelled', 'dead')",
            name="ai_mediation_jobs_status_check",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ai_mediation_jobs_attempt_count_nonnegative"
        ),
        sa.CheckConstraint(
            "(status = 'leased' AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'leased' AND lease_token IS NULL "
            "AND lease_expires_at IS NULL)",
            name="ai_mediation_jobs_lease_state_check",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="ai_mediation_jobs_message_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_mediation_jobs"),
        sa.UniqueConstraint("message_id", name="ai_mediation_jobs_message_unique"),
    )
    op.create_index(
        "ai_mediation_jobs_available_idx",
        "ai_mediation_jobs",
        ["status", "available_at"],
    )
    op.create_index(
        "ai_mediation_jobs_lease_expiry_idx",
        "ai_mediation_jobs",
        ["status", "lease_expires_at"],
    )
    op.add_column(
        "ai_processing_attempts",
        sa.Column(
            "execution_lease_token", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )


def downgrade() -> None:
    """Remove durable execution while preserving the prior foundation."""
    op.drop_column("ai_processing_attempts", "execution_lease_token")
    op.drop_index(
        "ai_mediation_jobs_lease_expiry_idx", table_name="ai_mediation_jobs"
    )
    op.drop_index("ai_mediation_jobs_available_idx", table_name="ai_mediation_jobs")
    op.drop_table("ai_mediation_jobs")
