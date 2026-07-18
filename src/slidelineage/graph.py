"""Deterministic relationship graph materialization from factual findings."""

from itertools import combinations

from slidelineage.errors import GraphReferenceError
from slidelineage.models import (
    CanonicalRecordPair,
    ConfirmationLevel,
    EvaluatedFinding,
    FactualFinding,
    FindingType,
    GraphEdge,
    GraphNode,
    RelationshipGraph,
)

EDGE_FINDING_TYPES = frozenset(
    {
        FindingType.confirmed_patient_overlap,
        FindingType.confirmed_specimen_overlap,
        FindingType.confirmed_slide_overlap,
        FindingType.institution_overlap,
        FindingType.confirmed_byte_content_duplicate,
        FindingType.confirmed_pixel_content_duplicate,
        FindingType.image_similarity_candidate,
    }
)


def build_relationship_graph(
    pair: CanonicalRecordPair,
    findings: tuple[FactualFinding | EvaluatedFinding, ...],
) -> RelationshipGraph:
    """Build a stable graph that materializes existing finding evidence only."""

    records = sorted(
        pair.train.records + pair.test.records, key=lambda record: record.record_id
    )
    record_ids = {record.record_id for record in records}
    nodes = tuple(
        GraphNode(
            record_id=record.record_id,
            partition=record.assigned_partition,
            label=record.label,
        )
        for record in records
    )
    finding_ids = {finding.finding_id for finding in findings}
    if len(finding_ids) != len(findings):
        raise GraphReferenceError("finding IDs must be unique when building a graph")

    edge_by_key: dict[tuple[str, str, str, FindingType], GraphEdge] = {}
    for finding in sorted(findings, key=lambda item: item.finding_id):
        if finding.finding_id not in finding_ids:
            raise GraphReferenceError("graph edge references an absent finding")
        if finding.finding_type not in EDGE_FINDING_TYPES:
            continue
        ids = tuple(sorted(finding.record_ids))
        if any(record_id not in record_ids for record_id in ids):
            raise GraphReferenceError(
                "finding references a record without a graph node"
            )
        for source, target in combinations(ids, 2):
            if source == target:
                raise GraphReferenceError("relationship graph rejects self-edges")
            key = (source, target, finding.finding_id, finding.finding_type)
            edge_by_key.setdefault(
                key,
                GraphEdge(
                    source_record_id=source,
                    target_record_id=target,
                    finding_id=finding.finding_id,
                    relationship_type=finding.finding_type,
                    confirmation_level=_edge_confirmation(
                        finding.finding_type, finding.confirmation_level
                    ),
                    policy_outcome=getattr(finding, "policy_outcome", None),
                ),
            )
    return RelationshipGraph(
        nodes=nodes, edges=tuple(edge_by_key[key] for key in sorted(edge_by_key))
    )


def _edge_confirmation(
    ftype: FindingType, level: ConfirmationLevel
) -> ConfirmationLevel:
    if ftype is FindingType.image_similarity_candidate:
        return ConfirmationLevel.probable
    if ftype is FindingType.institution_overlap:
        return ConfirmationLevel.warning
    return level
