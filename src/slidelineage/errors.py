"""Project-specific exception types for SlideLineage."""


class SlideLineageError(Exception):
    """Base exception for SlideLineage errors."""


class ConfigurationError(SlideLineageError):
    """Raised when user configuration cannot be validated or selected."""


class UnknownPolicyProfileError(ConfigurationError):
    """Raised when a requested SplitPolicy profile is not registered."""


class ManifestError(SlideLineageError):
    """Raised when a manifest cannot be safely ingested."""


class ManifestNotFoundError(ManifestError):
    """Raised when a manifest path does not exist."""


class ManifestUnreadableError(ManifestError):
    """Raised when a manifest path is not a readable regular file."""


class ManifestEncodingError(ManifestError):
    """Raised when a manifest is not supported strict UTF-8 text."""


class ManifestCsvError(ManifestError):
    """Raised when CSV structure is malformed or unsafe."""


class EmptyManifestError(ManifestCsvError):
    """Raised when a manifest lacks required header or data rows."""


class DuplicateHeaderError(ManifestCsvError):
    """Raised when original headers are blank or duplicated exactly."""


class NormalizedHeaderCollisionError(ManifestCsvError):
    """Raised when distinct headers normalize to the same canonical header."""


class SameManifestFileError(ManifestError):
    """Raised when train and test manifest paths identify the same file."""


class NormalizationError(ManifestError):
    """Raised when conservative normalization cannot produce a safe value."""
