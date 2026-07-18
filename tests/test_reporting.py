import csv
import json
from pathlib import Path

import pytest

from conftest import audit_config
from slidelineage.audit import run_audit
from slidelineage.errors import ArtifactWriteError, OutputDirectoryError
from slidelineage.html_report import render_html_report
from slidelineage.models import AuditReport
from slidelineage.reporting import prepare_output_directory, write_audit_artifacts


def test_output_directory_safety_and_force(tmp_path: Path) -> None:
    out = tmp_path / "out"
    prepare_output_directory(out)
    assert out.is_dir()
    (out / "note.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(OutputDirectoryError):
        prepare_output_directory(out)
    (out / "report.json").write_text("old", encoding="utf-8")
    prepare_output_directory(out, force=True)
    assert (out / "note.txt").read_text(encoding="utf-8") == "keep"
    assert not (out / "report.json").exists()
    file_out = tmp_path / "file"
    file_out.write_text("x", encoding="utf-8")
    with pytest.raises(OutputDirectoryError):
        prepare_output_directory(file_out)


def test_json_csv_html_outputs_are_valid_and_escaped(tmp_path: Path) -> None:
    cfg = audit_config(tmp_path, same_patient=True, repair=True)
    result = run_audit(cfg)
    assert result.artifacts is not None
    payload = json.loads(result.artifacts.report_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    AuditReport.model_validate(payload)
    findings = list(csv.DictReader(result.artifacts.findings_csv.open(newline="")))
    assert (
        findings
        and findings[0]["finding_id"] == sorted(r["finding_id"] for r in findings)[0]
    )
    repair_rows = list(
        csv.DictReader(result.artifacts.repair_proposal_csv.open(newline=""))
    )
    assert len({r["record_id"] for r in repair_rows}) == 2
    assert {r["source_manifest_id"] for r in repair_rows} == {
        "train_manifest",
        "test_manifest",
    }
    html = result.artifacts.report_html.read_text(encoding="utf-8")
    assert "<html" in html and "No clinical interpretation" in html
    assert "http://" not in html and "https://" not in html


def test_html_escapes_script_tags_and_writer_failure_is_atomic(tmp_path: Path) -> None:
    result = run_audit(audit_config(tmp_path))
    report = result.report.model_copy(
        update={"warnings": ("<script>alert(1)</script>",)}
    )
    html = render_html_report(report)
    assert "&lt;script&gt;" in html or "<script>alert" not in html
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "report.json").mkdir()
    with pytest.raises(ArtifactWriteError):
        write_audit_artifacts(result, bad)
