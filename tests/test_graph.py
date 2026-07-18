from datetime import UTC, datetime

import pytest

from slidelineage.errors import GraphReferenceError
from slidelineage.graph import build_relationship_graph
from slidelineage.models import (
    CanonicalManifestRecords,
    CanonicalRecord,
    CanonicalRecordPair,
    ConfirmationLevel,
    EvidenceRecord,
    FactualFinding,
    FindingType,
    Partition,
    RecordIdMethod,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def rec(rid, part, label="a"):
    return CanonicalRecord(
        record_id=rid,
        record_id_method=RecordIdMethod.source_column,
        source_manifest_id=f"{part.value}_m",
        source_row_number=0,
        assigned_partition=part,
        label=label,
        raw_values_digest="a" * 64,
        normalized_values_digest="b" * 64,
    )


def pair():
    return CanonicalRecordPair(
        train=CanonicalManifestRecords(
            source_manifest_id="train_m",
            partition=Partition.train,
            records=(rec("r1", Partition.train), rec("r3", Partition.train)),
        ),
        test=CanonicalManifestRecords(
            source_manifest_id="test_m",
            partition=Partition.test,
            records=(rec("r2", Partition.test), rec("r4", Partition.test)),
        ),
    )


def finding(ftype, ids=("r1", "r2"), level=ConfirmationLevel.confirmed, fid=None):
    ev = tuple(
        EvidenceRecord(
            record_id=i,
            source_manifest_id="m",
            source_manifest_path="x",
            source_row_number=0,
            assigned_partition=Partition.train if i in {"r1", "r3"} else Partition.test,
        )
        for i in ids
    )
    return FactualFinding(
        finding_id=fid or f"f_{ftype.value}_{'_'.join(ids)}",
        finding_type=ftype,
        confirmation_level=level,
        partitions_involved=(Partition.train, Partition.test),
        record_ids=ids,
        evidence=ev,
        detector_name="t",
        detector_version="1",
        created_at=NOW,
    )


def test_nodes_edges_supported_types_grouping_and_determinism():
    p = pair()
    findings = (
        finding(FindingType.confirmed_patient_overlap, ("r1", "r2", "r4"), fid="f1"),
        finding(FindingType.confirmed_specimen_overlap, fid="f2"),
        finding(FindingType.confirmed_slide_overlap, fid="f3"),
        finding(FindingType.confirmed_byte_content_duplicate, fid="f4"),
        finding(FindingType.confirmed_pixel_content_duplicate, fid="f5"),
        finding(
            FindingType.image_similarity_candidate,
            level=ConfirmationLevel.probable,
            fid="f6",
        ),
        finding(
            FindingType.institution_overlap, level=ConfirmationLevel.warning, fid="f7"
        ),
    )
    g = build_relationship_graph(p, tuple(reversed(findings)))
    assert [n.record_id for n in g.nodes] == ["r1", "r2", "r3", "r4"]
    assert any(
        e.relationship_type is FindingType.confirmed_patient_overlap for e in g.edges
    )
    assert sum(e.finding_id == "f1" for e in g.edges) == 3
    assert (
        next(e for e in g.edges if e.finding_id == "f6").confirmation_level
        is ConfirmationLevel.probable
    )
    assert (
        next(e for e in g.edges if e.finding_id == "f7").confirmation_level
        is ConfirmationLevel.warning
    )
    assert g.model_dump(mode="json") == build_relationship_graph(
        p, findings
    ).model_dump(mode="json")


def test_graph_rejects_missing_endpoint_and_excludes_single_record_quality():
    p = pair()
    with pytest.raises(GraphReferenceError):
        build_relationship_graph(
            p, (finding(FindingType.confirmed_patient_overlap, ("r1", "missing")),)
        )
    quality = finding(
        FindingType.image_read_error, ("r1",), level=ConfirmationLevel.warning, fid="q"
    )
    assert build_relationship_graph(p, (quality,)).edges == ()
