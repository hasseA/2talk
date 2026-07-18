"""Business-rule failures raised by the transactional service layer."""


class ServiceError(Exception):
    """Base class for expected service-layer failures."""


class ConversationNotFoundError(ServiceError):
    """The requested conversation does not exist."""


class ConversationFullError(ServiceError):
    """The conversation already has the maximum number of participants."""


class ConversationEndedError(ServiceError):
    """The requested operation is not allowed for an ended conversation."""


class ConversationAlreadyEndedError(ConversationEndedError):
    """An end request targeted a conversation that was already ended."""


class ConversationStateError(ServiceError):
    """The conversation is not in the required state."""


class InvitationNotFoundError(ServiceError):
    """No invitation matches the supplied token."""


class InvitationExpiredError(ServiceError):
    """The invitation has expired."""


class InvitationAlreadyUsedError(ServiceError):
    """The invitation has already been redeemed."""


class InvitationRevokedError(ServiceError):
    """The invitation has been revoked."""


class ParticipantNotFoundError(ServiceError):
    """The requested participant does not exist in the conversation."""


class MessageNotFoundError(ServiceError):
    """The requested message does not exist."""


class DuplicateMessageError(ServiceError):
    """The client message identifier has already been used by this sender."""


class MessageStateError(ServiceError):
    """The requested message transition is not valid from its current state."""


class ConversationNotActiveError(MessageStateError):
    """Messages cannot be created or retried outside an active conversation."""


class MessageNotRetryableError(MessageStateError):
    """Only a failed message owned by the participant may be retried."""


class InvalidCursorError(ServiceError):
    """The supplied pagination cursor is not visible in the requested collection."""


class SummaryNotFoundError(ServiceError):
    """The requested conversation summary does not exist."""
