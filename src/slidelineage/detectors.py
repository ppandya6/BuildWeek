"""Deterministic factual detectors for milestone-one lineage facts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Final

from slidelineage.config import AuditConfig
from slidelineage.image_fingerprints import fingerprint_record_images
from slidelineage.models import (
    CanonicalRecord,
    CanonicalRecordPair,
    ConfirmationLevel,
    EvidenceRecord,
    FactualDetectionResult,
    FactualFinding,
    FindingType,
    IdentifierStatus,
    ImageFingerprint,
    ImageFingerprintCollection,
    ImageReadStatus,
    Partition,
)

DETECTOR_VERSION: Final[str] = "task6-factual-detectors-v1"
DETECTOR_NAME: Final[str] = "slidelineage_deterministic_factual_detectors"
_CREATED_AT: Final[datetime] = datetime(2026, 1, 1, tzinfo=UTC)
_ID_FIELDS: Final[tuple[tuple[str, FindingType, ConfirmationLevel], ...]] = (
    ("patient_id", FindingType.confirmed_patient_overlap, ConfirmationLevel.confirmed),
    (
        "specimen_id",
        FindingType.confirmed_specimen_overlap,
        ConfirmationLevel.confirmed,
    ),
    ("slide_id", FindingType.confirmed_slide_overlap, ConfirmationLevel.confirmed),
    ("institution_id", FindingType.institution_overlap, ConfirmationLevel.warning),
)


def detect_identifier_overlaps(pair: CanonicalRecordPair) -> tuple[FactualFinding, ...]:
    """Detect cross-partition overlaps using accepted provenance only."""
    records = {r.record_id: r for r in pair.train.records + pair.test.records}
    accepted: dict[tuple[str, str], set[str]] = defaultdict(set)
    for manifest in (pair.train, pair.test):
        conflicted = {(c.record_id, c.semantic_field) for c in manifest.conflicts}
        accepted_values = {
            (p.semantic_field, p.value)
            for p in manifest.identifier_provenance
            if p.status is IdentifierStatus.accepted and p.value
        }
        for record in manifest.records:
            for field, _ftype, _level in _ID_FIELDS:
                value = getattr(record, field)
                if (
                    value
                    and (record.record_id, field) not in conflicted
                    and (field, value) in accepted_values
                ):
                    accepted[(field, value)].add(record.record_id)
    findings: list[FactualFinding] = []
    for field, ftype, level in _ID_FIELDS:
        for (semantic, value), record_ids in sorted(accepted.items()):
            if semantic != field:
                continue
            group = [records[rid] for rid in sorted(record_ids)]
            if {r.assigned_partition for r in group} == {
                Partition.train,
                Partition.test,
            }:
                findings.append(
                    _finding(
                        ftype,
                        level,
                        group,
                        _identifier_evidence(group, field, value),
                        {"semantic_field": field, "matched_value": value},
                    )
                )
    return tuple(sorted(findings, key=lambda f: f.finding_id))


def detect_image_relationships(
    pair: CanonicalRecordPair,
    fingerprints: ImageFingerprintCollection,
    config: AuditConfig,
) -> tuple[FactualFinding, ...]:
    """Detect exact image duplicates and probable similarity candidates."""
    record_map = {r.record_id: r for r in pair.train.records + pair.test.records}
    resolved = [
        f for f in fingerprints.fingerprints if f.status is ImageReadStatus.resolved
    ]
    findings: list[FactualFinding] = []
    byte_groups = _groups(resolved, "byte_sha256")
    byte_record_sets: set[frozenset[str]] = set()
    for digest, group in byte_groups:
        if _cross(group):
            byte_record_sets.add(frozenset(f.record_id for f in group))
            findings.append(
                _image_group_finding(
                    FindingType.confirmed_byte_content_duplicate,
                    ConfirmationLevel.confirmed,
                    group,
                    record_map,
                    {"byte_sha256": digest},
                )
            )
    for digest, group in _groups(resolved, "canonical_pixel_sha256"):
        if (
            _cross(group)
            and frozenset(f.record_id for f in group) not in byte_record_sets
            and len({f.byte_sha256 for f in group}) > 1
        ):
            findings.append(
                _image_group_finding(
                    FindingType.confirmed_pixel_content_duplicate,
                    ConfirmationLevel.confirmed,
                    group,
                    record_map,
                    {"canonical_pixel_sha256": digest},
                )
            )
    if fingerprints.pair_limit_exceeded:
        findings.append(_limit_finding(pair, fingerprints, config))
        return tuple(sorted(findings, key=lambda f: f.finding_id))
    train = sorted(
        [f for f in resolved if f.assigned_partition is Partition.train],
        key=lambda f: f.record_id,
    )
    test = sorted(
        [f for f in resolved if f.assigned_partition is Partition.test],
        key=lambda f: f.record_id,
    )
    for left in train:
        for right in test:
            if (
                left.byte_sha256 == right.byte_sha256
                or left.canonical_pixel_sha256 == right.canonical_pixel_sha256
            ):
                continue
            pd = _hamming(left.phash or "0", right.phash or "0")
            dd = _hamming(left.dhash or "0", right.dhash or "0")
            if (
                pd <= config.phash_distance_threshold
                and dd <= config.dhash_distance_threshold
            ):
                metrics = {
                    "phash_distance": pd,
                    "dhash_distance": dd,
                    "phash_distance_threshold": config.phash_distance_threshold,
                    "dhash_distance_threshold": config.dhash_distance_threshold,
                    "left_dimensions": f"{left.width}x{left.height}",
                    "right_dimensions": f"{right.width}x{right.height}",
                }
                findings.append(
                    _image_group_finding(
                        FindingType.image_similarity_candidate,
                        ConfirmationLevel.probable,
                        [left, right],
                        record_map,
                        metrics,
                    )
                )
    return tuple(sorted(findings, key=lambda f: f.finding_id))


def input_quality_findings(
    pair: CanonicalRecordPair,
    fingerprints: ImageFingerprintCollection,
    config: AuditConfig,
) -> tuple[FactualFinding, ...]:
    record_map = {r.record_id: r for r in pair.train.records + pair.test.records}
    findings = []
    for fp in fingerprints.fingerprints:
        if fp.status is not ImageReadStatus.resolved:
            rec = record_map[fp.record_id]
            findings.append(
                _finding(
                    FindingType.image_read_error,
                    ConfirmationLevel.warning,
                    [rec],
                    (_image_evidence(fp, rec),),
                    {"status": fp.status.value, "error_code": fp.error_code},
                )
            )
    if fingerprints.pair_limit_exceeded:
        findings.append(_limit_finding(pair, fingerprints, config))
    return tuple(sorted(findings, key=lambda f: f.finding_id))


def run_factual_detectors(
    pair: CanonicalRecordPair, config: AuditConfig
) -> FactualDetectionResult:
    fps = fingerprint_record_images(pair, config)
    identifier = detect_identifier_overlaps(pair)
    image_all = detect_image_relationships(pair, fps, config)
    quality = input_quality_findings(pair, fps, config)
    image = tuple(
        f
        for f in image_all
        if f.finding_type is not FindingType.resource_limit_exceeded
    )
    warnings = tuple(sorted(set(fps.warnings)))
    return FactualDetectionResult(
        identifier_findings=identifier,
        image_findings=image,
        input_quality_findings=quality,
        all_findings=identifier + image + quality,
        image_fingerprints=fps,
        warnings=warnings,
    )


def _groups(
    fps: Iterable[ImageFingerprint], attr: str
) -> list[tuple[str, list[ImageFingerprint]]]:
    grouped: dict[str, list[ImageFingerprint]] = defaultdict(list)
    for fp in fps:
        value = getattr(fp, attr)
        if value:
            grouped[value].append(fp)
    return sorted(
        (k, sorted(v, key=lambda f: f.record_id))
        for k, v in grouped.items()
        if len(v) > 1
    )


def _cross(group: Iterable[ImageFingerprint]) -> bool:
    return {f.assigned_partition for f in group} == {Partition.train, Partition.test}


def _identifier_evidence(
    records: list[CanonicalRecord], field: str, value: str
) -> tuple[EvidenceRecord, ...]:
    return tuple(
        EvidenceRecord(
            record_id=r.record_id,
            source_manifest_id=r.source_manifest_id,
            source_manifest_path=r.source_manifest_id,
            source_row_number=r.source_row_number,
            assigned_partition=r.assigned_partition,
            matched_field=field,
            matched_value=value,
            image_path=r.image_path,
        )
        for r in sorted(records, key=lambda r: r.record_id)
    )


def _image_evidence(fp: ImageFingerprint, rec: CanonicalRecord) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=fp.record_id,
        source_manifest_id=fp.source_manifest_id,
        source_manifest_path=fp.source_manifest_id,
        source_row_number=fp.source_row_number,
        assigned_partition=fp.assigned_partition,
        matched_field="image_path",
        matched_value=fp.source_image_path,
        image_path=fp.source_image_path,
        byte_sha256=fp.byte_sha256,
        canonical_pixel_sha256=fp.canonical_pixel_sha256,
        phash=fp.phash,
        dhash=fp.dhash,
    )


def _image_group_finding(
    ftype: FindingType,
    level: ConfirmationLevel,
    group: Iterable[ImageFingerprint],
    records: dict[str, CanonicalRecord],
    metrics: dict[str, object],
) -> FactualFinding:
    fps = sorted(group, key=lambda f: f.record_id)
    recs = [records[f.record_id] for f in fps]
    evidence = tuple(_image_evidence(f, records[f.record_id]) for f in fps)
    return _finding(ftype, level, recs, evidence, metrics)


def _limit_finding(
    pair: CanonicalRecordPair,
    fingerprints: ImageFingerprintCollection,
    config: AuditConfig,
) -> FactualFinding:
    records = sorted(pair.train.records + pair.test.records, key=lambda r: r.record_id)[
        :1
    ]
    return _finding(
        FindingType.resource_limit_exceeded,
        ConfirmationLevel.warning,
        records,
        _identifier_evidence(records, "image_pair_limit", str(config.max_image_pairs)),
        {
            "requested_pair_count": fingerprints.pair_count_considered,
            "max_image_pairs": config.max_image_pairs,
        },
    )


def _finding(
    ftype: FindingType,
    level: ConfirmationLevel,
    records: Iterable[CanonicalRecord],
    evidence: tuple[EvidenceRecord, ...],
    metrics: dict[str, object],
) -> FactualFinding:
    recs = sorted(records, key=lambda r: r.record_id)
    record_ids = tuple(r.record_id for r in recs)
    safe_metrics = {
        k: v
        for k, v in metrics.items()
        if isinstance(v, (int, float, str, bool)) or v is None
    }
    fid = _finding_id(ftype, record_ids, safe_metrics)
    return FactualFinding(
        finding_id=fid,
        finding_type=ftype,
        confirmation_level=level,
        partitions_involved=tuple(
            sorted({r.assigned_partition for r in recs}, key=lambda p: p.value)
        ),
        record_ids=record_ids,
        evidence=tuple(
            sorted(evidence, key=lambda e: (e.record_id, e.source_row_number))
        ),
        metrics=safe_metrics | {"detector_version": DETECTOR_VERSION},
        detector_name=DETECTOR_NAME,
        detector_version=DETECTOR_VERSION,
        created_at=_CREATED_AT,
    )


def _finding_id(
    ftype: FindingType,
    record_ids: tuple[str, ...],
    metrics: dict[str, int | float | str | bool | None],
) -> str:
    payload = {
        "type": ftype.value,
        "record_ids": record_ids,
        "metrics": metrics,
        "version": DETECTOR_VERSION,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return f"finding_{ftype.value}_{digest}"


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()
