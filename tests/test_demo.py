"""End-to-end contract tests for the entirely synthetic demonstration."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from slidelineage.cli import app
from slidelineage.models import AuditReport, FindingType, PolicyOutcome

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_demo.py"
SCHEMA_MAP = ROOT / "examples" / "demo" / "schema-map.yaml"
EXPECTED_TYPES = {
    FindingType.confirmed_patient_overlap,
    FindingType.confirmed_specimen_overlap,
    FindingType.confirmed_slide_overlap,
    FindingType.institution_overlap,
    FindingType.confirmed_byte_content_duplicate,
    FindingType.confirmed_pixel_content_duplicate,
    FindingType.image_similarity_candidate,
    FindingType.image_read_error,
}


def _generate(output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output), *extra],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_generator_is_deterministic_safe_and_preserves_unrelated_files(
    tmp_path: Path,
) -> None:
    output = tmp_path / "generated"
    first = _generate(output)
    assert first.returncode == 0
    assert "slidelineage audit" in first.stdout
    assert (output / "train_manifest.csv").is_file()
    assert (output / "test_manifest.csv").is_file()
    assert len(list((output / "images").iterdir())) == 11
    expected = _digests(output)

    refused = _generate(output)
    assert refused.returncode == 1
    assert "not empty" in refused.stderr
    assert "Traceback" not in refused.stderr
    unrelated = output / "researcher-note.txt"
    unrelated.write_text("preserve me", encoding="utf-8")
    repeated = _generate(output, "--force")
    assert repeated.returncode == 0
    assert unrelated.read_text(encoding="utf-8") == "preserve me"
    actual = _digests(output)
    actual.pop("researcher-note.txt")
    assert actual == expected


def test_operational_cli_demo_contract(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    assert _generate(generated).returncode == 0
    output = tmp_path / "audit"
    result = CliRunner().invoke(
        app,
        [
            "audit",
            "--train",
            str(generated / "train_manifest.csv"),
            "--test",
            str(generated / "test_manifest.csv"),
            "--images",
            str(generated / "images"),
            "--schema-map",
            str(SCHEMA_MAP),
            "--output",
            str(output),
            "--repair",
        ],
    )
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    artifact_names = {
        "report.json",
        "report.html",
        "findings.csv",
        "repair_proposal.csv",
    }
    assert all((output / name).is_file() for name in artifact_names)

    report = AuditReport.model_validate(
        json.loads((output / "report.json").read_text(encoding="utf-8"))
    )
    assert {
        finding.finding_type for finding in report.evaluated_findings
    } == EXPECTED_TYPES
    assert report.policy_evaluation.violations > 0
    assert report.policy_evaluation.review_items > 0
    by_type = {finding.finding_type: finding for finding in report.evaluated_findings}
    assert (
        by_type[FindingType.image_similarity_candidate].policy_outcome
        is PolicyOutcome.review_item
    )
    assert not by_type[FindingType.image_similarity_candidate].repair_eligible
    assert (
        by_type[FindingType.institution_overlap].policy_outcome
        is PolicyOutcome.allowed_overlap
    )
    assert not by_type[FindingType.institution_overlap].repair_eligible
    for finding_type in (
        FindingType.confirmed_patient_overlap,
        FindingType.confirmed_specimen_overlap,
        FindingType.confirmed_slide_overlap,
        FindingType.confirmed_byte_content_duplicate,
        FindingType.confirmed_pixel_content_duplicate,
    ):
        assert by_type[finding_type].policy_outcome is PolicyOutcome.violation
        assert by_type[finding_type].repair_eligible

    with (output / "findings.csv").open(newline="", encoding="utf-8") as handle:
        finding_rows = list(csv.DictReader(handle))
    assert {row["finding_type"] for row in finding_rows} == {
        finding_type.value for finding_type in EXPECTED_TYPES
    }
    with (output / "repair_proposal.csv").open(newline="", encoding="utf-8") as handle:
        repair_rows = list(csv.DictReader(handle))
    record_ids = [row["record_id"] for row in repair_rows]
    assert len(record_ids) == 12
    assert len(set(record_ids)) == 12
    assert set(record_ids) == {record.record_id for record in report.canonical_records}

    html = (output / "report.html").read_text(encoding="utf-8")
    assert "No clinical interpretation" in html
    assert "Image similarity does not establish patient identity" in html
    assert "researcher review" in html
    assert "http://" not in html and "https://" not in html
    generated_text = " ".join(
        path.read_text(encoding="utf-8")
        for path in (generated / "train_manifest.csv", generated / "test_manifest.csv")
    ).casefold()
    for prohibited in ("diagnosis", "cancer", "tumor", "disease", "clinical"):
        assert prohibited not in generated_text
