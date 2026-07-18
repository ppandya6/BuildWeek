"""End-to-end deterministic audit orchestration."""

import platform
import uuid
from collections import Counter
from datetime import UTC, datetime
from importlib import metadata

from slidelineage import __version__
from slidelineage.ai_schema import (
    PRIVACY_NOTICE,
    ai_request_digest,
    apply_validated_ai_schema_proposal,
    build_ai_schema_request,
    request_ai_schema_proposal,
    validate_ai_schema_proposal,
)
from slidelineage.config import AuditConfig
from slidelineage.detectors import run_factual_detectors
from slidelineage.errors import AiSchemaError, InsufficientSchemaCoverageError
from slidelineage.graph import build_relationship_graph
from slidelineage.ingest import load_manifest
from slidelineage.models import (
    AiUsageRecord,
    AuditReport,
    AuditRunResult,
    AuditStatus,
    FindingSummary,
    FindingType,
    InputSummary,
    LoadedManifestPair,
    Partition,
    PolicyEvaluationSummary,
    ReproducibilityMetadata,
    RunMetadata,
    ToolMetadata,
)
from slidelineage.policy import get_policy_profile
from slidelineage.policy_evaluation import evaluate_findings
from slidelineage.records import construct_record_pair
from slidelineage.repair import propose_repair
from slidelineage.reporting import prepare_output_directory, write_audit_artifacts
from slidelineage.schema_mapping import ManifestSchemaMappings, map_manifest_pair


def run_audit(config: AuditConfig) -> AuditRunResult:
    """Run the deterministic audit pipeline and write configured artifacts."""

    started = datetime.now(UTC)
    prepare_output_directory(config.output_dir, force=config.force)
    train = load_manifest(config.train_manifest, Partition.train, "train_manifest")
    test = load_manifest(config.test_manifest, Partition.test, "test_manifest")
    loaded_pair = LoadedManifestPair(train=train, test=test)
    mappings = map_manifest_pair(loaded_pair, config)
    mappings, ai_usage, ai_warnings = _assist_schema(loaded_pair, mappings, config)
    records = construct_record_pair(loaded_pair, mappings)
    detections = run_factual_detectors(records, config)
    graph = build_relationship_graph(records, detections.all_findings)
    policy = get_policy_profile(config.policy_profile)
    policy_result = evaluate_findings(detections.all_findings, policy)
    repair = (
        propose_repair(
            records,
            policy_result.evaluated_findings,
            policy,
            target_train_fraction=config.target_train_fraction,
            group_by_institution=config.group_by_institution,
        )
        if config.repair
        else None
    )
    completed = datetime.now(UTC)
    status = (
        AuditStatus.policy_violations
        if policy_result.violations
        else AuditStatus.passed
    )
    canonical_records = tuple(
        sorted(records.train.records + records.test.records, key=lambda r: r.record_id)
    )
    report = AuditReport(
        tool=ToolMetadata(version=__version__),
        run=RunMetadata(
            run_id=f"run-{uuid.uuid4()}",
            started_at=started,
            completed_at=completed,
        ),
        inputs=InputSummary(
            manifests=(train.source, test.source),
            image_root=config.images_dir,
            total_records=len(canonical_records),
            train_records=len(records.train.records),
            test_records=len(records.test.records),
        ),
        configuration=config,
        policy=policy,
        schema_mapping=mappings.train,
        schema_mappings=mappings.model_dump(mode="json"),
        ai_schema_assistance=ai_usage,
        status=status,
        summary=_summary(records, detections.all_findings, policy_result, repair),
        canonical_records=canonical_records,
        factual_findings=detections.all_findings,
        evaluated_findings=policy_result.evaluated_findings,
        relationship_graph=graph,
        policy_evaluation=PolicyEvaluationSummary(
            policy_profile=policy_result.policy_profile,
            violations=policy_result.violations,
            allowed_overlaps=policy_result.allowed_overlaps,
            review_items=policy_result.review_items,
            not_applicable=policy_result.not_applicable,
        ),
        repair_proposal=repair,
        reproducibility=_reproducibility(
            config, train.source.sha256, test.source.sha256
        ),
        warnings=_warnings(
            train.warnings,
            test.warnings,
            mappings.validation_messages,
            records.train.warnings,
            records.test.warnings,
            detections.warnings,
            ai_warnings,
        ),
    )
    terminal_summary = _terminal_summary(report, config.output_dir)
    result = AuditRunResult(
        report=report,
        exit_code=policy_result.exit_code,
        terminal_summary=terminal_summary,
        warnings=report.warnings,
    )
    artifacts = write_audit_artifacts(result, config.output_dir)
    return result.model_copy(update={"artifacts": artifacts})


def _assist_schema(
    pair: LoadedManifestPair,
    mappings: ManifestSchemaMappings,
    config: AuditConfig,
) -> tuple[ManifestSchemaMappings, AiUsageRecord, tuple[str, ...]]:
    disabled = AiUsageRecord(
        enabled=False, privacy_summary="AI disabled; no data sent to an AI provider."
    )
    if not config.ai_schema_map:
        return mappings, disabled, ()
    acceptance = config.accept_validated_ai_mapping
    unresolved = set(mappings.train.unresolved_fields) | set(
        mappings.test.unresolved_fields
    )
    if not unresolved:
        warning = (
            "AI schema assistance was enabled but unnecessary; no request was sent."
        )
        return (
            mappings,
            AiUsageRecord(
                enabled=True,
                acceptance_requested=acceptance,
                model=config.ai_model,
                provider="openai",
                privacy_summary=PRIVACY_NOTICE,
                warnings=(warning,),
            ),
            (warning,),
        )
    request = build_ai_schema_request(pair.train, pair.test, mappings, config)
    digest = ai_request_digest(request)
    try:
        proposal = request_ai_schema_proposal(request, config)
        validated = validate_ai_schema_proposal(proposal, pair, mappings)
        applied = apply_validated_ai_schema_proposal(
            mappings, validated, accept=acceptance
        )
        applied_count = len(validated.accepted_fields) if acceptance else 0
        validated = validated.model_copy(
            update={
                "acceptance_requested": acceptance,
                "applied": applied_count > 0,
            }
        )
        usage = AiUsageRecord(
            enabled=True,
            proposal_requested=True,
            proposal_received=True,
            proposal_validated=True,
            acceptance_requested=acceptance,
            accepted_field_count=len(validated.accepted_fields),
            rejected_field_count=len(validated.rejected_fields),
            model=proposal.model,
            provider=proposal.provider,
            request_digest=digest,
            proposal_id=proposal.proposal_id,
            response_id=proposal.response_id,
            privacy_summary=PRIVACY_NOTICE,
            warnings=()
            if acceptance
            else (
                "Validated AI proposal was not applied; explicit acceptance is "
                "required.",
            ),
            validated_proposal=validated,
        )
        mappings = applied
    except AiSchemaError as exc:
        if not _minimum_coverage(mappings):
            raise
        warning = f"AI schema assistance failed; deterministic audit continued: {exc}"
        usage = AiUsageRecord(
            enabled=True,
            proposal_requested=True,
            acceptance_requested=acceptance,
            model=config.ai_model,
            provider="openai",
            request_digest=digest,
            privacy_summary=PRIVACY_NOTICE,
            warnings=(warning,),
        )
        return mappings, usage, (warning,)
    if not _minimum_coverage(mappings):
        raise InsufficientSchemaCoverageError(
            "schema mapping still requires image_path or source_record_id after AI "
            "assistance"
        )
    return mappings, usage, usage.warnings


def _minimum_coverage(mappings: ManifestSchemaMappings) -> bool:
    return all(
        mapping.image_path.source_column is not None
        or mapping.source_record_id.source_column is not None
        for mapping in (mappings.train, mappings.test)
    )


def _summary(records, findings, policy_result, repair) -> FindingSummary:  # type: ignore[no-untyped-def]
    counts = Counter(f.finding_type for f in findings)
    metrics = {
        "train_records": len(records.train.records),
        "test_records": len(records.test.records),
        "patient_overlap_findings": counts[FindingType.confirmed_patient_overlap],
        "specimen_overlap_findings": counts[FindingType.confirmed_specimen_overlap],
        "slide_overlap_findings": counts[FindingType.confirmed_slide_overlap],
        "institution_warnings": counts[FindingType.institution_overlap],
        "byte_duplicate_findings": counts[FindingType.confirmed_byte_content_duplicate],
        "pixel_duplicate_findings": counts[
            FindingType.confirmed_pixel_content_duplicate
        ],
        "image_similarity_candidates": counts[FindingType.image_similarity_candidate],
        "image_input_quality_findings": counts[FindingType.image_read_error],
        "resource_limit_findings": counts[FindingType.resource_limit_exceeded],
        "policy_violations": policy_result.violations,
        "allowed_overlaps": policy_result.allowed_overlaps,
        "review_items": policy_result.review_items,
        "unresolved_schema_fields": len(records.train.warnings)
        + len(records.test.warnings),
        "lineage_conflicts": len(records.train.conflicts) + len(records.test.conflicts),
        "moved_records": 0
        if repair is None
        else repair.metrics.get("records_moved", 0),
    }
    return FindingSummary(
        factual_finding_count=len(findings),
        evaluated_finding_count=len(policy_result.evaluated_findings),
        review_item_count=policy_result.review_items,
        violation_count=policy_result.violations,
        metrics=metrics,
    )


def _reproducibility(
    config: AuditConfig, train_sha: str, test_sha: str
) -> ReproducibilityMetadata:
    dependencies = {}
    for package in ("pydantic", "typer", "jinja2", "pillow", "imagehash"):
        try:
            dependencies[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return ReproducibilityMetadata(
        config_digest=config.digest(),
        python_version=platform.python_version(),
        slidelineage_version=__version__,
        dependency_versions=dict(sorted(dependencies.items())),
        manifest_sha256={"train_manifest": train_sha, "test_manifest": test_sha},
        detector_versions=("slidelineage-detectors-v1",),
        image_thresholds={
            "max_image_pairs": config.max_image_pairs,
            "phash_distance_threshold": config.phash_distance_threshold,
            "dhash_distance_threshold": config.dhash_distance_threshold,
            "image_max_pixels": config.image_max_pixels,
        },
        policy_profile=config.policy_profile,
    )


def _warnings(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({warning for group in groups for warning in group}))


def _terminal_summary(report: AuditReport, output_dir) -> str:  # type: ignore[no-untyped-def]
    m = report.summary.metrics
    status = "POLICY VIOLATIONS" if report.policy_evaluation.violations else "PASSED"
    repair = "generated" if report.repair_proposal else "not requested"
    lines = [
        "SlideLineage audit complete",
        f"Train records: {m.get('train_records', 0)}",
        f"Test records: {m.get('test_records', 0)}",
        f"Patient overlaps: {m.get('patient_overlap_findings', 0)}",
        f"Specimen overlaps: {m.get('specimen_overlap_findings', 0)}",
        f"Slide overlaps: {m.get('slide_overlap_findings', 0)}",
        f"Byte duplicates: {m.get('byte_duplicate_findings', 0)}",
        f"Pixel duplicates: {m.get('pixel_duplicate_findings', 0)}",
        f"Similarity candidates: {m.get('image_similarity_candidates', 0)}",
        f"Institution warnings: {m.get('institution_warnings', 0)}",
        f"Image input issues: {m.get('image_input_quality_findings', 0)}",
        f"Policy violations: {report.policy_evaluation.violations}",
        f"Review items: {report.policy_evaluation.review_items}",
        f"Repair proposal: {repair}",
        "AI schema assistance: "
        + (
            "applied"
            if report.ai_schema_assistance.validated_proposal
            and report.ai_schema_assistance.validated_proposal.applied
            else "proposed only"
            if report.ai_schema_assistance.proposal_received
            else "enabled; no proposal"
            if report.ai_schema_assistance.enabled
            else "disabled"
        ),
        f"Output: {output_dir}",
        "Artifacts: report.json, report.html, findings.csv"
        + (", repair_proposal.csv" if report.repair_proposal else ""),
        f"Status: {status}",
    ]
    return "\n".join(lines)
