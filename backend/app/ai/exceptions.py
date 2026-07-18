"""Provider-independent AI error hierarchy."""


class AIError(Exception):
    """Base class for mediation-provider failures."""


class AIConfigurationError(AIError):
    """Required AI configuration or prompt content is unavailable."""


class AIProviderError(AIError):
    """The configured AI provider failed to produce a response."""


class AITimeoutError(AIProviderError):
    """The configured AI provider exceeded its request deadline."""


class AIOutputValidationError(AIError):
    """Provider output did not satisfy the mediation contract."""
