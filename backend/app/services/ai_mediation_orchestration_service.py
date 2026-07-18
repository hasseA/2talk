"""Three-phase, retry-safe orchestration for one mediated message."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIOutputValidationError,
    AIProviderError,
    AITimeoutError,
)
from app.ai.models import (
    ConversationContextMessage,
    MediationRequest,
    MediationResult,
    MediationStatus,
    PrivateGuidanceResult,
)
from app.ai.provider import AIProvider
from app.models import (
    AIProcessingAttempt,
    ConversationStatus,
    GuidanceAudience,
    GuidanceType,
    Message,
    MessageStatus,
    Participant,
    ProcessingAttemptStatus,
)
from app.repositories import (
    AIMediationJobRepository,
    AIProcessingAttemptRepository,
    ConversationRepository,
    MessageDeliveryRepository,
    MessageRepository,
    ParticipantRepository,
    PrivateGuidanceRepository,
)
from app.services.exceptions import (
    ConversationNotActiveError,
    MessageNotFoundError,
    MessageStateError,
    ParticipantNotFoundError,
)

MAX_CONTEXT_MESSAGES = 50


class MediationOutcomeStatus(StrEnum):
    """Provider-independent result of an orchestration request."""

    DELIVERED = "delivered"
    BLOCKED = "blocked"
    FAILED = "failed"
    ALREADY_FINALIZED = "already_finalized"
    ALREADY_PROCESSING = "already_processing"
    STALE_ATTEMPT = "stale_attempt"


@dataclass(frozen=True, slots=True)
class MediationOutcome:
    """Safe internal orchestration result with no message content."""

    message_id: UUID
    status: MediationOutcomeStatus
    message_status: MessageStatus
    attempt_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class _ClaimedMediation:
    message_id: UUID
    attempt_id: UUID
    recipient_id: UUID
    request: MediationRequest
    execution_lease_token: UUID | None


class AIMediationOrchestrationService:
    """Claim, call the provider without a transaction, and finalize atomically."""

    def __init__(
        self,
        session: AsyncSession,
        provider: AIProvider,
        *,
        provider_name: str,
        model: str,
        execution_lease_token: UUID | None = None,
    ) -> None:
        if not provider_name.strip() or not model.strip():
            raise ValueError("provider_name and model must not be blank")
        self.session = session
        self.provider = provider
        self.provider_name = provider_name
        self.model = model
        self.execution_lease_token = execution_lease_token

    async def process_message(self, message_id: UUID) -> MediationOutcome:
        """Process one eligible message through the three transaction phases."""
        claim = await self._claim_and_prepare(message_id)
        if isinstance(claim, MediationOutcome):
            return claim

        # Deliberately outside session.begin(): external latency must hold no DB lock.
        try:
            result = await self.provider.mediate_message(claim.request)
        except AIError as exc:
            return await self._finalize_failure(claim, exc)

        if result.status is MediationStatus.DELIVERED:
            return await self._finalize_delivered(claim, result)
        return await self._finalize_blocked(claim, result)

    async def _claim_and_prepare(
        self, message_id: UUID
    ) -> _ClaimedMediation | MediationOutcome:
        async with self.session.begin():
            lease_is_current = await self._lock_execution_lease(message_id)
            messages = MessageRepository(self.session)
            attempts = AIProcessingAttemptRepository(self.session)
            conversations = ConversationRepository(self.session)
            participants = ParticipantRepository(self.session)

            message = await messages.get_by_id_for_update(message_id)
            if message is None:
                raise MessageNotFoundError
            if not lease_is_current:
                return self._outcome(message, MediationOutcomeStatus.STALE_ATTEMPT)
            if message.status in (MessageStatus.DELIVERED, MessageStatus.BLOCKED):
                return self._outcome(message, MediationOutcomeStatus.ALREADY_FINALIZED)
            if message.status is not MessageStatus.PROCESSING:
                raise MessageStateError

            conversation = await conversations.get_by_id(message.conversation_id)
            if conversation is None:
                raise MessageNotFoundError
            if conversation.status is not ConversationStatus.ACTIVE:
                raise ConversationNotActiveError

            sender, recipient = await self._load_participants(participants, message)
            latest = await attempts.get_latest_for_message(message.id)
            if latest is not None and latest.status is ProcessingAttemptStatus.STARTED:
                return self._outcome(
                    message,
                    MediationOutcomeStatus.ALREADY_PROCESSING,
                    attempt_id=latest.id,
                )

            expected_attempt_number = (
                latest.attempt_number + 1 if latest is not None else 1
            )
            attempt = await attempts.create_attempt(
                message_id=message.id,
                attempt_number=expected_attempt_number,
                provider=self.provider_name,
                model=self.model,
                execution_lease_token=self.execution_lease_token,
            )
            context = await messages.list_mediated_context(
                conversation_id=message.conversation_id,
                perspective_sender_id=message.sender_id,
                before_created_at=message.created_at,
                before_message_id=message.id,
                limit=MAX_CONTEXT_MESSAGES,
            )
            request = MediationRequest(
                original_message=message.original_message,
                sender_language=sender.preferred_language,
                recipient_language=recipient.preferred_language,
                conversation_context=tuple(
                    ConversationContextMessage(
                        speaker=item.speaker,
                        mediated_message=item.mediated_message,
                        language=item.language,
                    )
                    for item in context
                ),
            )
            return _ClaimedMediation(
                message_id=message.id,
                attempt_id=attempt.id,
                recipient_id=recipient.id,
                request=request,
                execution_lease_token=self.execution_lease_token,
            )

    async def _finalize_delivered(
        self, claim: _ClaimedMediation, result: MediationResult
    ) -> MediationOutcome:
        assert result.mediated_message is not None
        assert result.delivered_language is not None
        async with self.session.begin():
            if not await self._lock_execution_lease(claim.message_id):
                return await self._stale_lease_outcome(claim.message_id)
            current = await self._lock_current_attempt(claim)
            if isinstance(current, MediationOutcome):
                return current
            message, attempt = current

            participants = ParticipantRepository(self.session)
            _, recipient = await self._load_participants(participants, message)
            if recipient.id != claim.recipient_id:
                raise ParticipantNotFoundError

            deliveries = MessageDeliveryRepository(self.session)
            if (
                await deliveries.get_for_message_and_recipient(message.id, recipient.id)
                is not None
            ):
                raise MessageStateError

            messages = MessageRepository(self.session)
            await messages.mark_delivered(
                message,
                mediated_message=result.mediated_message,
                delivered_language=result.delivered_language,
                communication_goal=result.communication_goal,
                detected_emotion=result.emotion,
                requires_pause=result.requires_pause,
            )
            await deliveries.create(
                message_id=message.id,
                recipient_id=recipient.id,
                delivered_at=message.delivered_at,
            )
            guidance = PrivateGuidanceRepository(self.session)
            await self._create_guidance(
                guidance,
                message=message,
                participant_id=message.sender_id,
                audience=GuidanceAudience.SENDER,
                item=result.sender_guidance,
            )
            await self._create_guidance(
                guidance,
                message=message,
                participant_id=recipient.id,
                audience=GuidanceAudience.RECIPIENT,
                item=result.recipient_guidance,
            )
            await AIProcessingAttemptRepository(self.session).mark_completed(attempt)
            return self._outcome(
                message,
                MediationOutcomeStatus.DELIVERED,
                attempt_id=attempt.id,
            )

    async def _finalize_blocked(
        self, claim: _ClaimedMediation, result: MediationResult
    ) -> MediationOutcome:
        async with self.session.begin():
            if not await self._lock_execution_lease(claim.message_id):
                return await self._stale_lease_outcome(claim.message_id)
            current = await self._lock_current_attempt(claim)
            if isinstance(current, MediationOutcome):
                return current
            message, attempt = current

            messages = MessageRepository(self.session)
            await messages.mark_blocked(message, failure_code="AI_BLOCKED")
            await self._create_guidance(
                PrivateGuidanceRepository(self.session),
                message=message,
                participant_id=message.sender_id,
                audience=GuidanceAudience.SENDER,
                item=result.sender_guidance,
            )
            await AIProcessingAttemptRepository(self.session).mark_rejected(
                attempt,
                error_code="AI_BLOCKED",
                error_message=result.blocking_reason,
            )
            return self._outcome(
                message,
                MediationOutcomeStatus.BLOCKED,
                attempt_id=attempt.id,
            )

    async def _finalize_failure(
        self, claim: _ClaimedMediation, error: AIError
    ) -> MediationOutcome:
        failure_code = self._failure_code(error)
        async with self.session.begin():
            if not await self._lock_execution_lease(claim.message_id):
                return await self._stale_lease_outcome(claim.message_id)
            current = await self._lock_current_attempt(claim)
            if isinstance(current, MediationOutcome):
                return current
            message, attempt = current
            await AIProcessingAttemptRepository(self.session).mark_failed(
                attempt,
                error_code=failure_code,
                error_message=None,
            )
            await MessageRepository(self.session).mark_failed(
                message, failure_code=failure_code
            )
            return self._outcome(
                message,
                MediationOutcomeStatus.FAILED,
                attempt_id=attempt.id,
            )

    async def _lock_execution_lease(self, message_id: UUID) -> bool:
        if self.execution_lease_token is None:
            return True
        repository = AIMediationJobRepository(self.session)
        job = await repository.get_by_message_id_for_update(message_id)
        return bool(
            job is not None
            and repository.lease_is_current(
                job,
                lease_token=self.execution_lease_token,
                now=datetime.now(UTC),
            )
        )

    async def _stale_lease_outcome(self, message_id: UUID) -> MediationOutcome:
        message = await MessageRepository(self.session).get_by_id_for_update(message_id)
        if message is None:
            raise MessageNotFoundError
        return self._outcome(message, MediationOutcomeStatus.STALE_ATTEMPT)

    async def _lock_current_attempt(
        self, claim: _ClaimedMediation
    ) -> tuple[Message, AIProcessingAttempt] | MediationOutcome:
        messages = MessageRepository(self.session)
        attempts = AIProcessingAttemptRepository(self.session)
        message = await messages.get_by_id_for_update(claim.message_id)
        if message is None:
            raise MessageNotFoundError
        attempt = await attempts.get_by_id_for_update(claim.attempt_id)
        latest = await attempts.get_latest_for_message_for_update(message.id)
        attempt_is_current = not (
            attempt is None
            or attempt.message_id != message.id
            or attempt.status is not ProcessingAttemptStatus.STARTED
            or latest is None
            or latest.id != attempt.id
        )
        if not attempt_is_current:
            if (
                attempt is not None
                and attempt.status is ProcessingAttemptStatus.STARTED
            ):
                await attempts.mark_rejected(
                    attempt,
                    error_code="STALE_ATTEMPT",
                    error_message=None,
                )
            if message.status is not MessageStatus.PROCESSING:
                return self._outcome(message, MediationOutcomeStatus.ALREADY_FINALIZED)
            return self._outcome(
                message,
                MediationOutcomeStatus.STALE_ATTEMPT,
                attempt_id=claim.attempt_id,
            )
        if message.status is not MessageStatus.PROCESSING:
            return self._outcome(message, MediationOutcomeStatus.ALREADY_FINALIZED)
        assert attempt is not None
        return message, attempt

    @staticmethod
    async def _load_participants(
        repository: ParticipantRepository, message: Message
    ) -> tuple[Participant, Participant]:
        participants = await repository.list_by_conversation(message.conversation_id)
        if len(participants) != 2:
            raise ParticipantNotFoundError
        sender = next(
            (item for item in participants if item.id == message.sender_id), None
        )
        recipient = next(
            (item for item in participants if item.id != message.sender_id), None
        )
        if sender is None or recipient is None:
            raise ParticipantNotFoundError
        return sender, recipient

    @staticmethod
    async def _create_guidance(
        repository: PrivateGuidanceRepository,
        *,
        message: Message,
        participant_id: UUID,
        audience: GuidanceAudience,
        item: PrivateGuidanceResult | None,
    ) -> None:
        if item is None:
            return
        await repository.create(
            conversation_id=message.conversation_id,
            message_id=message.id,
            participant_id=participant_id,
            audience=audience,
            guidance_type=GuidanceType(item.type.value),
            guidance_text=item.text,
        )

    @staticmethod
    def _failure_code(error: AIError) -> str:
        if isinstance(error, AITimeoutError):
            return "AI_TIMEOUT"
        if isinstance(error, AIOutputValidationError):
            return "AI_RESPONSE_INVALID"
        if isinstance(error, AIConfigurationError):
            return "AI_CONFIGURATION_ERROR"
        if isinstance(error, AIProviderError):
            return "AI_PROVIDER_ERROR"
        return "AI_PROCESSING_FAILED"

    @staticmethod
    def _outcome(
        message: Message,
        status: MediationOutcomeStatus,
        *,
        attempt_id: UUID | None = None,
    ) -> MediationOutcome:
        return MediationOutcome(
            message_id=message.id,
            status=status,
            message_status=message.status,
            attempt_id=attempt_id,
        )


def create_ai_mediation_orchestration_service(
    session: AsyncSession,
    provider: AIProvider,
    *,
    provider_name: str,
    model: str,
    execution_lease_token: UUID | None = None,
) -> AIMediationOrchestrationService:
    """Construct orchestration behind provider-independent dependencies."""
    return AIMediationOrchestrationService(
        session,
        provider,
        provider_name=provider_name,
        model=model,
        execution_lease_token=execution_lease_token,
    )
