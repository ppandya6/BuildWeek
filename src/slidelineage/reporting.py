"""Artifact writers for deterministic Slide-of-Life audit reports."""

import csv
import json
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from slidelineage.errors import (
    ArtifactWriteError,
    OutputDirectoryError,
    ReportSerializationError,
)
from slidelineage.html_report import render_html_report
from slidelineage.models import (
    AuditArtifactPaths,
    AuditReport,
    AuditRunResult,
    EvaluatedFinding,
    Partition,
)

KNOWN_ARTIFACTS = ("report.json", "report.html", "findings.csv", "repair_proposal.csv")
FINDINGS_COLUMNS = (
    "finding_id",
    "finding_type",
    "confirmation_level",
    "policy_outcome",
    "policy_rule",
    "policy_reason",
    "policy_profile",
    "repair_eligible",
    "partitions",
    "record_ids",
    "detector_name",
    "detector_version",
    "parser_version",
    "matched_field",
    "matched_value",
    "evidence_count",
    "metrics_json",
    "created_at",
)
REPAIR_COLUMNS = (
    "record_id",
    "source_manifest_id",
    "source_row_number",
    "original_partition",
    "proposed_partition",
    "component_id",
    "moved",
    "label",
    "confirming_finding_ids",
    "proposal_statement",
)


def prepare_output_directory(output_dir: Path, *, force: bool = False) -> None:
    """Create or validate an output directory without deleting unrelated files."""

    if output_dir.exists() and output_dir.is_file():
        raise OutputDirectoryError(f"output path is a file: {output_dir}")
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        return
    entries = tuple(output_dir.iterdir())
    if not entries:
        return
    unknown = [p for p in entries if p.name not in KNOWN_ARTIFACTS]
    if unknown and not force:
        raise OutputDirectoryError(
            "output directory is nonempty; use --force to replace known artifacts"
        )
    if not force:
        raise OutputDirectoryError(
            "output directory contains prior artifacts; use --force to replace them"
        )
    for name in KNOWN_ARTIFACTS:
        target = output_dir / name
        if target.exists() and target.is_file():
            target.unlink()


def write_audit_artifacts(
    result: AuditRunResult, output_dir: Path
) -> AuditArtifactPaths:
    """Write JSON, HTML, findings CSV, and optional repair CSV artifacts."""

    report_json = output_dir / "report.json"
    report_html = output_dir / "report.html"
    findings_csv = output_dir / "findings.csv"
    repair_csv = (
        output_dir / "repair_proposal.csv" if result.report.repair_proposal else None
    )
    try:
        _write_text_atomic(report_json, _report_json(result.report))
        _write_text_atomic(report_html, render_html_report(result.report))
        _write_text_atomic(
            findings_csv, _findings_csv(result.report.evaluated_findings)
        )
        if repair_csv is not None:
            _write_text_atomic(repair_csv, _repair_csv(result.report))
    except ArtifactWriteError:
        raise
    except OSError as exc:
        raise ArtifactWriteError("failed to write audit artifacts") from exc
    return AuditArtifactPaths(
        output_dir=output_dir,
        report_json=report_json,
        report_html=report_html,
        findings_csv=findings_csv,
        repair_proposal_csv=repair_csv,
    )


def _report_json(report: AuditReport) -> str:
    try:
        validated = AuditReport.model_validate(report.model_dump(mode="python"))
    except ValidationError as exc:
        raise ReportSerializationError("report failed typed validation") from exc
    return (
        json.dumps(
            validated.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def _findings_csv(findings: tuple[EvaluatedFinding, ...]) -> str:
    rows = []
    for finding in sorted(findings, key=lambda f: f.finding_id):
        matched_fields = sorted({e.matched_field or "" for e in finding.evidence})
        matched_values = sorted({e.matched_value or "" for e in finding.evidence})
        rows.append(
            {
                "finding_id": finding.finding_id,
                "finding_type": finding.finding_type.value,
                "confirmation_level": finding.confirmation_level.value,
                "policy_outcome": finding.policy_outcome.value,
                "policy_rule": finding.policy_rule,
                "policy_reason": finding.policy_reason,
                "policy_profile": finding.policy_profile,
                "repair_eligible": str(finding.repair_eligible).lower(),
                "partitions": _join(p.value for p in finding.partitions_involved),
                "record_ids": _join(finding.record_ids),
                "detector_name": finding.detector_name,
                "detector_version": finding.detector_version,
                "parser_version": finding.parser_version or "",
                "matched_field": matched_fields[0] if len(matched_fields) == 1 else "",
                "matched_value": matched_values[0] if len(matched_values) == 1 else "",
                "evidence_count": str(len(finding.evidence)),
                "metrics_json": json.dumps(
                    finding.metrics, sort_keys=True, separators=(",", ":")
                ),
                "created_at": finding.created_at.isoformat(),
            }
        )
    return _csv_text(FINDINGS_COLUMNS, rows)


def _repair_csv(report: AuditReport) -> str:
    proposal = report.repair_proposal
    if proposal is None:
        return _csv_text(REPAIR_COLUMNS, [])
    by_record = {}
    for component in proposal.components:
        for rid in component.record_ids:
            by_record[rid] = component
    rows = []
    for component in proposal.components:
        for rid in component.record_ids:
            original = _record_metadata(report, rid)
            proposed = component.proposed_partition or Partition.train
            rows.append(
                {
                    "record_id": rid,
                    "source_manifest_id": original[0],
                    "source_row_number": str(original[1]),
                    "original_partition": original[2].value,
                    "proposed_partition": proposed.value,
                    "component_id": component.component_id,
                    "moved": str(original[2] is not proposed).lower(),
                    "label": original[3] or "",
                    "confirming_finding_ids": _join(component.confirming_finding_ids),
                    "proposal_statement": proposal.statement,
                }
            )
    rows.sort(key=lambda row: row["record_id"])
    return _csv_text(REPAIR_COLUMNS, rows)


def _record_metadata(
    report: AuditReport, record_id: str
) -> tuple[str, int, Partition, str | None]:
    for record in report.canonical_records:
        if record.record_id == record_id:
            return (
                record.source_manifest_id,
                record.source_row_number,
                record.assigned_partition,
                record.label,
            )
    for node in report.relationship_graph.nodes:
        if node.record_id == record_id:
            return "unknown", 0, node.partition, node.label
    return "unknown", 0, Partition.train, None


def _csv_text(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = ""
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(text)
        Path(tmp_name).replace(path)
    except Exception as exc:
        if tmp_name:
            with suppress(OSError):
                Path(tmp_name).unlink(missing_ok=True)
        raise ArtifactWriteError(f"failed to write artifact: {path}") from exc


def _join(values: Iterable[object]) -> str:
    return ";".join(str(v) for v in values)
