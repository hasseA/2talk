"""Provider-independent asynchronous mediation interface."""

from typing import Protocol, runtime_checkable

from app.ai.models import MediationRequest, MediationResult


@runtime_checkable
class AIProvider(Protocol):
    """Interface consumed by the future mediation orchestration service."""

    async def mediate_message(self, request: MediationRequest) -> MediationResult:
        """Return a strictly validated mediation result."""
        ...
