"""Behavioral tests for typed Slide-of-Life contracts."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from slidelineage.config import AuditConfig
from slidelineage.models import (
    AuditReport,
    CanonicalRecord,
    ConfirmationLevel,
    EvaluatedFinding,
    EvidenceRecord,
    FactualFinding,
    FindingSummary,
    FindingType,
    GraphEdge,
    GraphNode,
    InputSummary,
    Partition,
    PolicyEvaluationSummary,
    PolicyOutcome,
    RecordIdMethod,
    RelationshipGraph,
    RepairComponent,
    RepairDecision,
    RepairProposal,
    ReproducibilityMetadata,
    RunMetadata,
    SchemaFieldMapping,
    SchemaMapping,
    SchemaMappingSource,
    SourceManifest,
    ToolMetadata,
)
from slidelineage.policy import get_policy_profile

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SHA = "a" * 64


def evidence(
    record_id: str = "r1", partition: Partition = Partition.train
) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=record_id,
        source_manifest_id="manifest-train",
        source_manifest_path="data/train.csv",
        source_row_number=0,
        assigned_partition=partition,
    )


def factual_finding(**overrides: object) -> FactualFinding:
    values: dict[str, object] = {
        "finding_id": "finding-1",
        "finding_type": FindingType.confirmed_patient_overlap,
        "confirmation_level": ConfirmationLevel.confirmed,
        "partitions_involved": (Partition.train, Partition.test),
        "record_ids": ("r1", "r2"),
        "evidence": (evidence("r1", Partition.train), evidence("r2", Partition.test)),
        "detector_name": "contract-test",
        "detector_version": "0.1",
        "created_at": NOW,
    }
    values.update(overrides)
    return FactualFinding(**values)


def evaluated_finding(**overrides: object) -> EvaluatedFinding:
    values: dict[str, object] = factual_finding().model_dump()
    values.update(
        {
            "policy_outcome": PolicyOutcome.violation,
            "policy_reason": "Patient overlap is disallowed by policy.",
        }
    )
    values.update(overrides)
    return EvaluatedFinding(**values)


def field_mapping(
    semantic_field: str,
    source_column: str | None,
    source: SchemaMappingSource,
) -> SchemaFieldMapping:
    return SchemaFieldMapping(
        semantic_field=semantic_field,
        source_column=source_column,
        source=source,
        confidence=None if source is SchemaMappingSource.unresolved else 1.0,
    )


def schema_mapping(**overrides: object) -> SchemaMapping:
    values: dict[str, object] = {
        "image_path": field_mapping(
            "image_path", "image_file", SchemaMappingSource.explicit_user_mapping
        ),
        "patient_id": field_mapping(
            "patient_id", "patient", SchemaMappingSource.deterministic_mapping
        ),
        "specimen_id": field_mapping(
            "specimen_id", None, SchemaMappingSource.unresolved
        ),
        "slide_id": field_mapping(
            "slide_id", "slide", SchemaMappingSource.deterministic_mapping
        ),
        "institution_id": field_mapping(
            "institution_id", None, SchemaMappingSource.unresolved
        ),
        "class_label": field_mapping(
            "class_label", "label", SchemaMappingSource.deterministic_mapping
        ),
        "partition": field_mapping(
            "partition", "split", SchemaMappingSource.explicit_user_mapping
        ),
        "source_record_id": field_mapping(
            "source_record_id", "case_id", SchemaMappingSource.explicit_user_mapping
        ),
        "unresolved_fields": ("specimen_id", "institution_id"),
    }
    values.update(overrides)
    return SchemaMapping(**values)


def test_enum_serialized_values_and_invalid_rejection() -> None:
    assert Partition.train.value == "train"
    assert PolicyOutcome.review_item.value == "review_item"
    assert SchemaMappingSource.accepted_validated_ai_mapping.value == (
        "accepted_validated_ai_mapping"
    )
    assert RecordIdMethod.canonical_row_fingerprint.value == "canonical_row_fingerprint"
    assert FindingType.repair_tradeoff.value == "repair_tradeoff"

    with pytest.raises(ValueError):
        Partition("validation")


def test_source_manifest_validation() -> None:
    manifest = SourceManifest(
        manifest_id="train",
        path="data/train.csv",
        assigned_partition=Partition.train,
        sha256=SHA,
        row_count=0,
        columns=("patient", "slide"),
    )

    assert manifest.columns == ("patient", "slide")
    with pytest.raises(ValidationError):
        SourceManifest(
            manifest_id="train",
            path="data/train.csv",
            assigned_partition=Partition.train,
            sha256="ABC",
            row_count=0,
            columns=("patient",),
        )
    with pytest.raises(ValidationError):
        SourceManifest(
            manifest_id="train",
            path="data/train.csv",
            assigned_partition=Partition.train,
            sha256=SHA,
            row_count=-1,
            columns=("patient",),
        )
    with pytest.raises(ValidationError):
        SourceManifest(
            manifest_id="train",
            path="data/train.csv",
            assigned_partition=Partition.train,
            sha256=SHA,
            row_count=0,
            columns=(" ",),
        )


def test_canonical_record_validation_and_blank_optional_normalization() -> None:
    record = CanonicalRecord(
        record_id="r1",
        record_id_method=RecordIdMethod.source_column,
        source_manifest_id="manifest-train",
        source_row_number=0,
        assigned_partition=Partition.train,
        source_record_id=" ",
        raw_values_digest=SHA,
        normalized_values_digest="b" * 64,
    )

    assert record.source_record_id is None
    with pytest.raises(ValidationError):
        CanonicalRecord(
            record_id=" ",
            record_id_method=RecordIdMethod.source_column,
            source_manifest_id="manifest-train",
            source_row_number=0,
            assigned_partition=Partition.train,
            raw_values_digest=SHA,
            normalized_values_digest="b" * 64,
        )


def test_schema_mapping_mixed_provenance_unresolved_and_validation() -> None:
    mapping = schema_mapping()

    assert mapping.image_path.source is SchemaMappingSource.explicit_user_mapping
    assert mapping.patient_id.source is SchemaMappingSource.deterministic_mapping
    assert mapping.specimen_id.source_column is None
    with pytest.raises(ValidationError):
        SchemaFieldMapping(
            semantic_field="patient_id",
            source_column="patient",
            source=SchemaMappingSource.deterministic_mapping,
            confidence=1.1,
        )
    with pytest.raises(ValidationError, match="semantic_field"):
        schema_mapping(
            patient_id=field_mapping(
                "slide_id", "slide", SchemaMappingSource.deterministic_mapping
            )
        )
    with pytest.raises(ValidationError, match="source_column"):
        SchemaFieldMapping(
            semantic_field="patient_id",
            source_column=None,
            source=SchemaMappingSource.deterministic_mapping,
        )


def test_factual_finding_has_no_policy_result() -> None:
    finding = factual_finding()

    assert not hasattr(finding, "policy_outcome")
    assert finding.record_ids == ("r1", "r2")


def test_evaluated_finding_requires_policy_result() -> None:
    payload = factual_finding().model_dump()

    with pytest.raises(ValidationError):
        EvaluatedFinding(**payload)
    assert evaluated_finding().policy_outcome is PolicyOutcome.violation


def test_finding_validation_rules() -> None:
    with pytest.raises(ValidationError, match="record_ids"):
        factual_finding(record_ids=("r1", "r1"))
    with pytest.raises(ValidationError, match="partitions_involved"):
        factual_finding(partitions_involved=(Partition.train, Partition.train))
    with pytest.raises(ValidationError, match="timezone-aware"):
        factual_finding(created_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError, match="at least two"):
        factual_finding(record_ids=("r1",), evidence=(evidence("r1"),))


def test_single_record_input_quality_finding_allowed() -> None:
    finding = factual_finding(
        finding_type=FindingType.image_read_error,
        confirmation_level=ConfirmationLevel.warning,
        partitions_involved=(Partition.train,),
        record_ids=("r1",),
        evidence=(evidence("r1"),),
    )

    assert finding.finding_type is FindingType.image_read_error


def test_graph_models_validate_nodes_and_edges() -> None:
    graph = RelationshipGraph(
        nodes=(
            GraphNode(record_id="r1", partition=Partition.train),
            GraphNode(record_id="r2", partition=Partition.test),
        ),
        edges=(
            GraphEdge(
                source_record_id="r1",
                target_record_id="r2",
                finding_id="finding-1",
                relationship_type=FindingType.confirmed_patient_overlap,
                confirmation_level=ConfirmationLevel.confirmed,
            ),
        ),
    )

    assert len(graph.edges) == 1
    with pytest.raises(ValidationError, match="unique"):
        RelationshipGraph(
            nodes=(
                GraphNode(record_id="r1", partition=Partition.train),
                GraphNode(record_id="r1", partition=Partition.test),
            )
        )
    with pytest.raises(ValidationError, match="self-edges"):
        GraphEdge(
            source_record_id="r1",
            target_record_id="r1",
            finding_id="finding-1",
            relationship_type=FindingType.confirmed_patient_overlap,
            confirmation_level=ConfirmationLevel.confirmed,
        )


def test_repair_proposal_contracts_and_serialization() -> None:
    component = RepairComponent(
        component_id="component-1",
        record_ids=("r1", "r2"),
        confirming_finding_ids=("finding-1",),
        original_partition_counts={Partition.train: 1, Partition.test: 1},
        label_counts={"tumor": 2},
    )
    decision = RepairDecision(
        component_id="component-1",
        proposed_partition=Partition.train,
        moved_record_ids=("r2",),
        reason="Keep related records together.",
        ratio_deviation=0.1,
        label_distribution_deviation=0.2,
        deterministic_tie_break_explanation="Lexicographic component ID order.",
    )
    proposal = RepairProposal(
        generated=True, components=(component,), decisions=(decision,)
    )

    assert proposal.requires_researcher_review is True
    assert "researcher review" in proposal.model_dump_json()
    assert RepairProposal().components == ()
    with pytest.raises(ValidationError):
        RepairProposal(requires_researcher_review=False)


def test_audit_report_minimal_serialization_and_extra_rejection() -> None:
    config = AuditConfig(
        train_manifest="data/train.csv",
        test_manifest="data/test.csv",
        output_dir="artifacts/audit",
    )
    report = AuditReport(
        tool=ToolMetadata(version="0.1.0"),
        run=RunMetadata(run_id="run-1", started_at=NOW),
        inputs=InputSummary(total_records=0),
        configuration=config,
        policy=get_policy_profile(),
        schema_mapping=schema_mapping(),
        summary=FindingSummary(),
        factual_findings=(factual_finding(),),
        evaluated_findings=(evaluated_finding(),),
        relationship_graph=RelationshipGraph(),
        policy_evaluation=PolicyEvaluationSummary(),
        repair_proposal=RepairProposal(),
        reproducibility=ReproducibilityMetadata(
            config_digest=config.digest(), python_version="3.12.13"
        ),
    )

    serialized = report.model_dump_json()
    assert report.schema_version == "1.0.0"
    assert "factual_findings" in serialized
    assert "evaluated_findings" in serialized
    with pytest.raises(ValidationError):
        AuditReport(
            tool=ToolMetadata(version="0.1.0"),
            run=RunMetadata(run_id="run-1", started_at=NOW),
            inputs=InputSummary(),
            configuration=config,
            policy=get_policy_profile(),
            summary=FindingSummary(),
            relationship_graph=RelationshipGraph(),
            policy_evaluation=PolicyEvaluationSummary(),
            reproducibility=ReproducibilityMetadata(
                config_digest=config.digest(), python_version="3.12.13"
            ),
            unexpected=True,
        )
