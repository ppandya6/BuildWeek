"""Typed domain and serialization contracts for Slide-of-Life milestone one."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from slidelineage.config import AuditConfig
from slidelineage.policy import DEFAULT_POLICY_PROFILE, SplitPolicy

MetricValue: TypeAlias = int | float | str | bool | None
PartitionCount: TypeAlias = dict["Partition", int]
LabelCount: TypeAlias = dict[str, int]


class Partition(StrEnum):
    train = "train"
    test = "test"


class AuditStatus(StrEnum):
    passed = "passed"
    policy_violations = "policy_violations"
    failed = "failed"


class PolicyOutcome(StrEnum):
    violation = "violation"
    allowed_overlap = "allowed_overlap"
    review_item = "review_item"
    not_applicable = "not_applicable"


class ConfirmationLevel(StrEnum):
    confirmed = "confirmed"
    probable = "probable"
    warning = "warning"
    ambiguous = "ambiguous"
    conflict = "conflict"


class SchemaMappingSource(StrEnum):
    explicit_user_mapping = "explicit_user_mapping"
    accepted_validated_ai_mapping = "accepted_validated_ai_mapping"
    deterministic_mapping = "deterministic_mapping"
    validated_ai_mapping = "validated_ai_mapping"
    unresolved = "unresolved"


class IdentifierDerivationMethod(StrEnum):
    direct_manifest_value = "direct_manifest_value"
    tcga_derived = "tcga_derived"
    unavailable = "unavailable"


class IdentifierStatus(StrEnum):
    accepted = "accepted"
    conflicted = "conflicted"
    unresolved = "unresolved"


class ImageReadStatus(StrEnum):
    resolved = "resolved"
    missing = "missing"
    outside_root = "outside_root"
    unreadable = "unreadable"
    unsafe_image = "unsafe_image"
    unsupported_format = "unsupported_format"


class RecordIdMethod(StrEnum):
    source_column = "source_column"
    canonical_row_fingerprint = "canonical_row_fingerprint"
    canonical_row_fingerprint_with_collision_suffix = (
        "canonical_row_fingerprint_with_collision_suffix"
    )


class FindingType(StrEnum):
    confirmed_patient_overlap = "confirmed_patient_overlap"
    confirmed_specimen_overlap = "confirmed_specimen_overlap"
    confirmed_slide_overlap = "confirmed_slide_overlap"
    confirmed_byte_content_duplicate = "confirmed_byte_content_duplicate"
    confirmed_pixel_content_duplicate = "confirmed_pixel_content_duplicate"
    image_similarity_candidate = "image_similarity_candidate"
    institution_overlap = "institution_overlap"
    ambiguous_schema_mapping = "ambiguous_schema_mapping"
    missing_required_semantic_field = "missing_required_semantic_field"
    cross_manifest_schema_mismatch = "cross_manifest_schema_mismatch"
    conflicting_lineage_metadata = "conflicting_lineage_metadata"
    image_read_error = "image_read_error"
    resource_limit_exceeded = "resource_limit_exceeded"
    repair_tradeoff = "repair_tradeoff"


class ContractModel(BaseModel):
    """Base model for immutable persisted contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceManifest(ContractModel):
    """Manifest provenance summary with lowercase hexadecimal SHA-256."""

    manifest_id: str
    path: Path
    assigned_partition: Partition
    sha256: str = Field(description="Lowercase 64-character hexadecimal SHA-256.")
    row_count: int = Field(ge=0)
    columns: tuple[str, ...]

    @field_validator("manifest_id")
    @classmethod
    def _nonblank_manifest_id(cls, value: str) -> str:
        return _nonblank(value, "manifest_id")

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("sha256 must be lowercase 64-character hexadecimal text")
        return value

    @field_validator("columns")
    @classmethod
    def _validate_columns(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for column in value:
            _nonblank(column, "columns")
        return value


class RawManifestRow(ContractModel):
    """One decoded CSV data row before semantic schema mapping."""

    source_manifest_id: str
    source_row_number: int = Field(ge=0)
    assigned_partition: Partition
    raw_values: dict[str, str | None]
    normalized_header_values: dict[str, str | None]

    @field_validator("source_manifest_id")
    @classmethod
    def _manifest_id_nonblank(cls, value: str) -> str:
        return _nonblank(value, "source_manifest_id")

    @field_validator("raw_values", "normalized_header_values")
    @classmethod
    def _mapping_keys_nonblank(
        cls, value: dict[str, str | None]
    ) -> dict[str, str | None]:
        for key in value:
            _nonblank(key, "manifest row mapping key")
        return value


class LoadedManifest(ContractModel):
    """Loaded CSV manifest with source-byte and row-level provenance."""

    source: SourceManifest
    original_headers: tuple[str, ...]
    normalized_headers: tuple[str, ...]
    rows: tuple[RawManifestRow, ...]
    encoding_used: str
    newline_style: str | None
    warnings: tuple[str, ...] = ()

    @field_validator("original_headers", "normalized_headers")
    @classmethod
    def _headers_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for header in value:
            _nonblank(header, "loaded manifest header")
        return value

    @field_validator("encoding_used")
    @classmethod
    def _encoding_nonblank(cls, value: str) -> str:
        return _nonblank(value, "encoding_used")

    @field_validator("warnings")
    @classmethod
    def _loaded_warnings_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for warning in value:
            _nonblank(warning, "loaded manifest warning")
        return value

    @model_validator(mode="after")
    def _validate_loaded_manifest(self) -> "LoadedManifest":
        if len(self.original_headers) != len(self.normalized_headers):
            raise ValueError("original and normalized header counts must match")
        if len(self.rows) != self.source.row_count:
            raise ValueError("source row_count must agree with loaded rows")
        for row in self.rows:
            if row.source_manifest_id != self.source.manifest_id:
                raise ValueError("row source_manifest_id must agree with manifest")
            if row.assigned_partition is not self.source.assigned_partition:
                raise ValueError("row assigned_partition must agree with manifest")
        return self


class LoadedManifestPair(ContractModel):
    """Typed container for train and test loaded manifests."""

    train: LoadedManifest
    test: LoadedManifest

    @model_validator(mode="after")
    def _validate_pair(self) -> "LoadedManifestPair":
        if self.train.source.assigned_partition is not Partition.train:
            raise ValueError("train manifest must be assigned to train")
        if self.test.source.assigned_partition is not Partition.test:
            raise ValueError("test manifest must be assigned to test")
        if self.train.source.manifest_id == self.test.source.manifest_id:
            raise ValueError("manifest IDs must differ")
        try:
            if self.train.source.path.samefile(self.test.source.path):
                raise ValueError("train and test manifest files must be distinct")
        except OSError:
            if self.train.source.path.resolve() == self.test.source.path.resolve():
                raise ValueError(
                    "train and test manifest files must be distinct"
                ) from None
        return self


class TcgaLineage(ContractModel):
    """Contract for TCGA lineage fields; parsing is intentionally out of scope."""

    raw_identifier: str
    project: str | None = None
    tissue_source_site: str | None = None
    participant: str | None = None
    sample: str | None = None
    vial: str | None = None
    portion: str | None = None
    analyte: str | None = None
    plate: str | None = None
    center: str | None = None
    derived_patient_id: str | None = None
    derived_specimen_id: str | None = None
    parser_version: str

    @field_validator("raw_identifier", "parser_version")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "tcga required field")

    @field_validator(
        "project",
        "tissue_source_site",
        "participant",
        "sample",
        "vial",
        "portion",
        "analyte",
        "plate",
        "center",
        "derived_patient_id",
        "derived_specimen_id",
        mode="before",
    )
    @classmethod
    def _blank_optional_to_none(cls, value: object) -> object:
        return _blank_to_none(value)


class CanonicalRecord(ContractModel):
    """Canonical record contract using zero-based source row numbers."""

    record_id: str
    record_id_method: RecordIdMethod
    source_manifest_id: str
    source_row_number: int = Field(
        ge=0, description="Zero-based source data row number."
    )
    assigned_partition: Partition
    source_record_id: str | None = None
    image_path: str | None = None
    patient_id: str | None = None
    specimen_id: str | None = None
    slide_id: str | None = None
    institution_id: str | None = None
    label: str | None = None
    tcga: TcgaLineage | None = None
    raw_values_digest: str
    normalized_values_digest: str

    @field_validator(
        "record_id",
        "source_manifest_id",
        "raw_values_digest",
        "normalized_values_digest",
    )
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "canonical record required field")

    @field_validator(
        "source_record_id",
        "image_path",
        "patient_id",
        "specimen_id",
        "slide_id",
        "institution_id",
        "label",
        mode="before",
    )
    @classmethod
    def _blank_optional_to_none(cls, value: object) -> object:
        return _blank_to_none(value)


class IdentifierProvenance(ContractModel):
    """Provenance for one direct or derived semantic identifier value."""

    semantic_field: str
    value: str | None = None
    source_column: str | None = None
    derivation_method: IdentifierDerivationMethod
    parser_version: str | None = None
    confidence: float = Field(ge=0, le=1)
    status: IdentifierStatus

    @field_validator("semantic_field")
    @classmethod
    def _semantic_nonblank(cls, value: str) -> str:
        return _nonblank(value, "semantic_field")

    @field_validator("value", "source_column", "parser_version", mode="before")
    @classmethod
    def _optional_blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def _status_value_consistency(self) -> "IdentifierProvenance":
        if self.status is IdentifierStatus.accepted and self.value is None:
            raise ValueError("accepted identifier provenance requires value")
        if self.status is IdentifierStatus.unresolved and self.confidence != 0:
            raise ValueError(
                "unresolved identifier provenance requires zero confidence"
            )
        return self


class LineageConflict(ContractModel):
    """Direct-versus-derived lineage disagreement for researcher review."""

    conflict_id: str
    record_id: str
    semantic_field: str
    direct_value: str
    derived_value: str
    direct_source_column: str | None
    parser_version: str
    message: str

    @field_validator(
        "conflict_id",
        "record_id",
        "semantic_field",
        "direct_value",
        "derived_value",
        "parser_version",
        "message",
    )
    @classmethod
    def _required_nonblank(cls, value: str) -> str:
        return _nonblank(value, "lineage conflict required field")

    @field_validator("direct_source_column", mode="before")
    @classmethod
    def _source_blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def _values_must_differ(self) -> "LineageConflict":
        if self.direct_value.casefold() == self.derived_value.casefold():
            raise ValueError("lineage conflict values must differ")
        forbidden = {"diagnosis", "prognosis", "treatment", "clinical"}
        if any(term in self.message.casefold() for term in forbidden):
            raise ValueError("lineage conflict message must avoid clinical language")
        return self


class CanonicalManifestRecords(ContractModel):
    """Canonical records and lineage metadata for one manifest."""

    source_manifest_id: str
    partition: Partition
    records: tuple[CanonicalRecord, ...]
    identifier_provenance: tuple[IdentifierProvenance, ...] = ()
    conflicts: tuple[LineageConflict, ...] = ()
    warnings: tuple[str, ...] = ()

    @field_validator("source_manifest_id")
    @classmethod
    def _manifest_nonblank(cls, value: str) -> str:
        return _nonblank(value, "source_manifest_id")

    @field_validator("warnings")
    @classmethod
    def _warnings_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for warning in value:
            _nonblank(warning, "canonical record warning")
        return value

    @model_validator(mode="after")
    def _records_match_manifest(self) -> "CanonicalManifestRecords":
        for record in self.records:
            if record.source_manifest_id != self.source_manifest_id:
                raise ValueError("record source_manifest_id must match collection")
            if record.assigned_partition is not self.partition:
                raise ValueError("record partition must match collection")
        return self


class CanonicalRecordPair(ContractModel):
    """Canonical train/test record collections."""

    train: CanonicalManifestRecords
    test: CanonicalManifestRecords

    @model_validator(mode="after")
    def _validate_pair(self) -> "CanonicalRecordPair":
        if self.train.partition is not Partition.train:
            raise ValueError("train records must have train partition")
        if self.test.partition is not Partition.test:
            raise ValueError("test records must have test partition")
        if self.train.source_manifest_id == self.test.source_manifest_id:
            raise ValueError("canonical manifest IDs must differ")
        return self


class SchemaFieldMapping(ContractModel):
    semantic_field: str
    source_column: str | None
    source: SchemaMappingSource
    confidence: float | None = Field(default=None, ge=0, le=1)
    alternatives: tuple[str, ...] = ()
    validation_messages: tuple[str, ...] = ()

    @field_validator("semantic_field")
    @classmethod
    def _semantic_nonblank(cls, value: str) -> str:
        return _nonblank(value, "semantic_field")

    @field_validator("source_column", mode="before")
    @classmethod
    def _source_column_blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("alternatives", "validation_messages")
    @classmethod
    def _tuple_strings_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _nonblank(item, "mapping tuple field")
        return value

    @model_validator(mode="after")
    def _resolved_mapping_has_column(self) -> "SchemaFieldMapping":
        if (
            self.source is not SchemaMappingSource.unresolved
            and self.source_column is None
        ):
            raise ValueError("resolved mappings require source_column")
        return self


class SchemaMapping(ContractModel):
    image_path: SchemaFieldMapping
    patient_id: SchemaFieldMapping
    specimen_id: SchemaFieldMapping
    slide_id: SchemaFieldMapping
    institution_id: SchemaFieldMapping
    class_label: SchemaFieldMapping
    partition: SchemaFieldMapping
    source_record_id: SchemaFieldMapping
    unresolved_fields: tuple[str, ...] = ()

    @field_validator("unresolved_fields")
    @classmethod
    def _unresolved_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for field in value:
            _nonblank(field, "unresolved_fields")
        return value

    @model_validator(mode="after")
    def _semantic_fields_match_attributes(self) -> "SchemaMapping":
        for attribute in _SCHEMA_MAPPING_ATTRIBUTES:
            mapping = getattr(self, attribute)
            if mapping.semantic_field != attribute:
                raise ValueError(
                    f"mapping {attribute!r} must have semantic_field {attribute!r}"
                )
        return self


AiRationaleCode = Literal[
    "header_alias",
    "cross_manifest_header_alignment",
    "value_pattern_support",
    "insufficient_evidence",
    "ambiguous_candidates",
]


class AiColumnSummary(ContractModel):
    original_header: str
    normalized_header: str
    nonblank_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)
    approximate_cardinality_ratio: float = Field(ge=0, le=1)
    example_categories: tuple[str, ...] = ()
    value_pattern_flags: tuple[str, ...] = ()


class AiManifestSchemaSummary(ContractModel):
    manifest_id: str
    assigned_partition: Partition
    columns: tuple[AiColumnSummary, ...]
    row_count: int = Field(ge=0)
    unresolved_semantic_fields: tuple[str, ...]
    deterministic_mapping_summary: dict[str, str]


class AiSchemaRequest(ContractModel):
    request_schema_version: Literal["1.0"] = "1.0"
    supported_semantic_fields: tuple[str, ...]
    train_summary: AiManifestSchemaSummary
    test_summary: AiManifestSchemaSummary
    instructions_digest: str
    privacy_notice: str
    model: str


class AiProposedFieldMapping(ContractModel):
    semantic_field: str
    train_source_column: str | None = None
    test_source_column: str | None = None
    confidence: float = Field(ge=0, le=1)
    rationale_code: AiRationaleCode
    requires_review: bool = True


class AiSchemaProposal(ContractModel):
    proposal_id: str
    model: str
    response_id: str | None = None
    request_digest: str
    proposed_fields: tuple[AiProposedFieldMapping, ...]
    model_output_digest: str
    generated_at: datetime
    provider: str = "openai"


class AiFieldValidation(ContractModel):
    semantic_field: str
    accepted: bool
    train_source_column: str | None = None
    test_source_column: str | None = None
    confidence: float
    validation_codes: tuple[str, ...]
    validation_messages: tuple[str, ...]


class ValidatedAiSchemaProposal(ContractModel):
    proposal: AiSchemaProposal
    field_validations: tuple[AiFieldValidation, ...]
    accepted_fields: tuple[str, ...]
    rejected_fields: tuple[str, ...]
    fully_valid: bool
    applied: bool = False
    acceptance_requested: bool = False


class AiUsageRecord(ContractModel):
    enabled: bool = False
    proposal_requested: bool = False
    proposal_received: bool = False
    proposal_validated: bool = False
    acceptance_requested: bool = False
    accepted_field_count: int = 0
    rejected_field_count: int = 0
    model: str | None = None
    provider: str | None = None
    request_digest: str | None = None
    proposal_id: str | None = None
    response_id: str | None = None
    privacy_summary: str
    warnings: tuple[str, ...] = ()
    validated_proposal: ValidatedAiSchemaProposal | None = None


class EvidenceRecord(ContractModel):
    record_id: str
    source_manifest_id: str
    source_manifest_path: str
    source_row_number: int = Field(ge=0)
    assigned_partition: Partition
    matched_field: str | None = None
    matched_value: str | None = None
    image_path: str | None = None
    byte_sha256: str | None = None
    canonical_pixel_sha256: str | None = None
    phash: str | None = None
    dhash: str | None = None

    @field_validator("record_id", "source_manifest_id", "source_manifest_path")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "evidence required field")

    @field_validator(
        "matched_field",
        "matched_value",
        "image_path",
        "byte_sha256",
        "canonical_pixel_sha256",
        "phash",
        "dhash",
        mode="before",
    )
    @classmethod
    def _blank_optional_to_none(cls, value: object) -> object:
        return _blank_to_none(value)


class FindingBase(ContractModel):
    finding_id: str
    finding_type: FindingType
    confirmation_level: ConfirmationLevel
    partitions_involved: tuple[Partition, ...]
    record_ids: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]
    metrics: dict[str, MetricValue] = Field(default_factory=dict)
    detector_name: str
    detector_version: str
    parser_version: str | None = None
    created_at: datetime

    single_record_finding_types: ClassVar[frozenset[FindingType]] = frozenset(
        {
            FindingType.ambiguous_schema_mapping,
            FindingType.missing_required_semantic_field,
            FindingType.cross_manifest_schema_mismatch,
            FindingType.conflicting_lineage_metadata,
            FindingType.image_read_error,
            FindingType.resource_limit_exceeded,
            FindingType.repair_tradeoff,
        }
    )

    @field_validator("finding_id", "detector_name", "detector_version")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "finding required field")

    @field_validator("parser_version", mode="before")
    @classmethod
    def _parser_blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("partitions_involved")
    @classmethod
    def _unique_partitions(cls, value: tuple[Partition, ...]) -> tuple[Partition, ...]:
        if len(set(value)) != len(value):
            raise ValueError("partitions_involved must be unique")
        return value

    @field_validator("record_ids")
    @classmethod
    def _unique_record_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for record_id in value:
            _nonblank(record_id, "record_ids")
        if len(set(value)) != len(value):
            raise ValueError("record_ids must be unique")
        return value

    @field_validator("created_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _record_count_matches_finding_type(self) -> "FindingBase":
        if (
            self.finding_type not in self.single_record_finding_types
            and len(self.record_ids) < 2
        ):
            raise ValueError(
                "cross-record factual findings require at least two records"
            )
        if not self.partitions_involved:
            raise ValueError("partitions_involved cannot be empty")
        return self


class FactualFinding(FindingBase):
    """Detector-stage factual relationship without a policy outcome."""


class EvaluatedFinding(FindingBase):
    """Policy-evaluated finding with an explicit policy outcome and reason."""

    policy_outcome: PolicyOutcome
    policy_rule: str = "unspecified_policy_rule"
    policy_reason: str
    policy_profile: str = DEFAULT_POLICY_PROFILE
    repair_eligible: bool = False

    @field_validator("policy_reason", "policy_rule", "policy_profile")
    @classmethod
    def _policy_text_nonblank(cls, value: str) -> str:
        return _nonblank(value, "policy evaluation text")


class GraphNode(ContractModel):
    record_id: str
    partition: Partition
    label: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_nonblank(cls, value: str) -> str:
        return _nonblank(value, "record_id")

    @field_validator("label", mode="before")
    @classmethod
    def _label_blank_to_none(cls, value: object) -> object:
        return _blank_to_none(value)


class GraphEdge(ContractModel):
    source_record_id: str
    target_record_id: str
    finding_id: str
    relationship_type: FindingType
    confirmation_level: ConfirmationLevel
    policy_outcome: PolicyOutcome | None = None

    @field_validator("source_record_id", "target_record_id", "finding_id")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "graph edge required field")

    @model_validator(mode="after")
    def _reject_self_edge(self) -> "GraphEdge":
        if self.source_record_id == self.target_record_id:
            raise ValueError("self-edges are rejected by default")
        return self


class RelationshipGraph(ContractModel):
    """Serialization contract; callers supply deterministic node and edge order."""

    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()

    @field_validator("nodes")
    @classmethod
    def _unique_nodes(cls, value: tuple[GraphNode, ...]) -> tuple[GraphNode, ...]:
        record_ids = [node.record_id for node in value]
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("graph node record IDs must be unique")
        return value


class RepairComponent(ContractModel):
    component_id: str
    record_ids: tuple[str, ...]
    confirming_finding_ids: tuple[str, ...]
    original_partition_counts: PartitionCount = Field(default_factory=dict)
    label_counts: LabelCount = Field(default_factory=dict)
    proposed_partition: Partition | None = None
    conflict_status: str | None = None

    @field_validator("component_id")
    @classmethod
    def _component_nonblank(cls, value: str) -> str:
        return _nonblank(value, "component_id")

    @field_validator("record_ids", "confirming_finding_ids")
    @classmethod
    def _tuple_nonblank_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _nonblank(item, "repair tuple field")
        if len(set(value)) != len(value):
            raise ValueError("repair tuple fields must be unique")
        return value


class RepairDecision(ContractModel):
    component_id: str
    proposed_partition: Partition
    moved_record_ids: tuple[str, ...]
    reason: str
    ratio_deviation: float = Field(ge=0)
    label_distribution_deviation: float = Field(ge=0)
    deterministic_tie_break_explanation: str

    @field_validator("component_id", "reason", "deterministic_tie_break_explanation")
    @classmethod
    def _required_nonblank(cls, value: str) -> str:
        return _nonblank(value, "repair decision required field")

    @field_validator("moved_record_ids")
    @classmethod
    def _moved_nonblank_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _nonblank(item, "moved_record_ids")
        if len(set(value)) != len(value):
            raise ValueError("moved_record_ids must be unique")
        return value


class RepairProposal(ContractModel):
    generated: bool = False
    requires_researcher_review: bool = True
    statement: str = (
        "This repair output is a proposed partition requiring researcher review."
    )
    policy_profile: str = DEFAULT_POLICY_PROFILE
    included_relationship_types: tuple[FindingType, ...] = ()
    excluded_relationship_types: tuple[FindingType, ...] = ()
    components: tuple[RepairComponent, ...] = ()
    decisions: tuple[RepairDecision, ...] = ()
    unresolved_conflicts: tuple[str, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    metrics: dict[str, MetricValue] = Field(default_factory=dict)

    @field_validator("statement", "policy_profile")
    @classmethod
    def _required_nonblank(cls, value: str) -> str:
        return _nonblank(value, "repair proposal required field")

    @field_validator("unresolved_conflicts", "tradeoffs")
    @classmethod
    def _tuple_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _nonblank(item, "repair proposal tuple field")
        return value

    @model_validator(mode="after")
    def _requires_review_language(self) -> "RepairProposal":
        if not self.requires_researcher_review:
            raise ValueError("repair proposals must require researcher review")
        if "researcher review" not in self.statement:
            raise ValueError("repair proposal statement must mention researcher review")
        return self


class ToolMetadata(ContractModel):
    name: str = "Slide-of-Life"
    version: str

    @field_validator("name", "version")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "tool metadata required field")


class RunMetadata(ContractModel):
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    command: tuple[str, ...] = ()

    @field_validator("run_id")
    @classmethod
    def _run_id_nonblank(cls, value: str) -> str:
        return _nonblank(value, "run_id")

    @field_validator("started_at", "completed_at")
    @classmethod
    def _aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("run timestamps must be timezone-aware")
        return value


class InputSummary(ContractModel):
    manifests: tuple[SourceManifest, ...] = ()
    image_root: Path | None = None
    total_records: int = Field(default=0, ge=0)
    train_records: int = Field(default=0, ge=0)
    test_records: int = Field(default=0, ge=0)


class FindingSummary(ContractModel):
    factual_finding_count: int = Field(default=0, ge=0)
    evaluated_finding_count: int = Field(default=0, ge=0)
    review_item_count: int = Field(default=0, ge=0)
    violation_count: int = Field(default=0, ge=0)
    metrics: dict[str, MetricValue] = Field(default_factory=dict)


class PolicyEvaluationSummary(ContractModel):
    policy_profile: str = DEFAULT_POLICY_PROFILE
    violations: int = Field(default=0, ge=0)
    allowed_overlaps: int = Field(default=0, ge=0)
    review_items: int = Field(default=0, ge=0)
    not_applicable: int = Field(default=0, ge=0)

    @field_validator("policy_profile")
    @classmethod
    def _policy_nonblank(cls, value: str) -> str:
        return _nonblank(value, "policy_profile")


class PolicyEvaluationResult(PolicyEvaluationSummary):
    evaluated_findings: tuple[EvaluatedFinding, ...] = ()
    repair_eligible_finding_ids: tuple[str, ...] = ()
    exit_code: int = 0
    reasons: tuple[str, ...] = ()

    @field_validator("repair_eligible_finding_ids", "reasons")
    @classmethod
    def _result_tuple_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _nonblank(item, "policy result tuple field")
        return value

    @model_validator(mode="after")
    def _validate_counts(self) -> "PolicyEvaluationResult":
        counts = {outcome: 0 for outcome in PolicyOutcome}
        for finding in self.evaluated_findings:
            counts[finding.policy_outcome] += 1
        if (
            self.violations != counts[PolicyOutcome.violation]
            or self.allowed_overlaps != counts[PolicyOutcome.allowed_overlap]
            or self.review_items != counts[PolicyOutcome.review_item]
            or self.not_applicable != counts[PolicyOutcome.not_applicable]
        ):
            raise ValueError("policy result counts must match evaluated findings")
        expected_exit = 2 if self.violations else 0
        if self.exit_code != expected_exit:
            raise ValueError(
                "policy result exit code must be 0 or 2 based on violations"
            )
        return self


class ReproducibilityMetadata(ContractModel):
    config_digest: str
    python_version: str
    slidelineage_version: str | None = None
    dependency_versions: dict[str, str] = Field(default_factory=dict)
    manifest_sha256: dict[str, str] = Field(default_factory=dict)
    parser_versions: tuple[str, ...] = ()
    detector_versions: tuple[str, ...] = ()
    image_thresholds: dict[str, int] = Field(default_factory=dict)
    policy_profile: str | None = None
    report_schema_version: str = "1.0.0"

    @field_validator("config_digest", "python_version")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "reproducibility required field")


class ImageFingerprint(ContractModel):
    record_id: str
    assigned_partition: Partition
    source_manifest_id: str
    source_row_number: int = Field(ge=0)
    source_image_path: str
    resolved_path: str | None = None
    status: ImageReadStatus
    byte_sha256: str | None = None
    canonical_pixel_sha256: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    image_format: str | None = None
    phash: str | None = None
    dhash: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    detector_version: str

    @field_validator(
        "record_id", "source_manifest_id", "source_image_path", "detector_version"
    )
    @classmethod
    def _image_required_nonblank(cls, value: str) -> str:
        return _nonblank(value, "image fingerprint required field")

    @field_validator("byte_sha256", "canonical_pixel_sha256")
    @classmethod
    def _optional_sha256(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError(
                "image SHA-256 fields must be lowercase 64-character hexadecimal text"
            )
        return value

    @field_validator("phash", "dhash")
    @classmethod
    def _optional_hash64(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) != 16 or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError(
                "perceptual hashes must be fixed-width lowercase "
                "64-bit hexadecimal text"
            )
        return value

    @model_validator(mode="after")
    def _status_consistency(self) -> "ImageFingerprint":
        if self.status is ImageReadStatus.resolved:
            required = (
                self.resolved_path,
                self.byte_sha256,
                self.canonical_pixel_sha256,
                self.width,
                self.height,
                self.image_format,
                self.phash,
                self.dhash,
            )
            if any(v is None for v in required):
                raise ValueError(
                    "resolved image fingerprints require hashes, dimensions, "
                    "format, and resolved path"
                )
            if self.error_code is not None or self.error_message is not None:
                raise ValueError(
                    "resolved image fingerprints cannot carry error fields"
                )
        elif any(
            v is not None
            for v in (
                self.byte_sha256,
                self.canonical_pixel_sha256,
                self.width,
                self.height,
                self.image_format,
                self.phash,
                self.dhash,
            )
        ):
            raise ValueError(
                "failed image fingerprints must not include successful "
                "fingerprint fields"
            )
        return self


class ImageFingerprintCollection(ContractModel):
    fingerprints: tuple[ImageFingerprint, ...] = ()
    resolved_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    unreadable_count: int = Field(ge=0)
    unsafe_count: int = Field(ge=0)
    pair_count_considered: int = Field(ge=0)
    pair_limit_exceeded: bool = False
    warnings: tuple[str, ...] = ()

    @field_validator("warnings")
    @classmethod
    def _image_warnings_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for warning in value:
            _nonblank(warning, "image fingerprint warning")
        return value


class FactualDetectionResult(ContractModel):
    identifier_findings: tuple[FactualFinding, ...] = ()
    image_findings: tuple[FactualFinding, ...] = ()
    input_quality_findings: tuple[FactualFinding, ...] = ()
    all_findings: tuple[FactualFinding, ...] = ()
    image_fingerprints: ImageFingerprintCollection
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _all_findings_match_components(self) -> "FactualDetectionResult":
        expected = (
            self.identifier_findings + self.image_findings + self.input_quality_findings
        )
        if self.all_findings != expected:
            raise ValueError(
                "all_findings must concatenate identifier, image, "
                "and input-quality findings"
            )
        return self


class AuditArtifactPaths(ContractModel):
    output_dir: Path
    report_json: Path
    report_html: Path
    findings_csv: Path
    repair_proposal_csv: Path | None = None


class AuditRunResult(ContractModel):
    report: "AuditReport"
    artifacts: AuditArtifactPaths | None = None
    exit_code: int = Field(ge=0)
    terminal_summary: str
    warnings: tuple[str, ...] = ()


class AuditReport(ContractModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    tool: ToolMetadata
    run: RunMetadata
    inputs: InputSummary
    configuration: AuditConfig
    policy: SplitPolicy
    schema_mapping: SchemaMapping | None = None
    schema_mappings: dict[str, object] | None = None
    ai_schema_assistance: AiUsageRecord = AiUsageRecord(
        privacy_summary="AI disabled; no data sent to an AI provider."
    )
    status: AuditStatus = AuditStatus.passed
    summary: FindingSummary
    canonical_records: tuple[CanonicalRecord, ...] = ()
    factual_findings: tuple[FactualFinding, ...] = ()
    evaluated_findings: tuple[EvaluatedFinding, ...] = ()
    relationship_graph: RelationshipGraph
    policy_evaluation: PolicyEvaluationSummary
    repair_proposal: RepairProposal | None = None
    reproducibility: ReproducibilityMetadata
    warnings: tuple[str, ...] = ()

    @field_validator("warnings")
    @classmethod
    def _warnings_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for warning in value:
            _nonblank(warning, "warnings")
        return value


_SCHEMA_MAPPING_ATTRIBUTES = (
    "image_path",
    "patient_id",
    "specimen_id",
    "slide_id",
    "institution_id",
    "class_label",
    "partition",
    "source_record_id",
)


def _nonblank(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")
    return value


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value
