"""Evaluate factual findings under explicit SplitPolicy profiles."""

from slidelineage.models import (
    ConfirmationLevel,
    EvaluatedFinding,
    FactualFinding,
    FindingType,
    PolicyEvaluationResult,
    PolicyOutcome,
)
from slidelineage.policy import SplitPolicy

_EXACT_REPAIR_TYPES = frozenset(
    {
        FindingType.confirmed_patient_overlap,
        FindingType.confirmed_specimen_overlap,
        FindingType.confirmed_slide_overlap,
        FindingType.confirmed_byte_content_duplicate,
        FindingType.confirmed_pixel_content_duplicate,
    }
)


def evaluate_findings(
    findings: tuple[FactualFinding, ...], policy: SplitPolicy
) -> PolicyEvaluationResult:
    """Convert factual findings to evaluated findings with stable counts."""
    evaluated = tuple(
        _evaluate(f, policy) for f in sorted(findings, key=lambda item: item.finding_id)
    )
    violations = sum(f.policy_outcome is PolicyOutcome.violation for f in evaluated)
    allowed = sum(f.policy_outcome is PolicyOutcome.allowed_overlap for f in evaluated)
    review = sum(f.policy_outcome is PolicyOutcome.review_item for f in evaluated)
    na = sum(f.policy_outcome is PolicyOutcome.not_applicable for f in evaluated)
    repair_ids = tuple(f.finding_id for f in evaluated if f.repair_eligible)
    reasons = tuple(sorted({f.policy_reason for f in evaluated}))
    return PolicyEvaluationResult(
        policy_profile=policy.name,
        evaluated_findings=evaluated,
        violations=violations,
        allowed_overlaps=allowed,
        review_items=review,
        not_applicable=na,
        repair_eligible_finding_ids=repair_ids,
        exit_code=2 if violations else 0,
        reasons=reasons,
    )


def _evaluate(finding: FactualFinding, policy: SplitPolicy) -> EvaluatedFinding:
    outcome, rule, reason = _mapping(finding.finding_type, policy)
    eligible = (
        finding.finding_type in _EXACT_REPAIR_TYPES
        and outcome is PolicyOutcome.violation
        and finding.confirmation_level
        in {ConfirmationLevel.confirmed, ConfirmationLevel.confirmed}
    )
    return EvaluatedFinding(
        **finding.model_dump(),
        policy_outcome=outcome,
        policy_rule=rule,
        policy_reason=reason,
        policy_profile=policy.name,
        repair_eligible=eligible,
    )


def _mapping(ftype: FindingType, policy: SplitPolicy) -> tuple[PolicyOutcome, str, str]:
    checks = {
        FindingType.confirmed_patient_overlap: (
            policy.patient_disjoint,
            "patient_disjoint",
            "Confirmed patient overlap",
        ),
        FindingType.confirmed_specimen_overlap: (
            policy.specimen_disjoint,
            "specimen_disjoint",
            "Confirmed specimen overlap",
        ),
        FindingType.confirmed_slide_overlap: (
            policy.slide_disjoint,
            "slide_disjoint",
            "Confirmed slide overlap",
        ),
        FindingType.confirmed_byte_content_duplicate: (
            policy.exact_byte_content_disjoint,
            "exact_byte_content_disjoint",
            "Exact byte-content duplicate",
        ),
        FindingType.confirmed_pixel_content_duplicate: (
            policy.exact_pixel_content_disjoint,
            "exact_pixel_content_disjoint",
            "Exact pixel-content duplicate",
        ),
        FindingType.institution_overlap: (
            policy.institution_disjoint,
            "institution_disjoint",
            "Institution overlap",
        ),
    }
    if ftype in checks:
        enabled, rule, label = checks[ftype]
        outcome = PolicyOutcome.violation if enabled else PolicyOutcome.allowed_overlap
        status = "disallowed" if enabled else "allowed"
        reason = f"{label} is {status} by policy profile {policy.name}."
        if ftype is FindingType.institution_overlap and not enabled:
            reason = (
                f"Institution reuse is allowed by policy profile {policy.name}; "
                "warning-level provenance is preserved."
            )
        return outcome, rule, reason
    if ftype is FindingType.image_similarity_candidate:
        outcome = (
            PolicyOutcome.violation
            if policy.similarity_candidates_fail_audit
            else PolicyOutcome.review_item
        )
        status = (
            "audit failures" if outcome is PolicyOutcome.violation else "review items"
        )
        return (
            outcome,
            "similarity_candidates_fail_audit",
            f"Image-similarity candidates are {status} under policy {policy.name}.",
        )
    if ftype in {FindingType.image_read_error, FindingType.resource_limit_exceeded}:
        return (
            PolicyOutcome.review_item,
            "input_quality_review",
            f"{ftype.value} requires researcher review and is not repair eligible.",
        )
    return (
        PolicyOutcome.review_item,
        "unsupported_or_ambiguous_review",
        f"{ftype.value} is retained as a review item under policy {policy.name}.",
    )
