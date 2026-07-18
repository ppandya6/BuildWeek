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


class SchemaMappingError(SlideLineageError):
    """Raised when semantic schema mapping cannot be completed safely."""


class SchemaMapFileError(SchemaMappingError):
    """Raised when an explicit schema-map file cannot be read or parsed."""


class UnsupportedSchemaMapFormatError(SchemaMapFileError):
    """Raised when a schema-map file extension is unsupported."""


class InvalidSchemaMapError(SchemaMapFileError):
    """Raised when a schema-map payload violates its contract."""


class UnknownSchemaFieldError(InvalidSchemaMapError):
    """Raised when a schema map names an unsupported semantic field."""


class MissingMappedColumnError(SchemaMappingError):
    """Raised when a mapped source column is absent or ambiguous."""


class DuplicateSemanticAssignmentError(SchemaMappingError):
    """Raised when one source column is assigned incompatible meanings."""


class InsufficientSchemaCoverageError(SchemaMappingError):
    """Raised when neither image_path nor source_record_id can be mapped."""
