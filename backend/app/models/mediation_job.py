"""Durable PostgreSQL queue row for one message mediation job."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import MediationJobStatus, constrained_enum

if TYPE_CHECKING:
    from app.models.message import Message


class AIMediationJob(Base):
    """One reusable durable execution record for a message."""

    __tablename__ = "ai_mediation_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'leased', 'completed', 'cancelled', 'dead')",
            name="ai_mediation_jobs_status_check",
        ),
        CheckConstraint(
            "attempt_count >= 0", name="ai_mediation_jobs_attempt_count_nonnegative"
        ),
        CheckConstraint(
            "(status = 'leased' AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'leased' AND lease_token IS NULL "
            "AND lease_expires_at IS NULL)",
            name="ai_mediation_jobs_lease_state_check",
        ),
        UniqueConstraint("message_id", name="ai_mediation_jobs_message_unique"),
        Index("ai_mediation_jobs_available_idx", "status", "available_at"),
        Index("ai_mediation_jobs_lease_expiry_idx", "status", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "messages.id", ondelete="CASCADE", name="ai_mediation_jobs_message_fk"
        ),
        nullable=False,
    )
    status: Mapped[MediationJobStatus] = mapped_column(
        constrained_enum(MediationJobStatus, name="mediation_job_status", length=20),
        nullable=False,
        default=MediationJobStatus.QUEUED,
        server_default=MediationJobStatus.QUEUED.value,
    )
    available_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error_category: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    message: Mapped["Message"] = relationship(back_populates="mediation_job")
