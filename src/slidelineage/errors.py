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


class AiSchemaError(SlideLineageError):
    """Base error for optional AI schema assistance."""


class AiSdkUnavailableError(AiSchemaError):
    """The optional OpenAI SDK is not installed."""


class AiCredentialError(AiSchemaError):
    """Provider credentials are unavailable or rejected."""


class AiRequestError(AiSchemaError):
    """The provider request failed."""


class AiResponseValidationError(AiSchemaError):
    """The provider response did not match the structured contract."""


class AiProposalValidationError(AiSchemaError):
    """A proposal cannot provide minimum schema coverage."""


class RecordConstructionError(SlideLineageError):
    """Raised when canonical records cannot be constructed safely."""


class MissingSourceRecordIdError(RecordConstructionError):
    """Raised when a mapped source-record ID is missing for a row."""


class DuplicateSourceRecordIdError(RecordConstructionError):
    """Raised when a source-record ID repeats within one manifest."""


class RecordIdCollisionError(RecordConstructionError):
    """Raised when deterministic record ID collision handling fails."""


class SemanticColumnAccessError(RecordConstructionError):
    """Raised when a mapped semantic source column cannot be read."""


class TcgaParseError(SlideLineageError):
    """Raised when TCGA parsing cannot proceed safely."""


class MalformedTcgaIdentifierError(TcgaParseError):
    """Raised when a TCGA-like identifier is malformed."""


class ImageFingerprintError(SlideLineageError):
    """Raised when image fingerprint configuration or processing fails."""


class ImagePathResolutionError(ImageFingerprintError):
    """Raised when image path resolution cannot proceed safely."""


class ImageOutsideRootError(ImagePathResolutionError):
    """Raised when an image path escapes the configured image root."""


class ImageUnreadableError(ImageFingerprintError):
    """Raised when an image cannot be decoded or read."""


class ImageSafetyError(ImageFingerprintError):
    """Raised when image safety limits are exceeded."""


class GraphConstructionError(SlideLineageError):
    """Raised when relationship graph construction receives invalid inputs."""


class GraphReferenceError(GraphConstructionError):
    """Raised when graph edges reference missing records or findings."""


class PolicyEvaluationError(SlideLineageError):
    """Raised when policy evaluation contracts are internally inconsistent."""


class RepairError(SlideLineageError):
    """Raised when deterministic repair proposal construction fails."""


class InvalidTargetFractionError(RepairError):
    """Raised when a repair target train fraction is invalid."""


class RepairAssignmentError(RepairError):
    """Raised when repair components cannot be assigned consistently."""


class AuditExecutionError(SlideLineageError):
    """Raised when deterministic audit orchestration fails."""


class OutputDirectoryError(AuditExecutionError):
    """Raised when an audit output directory is unsafe to use."""


class ArtifactWriteError(AuditExecutionError):
    """Raised when report artifact writing fails."""


class ReportSerializationError(ArtifactWriteError):
    """Raised when report serialization fails validation."""


class ReportTemplateError(ArtifactWriteError):
    """Raised when HTML report rendering fails."""
