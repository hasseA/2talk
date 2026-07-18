"""Business-rule failures raised by the transactional service layer."""


class ServiceError(Exception):
    """Base class for expected service-layer failures."""


class ConversationNotFoundError(ServiceError):
    """The requested conversation does not exist."""


class ConversationFullError(ServiceError):
    """The conversation already has the maximum number of participants."""


class ConversationEndedError(ServiceError):
    """The requested operation is not allowed for an ended conversation."""


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


class SummaryNotFoundError(ServiceError):
    """The requested conversation summary does not exist."""
