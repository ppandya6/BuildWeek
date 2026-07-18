"""Typed domain and serialization contracts for SlideLineage milestone one."""

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
    unresolved = "unresolved"


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
    policy_reason: str

    @field_validator("policy_reason")
    @classmethod
    def _policy_reason_nonblank(cls, value: str) -> str:
        return _nonblank(value, "policy_reason")


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
    name: str = "SlideLineage"
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


class FindingSummary(ContractModel):
    factual_finding_count: int = Field(default=0, ge=0)
    evaluated_finding_count: int = Field(default=0, ge=0)
    review_item_count: int = Field(default=0, ge=0)
    violation_count: int = Field(default=0, ge=0)


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


class ReproducibilityMetadata(ContractModel):
    config_digest: str
    python_version: str
    dependency_versions: dict[str, str] = Field(default_factory=dict)

    @field_validator("config_digest", "python_version")
    @classmethod
    def _nonblank_required(cls, value: str) -> str:
        return _nonblank(value, "reproducibility required field")


class AuditReport(ContractModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    tool: ToolMetadata
    run: RunMetadata
    inputs: InputSummary
    configuration: AuditConfig
    policy: SplitPolicy
    schema_mapping: SchemaMapping | None = None
    summary: FindingSummary
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
