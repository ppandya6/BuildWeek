"""Deterministic repair proposal construction."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable

from slidelineage.errors import InvalidTargetFractionError, RepairAssignmentError
from slidelineage.models import (
    CanonicalRecord,
    CanonicalRecordPair,
    EvaluatedFinding,
    FindingType,
    Partition,
    PolicyOutcome,
    RepairComponent,
    RepairDecision,
    RepairProposal,
)
from slidelineage.policy import SplitPolicy

DEFAULT_REPAIR_TYPES = frozenset(
    {
        FindingType.confirmed_patient_overlap,
        FindingType.confirmed_specimen_overlap,
        FindingType.confirmed_slide_overlap,
        FindingType.confirmed_byte_content_duplicate,
        FindingType.confirmed_pixel_content_duplicate,
    }
)
INSTITUTION_TYPE = FindingType.institution_overlap


def build_repair_components(
    pair: CanonicalRecordPair,
    evaluated_findings: tuple[EvaluatedFinding, ...],
    *,
    group_by_institution: bool = False,
) -> tuple[RepairComponent, ...]:
    records = {
        record.record_id: record for record in pair.train.records + pair.test.records
    }
    parent = {rid: rid for rid in records}
    finding_ids_by_edge_records: dict[frozenset[str], set[str]] = defaultdict(set)

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for finding in sorted(evaluated_findings, key=lambda item: item.finding_id):
        if not _included(finding, group_by_institution):
            continue
        ids = tuple(sorted(finding.record_ids))
        if any(rid not in records for rid in ids):
            raise RepairAssignmentError("repair finding references an unknown record")
        for rid in ids[1:]:
            union(ids[0], rid)
        finding_ids_by_edge_records[frozenset(ids)].add(finding.finding_id)

    grouped: dict[str, list[str]] = defaultdict(list)
    for rid in sorted(records):
        grouped[find(rid)].append(rid)

    components = []
    for ids in sorted((tuple(v) for v in grouped.values()), key=lambda v: v[0]):
        finding_ids = tuple(
            sorted(
                fid
                for recset, fids in finding_ids_by_edge_records.items()
                if recset.issubset(set(ids))
                for fid in fids
            )
        )
        labels: dict[str, int] = {}
        partitions = {Partition.train: 0, Partition.test: 0}
        for rid in ids:
            rec = records[rid]
            partitions[rec.assigned_partition] += 1
            labels[rec.label if rec.label is not None else "__missing__"] = (
                labels.get(rec.label if rec.label is not None else "__missing__", 0) + 1
            )
        components.append(
            RepairComponent(
                component_id=_component_id(ids, finding_ids),
                record_ids=ids,
                confirming_finding_ids=finding_ids,
                original_partition_counts=partitions,
                label_counts=dict(sorted(labels.items())),
                conflict_status="cross_partition"
                if partitions[Partition.train] and partitions[Partition.test]
                else None,
            )
        )
    return tuple(components)


def propose_repair(
    pair: CanonicalRecordPair,
    evaluated_findings: tuple[EvaluatedFinding, ...],
    policy: SplitPolicy,
    *,
    target_train_fraction: float | None = None,
    group_by_institution: bool = False,
) -> RepairProposal:
    records = {
        record.record_id: record for record in pair.train.records + pair.test.records
    }
    total = len(records)
    if total == 0:
        raise RepairAssignmentError("repair requires at least one record")
    original_train = sum(
        r.assigned_partition is Partition.train for r in records.values()
    )
    target_fraction = (
        original_train / total
        if target_train_fraction is None
        else target_train_fraction
    )
    if not 0 < target_fraction < 1:
        raise InvalidTargetFractionError(
            "target_train_fraction must be strictly between 0 and 1"
        )
    target_train_count = target_fraction * total
    components = build_repair_components(
        pair, evaluated_findings, group_by_institution=group_by_institution
    )
    assigned: dict[str, Partition] = {}
    train_count = 0
    train_labels: dict[str, int] = defaultdict(int)
    overall_labels = _overall_labels(records.values())
    has_missing = "__missing__" in overall_labels
    ordered = sorted(
        components,
        key=lambda c: (
            -len(c.record_ids),
            -_cross_finding_count(c, evaluated_findings),
            c.record_ids[0],
        ),
    )
    decisions = []
    for comp in ordered:
        candidates = []
        for partition in (Partition.train, Partition.test):
            new_train = train_count + (
                len(comp.record_ids) if partition is Partition.train else 0
            )
            ratio_dev = abs(new_train - target_train_count)
            label_dev = (
                _label_deviation(
                    train_labels, comp, partition, overall_labels, target_fraction
                )
                if overall_labels and not has_missing
                else 0.0
            )
            moved = tuple(
                rid
                for rid in comp.record_ids
                if records[rid].assigned_partition is not partition
            )
            candidates.append(
                (
                    ratio_dev,
                    label_dev,
                    len(moved),
                    0 if partition is Partition.train else 1,
                    partition,
                    moved,
                )
            )
        ratio_dev, label_dev, _, _, partition, moved = min(candidates)
        assigned[comp.component_id] = partition
        if partition is Partition.train:
            train_count += len(comp.record_ids)
            for label, count in comp.label_counts.items():
                train_labels[label] += count
        decisions.append(
            RepairDecision(
                component_id=comp.component_id,
                proposed_partition=partition,
                moved_record_ids=moved,
                reason=(
                    "Greedy deterministic assignment preserves each repair "
                    "component as indivisible."
                ),
                ratio_deviation=float(ratio_dev / total),
                label_distribution_deviation=float(label_dev),
                deterministic_tie_break_explanation=(
                    "Objective order: train-count deviation, label deviation, "
                    "moved records, then train before test."
                ),
            )
        )
    comps = tuple(
        c.model_copy(update={"proposed_partition": assigned[c.component_id]})
        for c in components
    )
    assigned_records = [rid for c in comps for rid in c.record_ids]
    if sorted(assigned_records) != sorted(records):
        raise RepairAssignmentError("every input record must be assigned exactly once")
    moved_count = sum(len(d.moved_record_ids) for d in decisions)
    included = tuple(
        sorted(
            {
                _rel(f.finding_type)
                for f in evaluated_findings
                if _included(f, group_by_institution)
            },
            key=lambda x: x.value,
        )
    )
    excluded = tuple(
        sorted(
            {
                _rel(f.finding_type)
                for f in evaluated_findings
                if not _included(f, group_by_institution)
            },
            key=lambda x: x.value,
        )
    )
    tradeoffs = _tradeoffs(
        evaluated_findings,
        comps,
        target_train_count,
        train_count,
        overall_labels,
        has_missing,
        group_by_institution,
    )
    metrics: dict[str, int | float | str | bool | None] = {
        "original_train_fraction": original_train / total,
        "proposed_train_fraction": train_count / total,
        "target_train_fraction": target_fraction,
        "records_moved": moved_count,
        "component_count": len(comps),
        "largest_component_size": max(len(c.record_ids) for c in comps),
        "label_distribution_before": json.dumps(overall_labels, sort_keys=True),
        "label_distribution_after": json.dumps(_after_labels(comps), sort_keys=True),
    }
    return RepairProposal(
        generated=True,
        policy_profile=policy.name,
        included_relationship_types=included,
        excluded_relationship_types=excluded,
        components=comps,
        decisions=tuple(sorted(decisions, key=lambda d: d.component_id)),
        unresolved_conflicts=tuple(c.component_id for c in comps if c.conflict_status),
        tradeoffs=tuple(sorted(set(tradeoffs))),
        metrics=metrics,
    )


def _included(f: EvaluatedFinding, group_by_institution: bool) -> bool:
    if f.finding_type is INSTITUTION_TYPE:
        return group_by_institution and f.policy_outcome in {
            PolicyOutcome.violation,
            PolicyOutcome.allowed_overlap,
        }
    return f.repair_eligible and f.finding_type in DEFAULT_REPAIR_TYPES


def _rel(ftype: FindingType) -> FindingType:
    return ftype


def _component_id(record_ids: tuple[str, ...], finding_ids: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"record_ids": record_ids, "finding_ids": finding_ids},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "component_" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _cross_finding_count(
    comp: RepairComponent, findings: tuple[EvaluatedFinding, ...]
) -> int:
    ids = set(comp.confirming_finding_ids)
    return sum(
        1
        for f in findings
        if f.finding_id in ids
        and set(f.partitions_involved) == {Partition.train, Partition.test}
    )


def _overall_labels(records: Iterable[CanonicalRecord]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for rec in records:
        label = rec.label if rec.label is not None else "__missing__"
        labels[label] = labels.get(label, 0) + 1
    return dict(sorted(labels.items()))


def _label_deviation(
    current: dict[str, int],
    comp: RepairComponent,
    partition: Partition,
    overall: dict[str, int],
    target_fraction: float,
) -> float:
    proposed = dict(current)
    if partition is Partition.train:
        for label, count in comp.label_counts.items():
            proposed[label] = proposed.get(label, 0) + count
    return sum(
        abs(proposed.get(label, 0) - (count * target_fraction))
        for label, count in overall.items()
    )


def _after_labels(
    components: tuple[RepairComponent, ...],
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {
        Partition.train.value: {},
        Partition.test.value: {},
    }
    for comp in components:
        if comp.proposed_partition is None:
            continue
        bucket = out[comp.proposed_partition.value]
        for label, count in comp.label_counts.items():
            bucket[label] = bucket.get(label, 0) + count
    return out


def _tradeoffs(
    findings: tuple[EvaluatedFinding, ...],
    comps: tuple[RepairComponent, ...],
    target_train_count: float,
    train_count: int,
    overall_labels: dict[str, int],
    has_missing: bool,
    group_by_institution: bool,
) -> list[str]:
    msgs: list[str] = []
    if abs(train_count - target_train_count) > 1e-9:
        msgs.append(
            "Exact target train fraction is impossible or was not selected "
            "under indivisible repair components."
        )
    if any(len(c.record_ids) > target_train_count for c in comps):
        msgs.append(
            "At least one indivisible component exceeds the target train "
            "partition size."
        )
    if has_missing:
        msgs.append("Some labels are missing; label-distribution scoring was skipped.")
    if (
        any(f.finding_type is INSTITUTION_TYPE for f in findings)
        and not group_by_institution
    ):
        msgs.append(
            "Institution overlap findings remain outside repair grouping "
            "unless explicitly enabled."
        )
    if any(f.finding_type is FindingType.image_similarity_candidate for f in findings):
        msgs.append(
            "Image-similarity candidates remain outside repair grouping because "
            "they are not confirmed lineage evidence."
        )
    if any(
        f.finding_type
        in {FindingType.image_read_error, FindingType.resource_limit_exceeded}
        for f in findings
    ):
        msgs.append(
            "Input-quality findings reduce confidence in the audit and require "
            "researcher review."
        )
    return msgs
