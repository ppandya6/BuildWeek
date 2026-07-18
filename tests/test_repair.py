from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from slidelineage.errors import InvalidTargetFractionError
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
from slidelineage.policy import get_policy_profile
from slidelineage.policy_evaluation import evaluate_findings
from slidelineage.repair import build_repair_components, propose_repair

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


def evaluated(*findings):
    return evaluate_findings(tuple(findings), get_policy_profile()).evaluated_findings


def test_components_transitive_duplicates_singletons_and_determinism():
    p = pair()
    fs = evaluated(
        finding(FindingType.confirmed_patient_overlap, ("r1", "r2"), fid="a"),
        finding(FindingType.confirmed_byte_content_duplicate, ("r2", "r3"), fid="b"),
        finding(FindingType.confirmed_pixel_content_duplicate, ("r4", "r3"), fid="c"),
        finding(FindingType.image_similarity_candidate, ("r1", "r4"), fid="s"),
    )
    comps = build_repair_components(p, tuple(reversed(fs)))
    assert len(comps) == 1
    assert comps[0].record_ids == ("r1", "r2", "r3", "r4")
    assert comps == build_repair_components(p, fs)


def test_institution_grouping_option_and_singletons():
    p = pair()
    fs = evaluated(finding(FindingType.institution_overlap, ("r1", "r2"), fid="i"))
    assert sorted(len(c.record_ids) for c in build_repair_components(p, fs)) == [
        1,
        1,
        1,
        1,
    ]
    assert sorted(
        len(c.record_ids)
        for c in build_repair_components(p, fs, group_by_institution=True)
    ) == [1, 1, 2]


def test_proposal_assignment_metrics_tradeoffs_and_validation():
    p = pair()
    fs = evaluated(
        finding(FindingType.confirmed_patient_overlap, ("r1", "r2"), fid="a"),
        finding(FindingType.image_similarity_candidate, ("r3", "r4"), fid="s"),
        finding(FindingType.resource_limit_exceeded, ("r1",), fid="q"),
    )
    with pytest.raises(InvalidTargetFractionError):
        propose_repair(p, fs, get_policy_profile(), target_train_fraction=1)
    proposal = propose_repair(
        p, tuple(reversed(fs)), get_policy_profile(), target_train_fraction=0.5
    )
    assert proposal.generated and proposal.requires_researcher_review
    assert "researcher review" in proposal.statement
    assert FindingType.confirmed_patient_overlap in proposal.included_relationship_types
    assert (
        FindingType.image_similarity_candidate in proposal.excluded_relationship_types
    )
    assigned = sorted(rid for c in proposal.components for rid in c.record_ids)
    assert assigned == ["r1", "r2", "r3", "r4"]
    assert proposal.metrics["component_count"] == 3
    assert proposal.tradeoffs
    assert proposal.model_dump(mode="json") == propose_repair(
        p, fs, get_policy_profile(), target_train_fraction=0.5
    ).model_dump(mode="json")
    with pytest.raises(ValidationError):
        type(proposal)(
            **(proposal.model_dump() | {"requires_researcher_review": False})
        )
