from datetime import UTC, datetime

from slidelineage.models import (
    CanonicalManifestRecords,
    CanonicalRecord,
    CanonicalRecordPair,
    ConfirmationLevel,
    EvidenceRecord,
    FactualFinding,
    FindingType,
    Partition,
    PolicyOutcome,
    RecordIdMethod,
)
from slidelineage.policy import SplitPolicy, get_policy_profile
from slidelineage.policy_evaluation import evaluate_findings

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


def test_policy_mapping_counts_preserves_evidence_and_determinism():
    ftypes = [
        FindingType.confirmed_patient_overlap,
        FindingType.confirmed_specimen_overlap,
        FindingType.confirmed_slide_overlap,
        FindingType.confirmed_byte_content_duplicate,
        FindingType.confirmed_pixel_content_duplicate,
        FindingType.institution_overlap,
        FindingType.image_similarity_candidate,
        FindingType.image_read_error,
        FindingType.resource_limit_exceeded,
    ]
    findings = tuple(
        finding(
            t,
            ("r1",)
            if t in {FindingType.image_read_error, FindingType.resource_limit_exceeded}
            else ("r1", "r2"),
            ConfirmationLevel.warning
            if t is FindingType.institution_overlap
            else ConfirmationLevel.confirmed,
            fid=f"f{i}",
        )
        for i, t in enumerate(ftypes)
    )
    result = evaluate_findings(tuple(reversed(findings)), get_policy_profile())
    assert result.violations == 5
    assert result.allowed_overlaps == 1
    assert result.review_items == 3
    assert result.exit_code == 2
    assert result.evaluated_findings[0].evidence == findings[0].evidence
    assert all(
        f.policy_profile == "patient_independent_pathology_benchmark"
        for f in result.evaluated_findings
    )
    assert set(result.repair_eligible_finding_ids) == {"f0", "f1", "f2", "f3", "f4"}
    assert result.model_dump(mode="json") == evaluate_findings(
        findings, get_policy_profile()
    ).model_dump(mode="json")


def test_policy_disabled_and_similarity_fail_audit():
    policy = SplitPolicy(
        patient_disjoint=False,
        specimen_disjoint=False,
        slide_disjoint=False,
        exact_byte_content_disjoint=False,
        exact_pixel_content_disjoint=False,
        institution_disjoint=True,
        similarity_candidates_fail_audit=True,
    )
    findings = (
        finding(FindingType.confirmed_patient_overlap, fid="p"),
        finding(
            FindingType.institution_overlap, level=ConfirmationLevel.warning, fid="i"
        ),
        finding(FindingType.image_similarity_candidate, fid="s"),
    )
    outcomes = {
        f.finding_id: f.policy_outcome
        for f in evaluate_findings(findings, policy).evaluated_findings
    }
    assert outcomes == {
        "p": PolicyOutcome.allowed_overlap,
        "i": PolicyOutcome.violation,
        "s": PolicyOutcome.violation,
    }
