"""Project-specific exception types for SlideLineage."""


class SlideLineageError(Exception):
    """Base exception for SlideLineage errors."""


class ConfigurationError(SlideLineageError):
    """Raised when user configuration cannot be validated or selected."""


class UnknownPolicyProfileError(ConfigurationError):
    """Raised when a requested SplitPolicy profile is not registered."""
