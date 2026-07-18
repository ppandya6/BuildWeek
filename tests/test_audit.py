from pathlib import Path

from conftest import audit_config
from slidelineage.audit import run_audit
from slidelineage.models import AuditStatus


def test_complete_clean_audit_writes_artifacts_and_metadata(tmp_path: Path) -> None:
    result = run_audit(audit_config(tmp_path))
    assert result.exit_code == 0
    assert result.report.status is AuditStatus.passed
    assert result.artifacts is not None
    assert result.artifacts.report_json.is_file()
    assert result.artifacts.report_html.is_file()
    assert result.artifacts.findings_csv.is_file()
    assert result.artifacts.repair_proposal_csv is None
    assert result.report.reproducibility.config_digest
    assert result.report.schema_mappings is not None
    assert "SlideLineage audit complete" in result.terminal_summary


def test_policy_violations_return_two_and_artifacts_remain(tmp_path: Path) -> None:
    result = run_audit(audit_config(tmp_path, same_patient=True))
    assert result.exit_code == 2
    assert result.report.status is AuditStatus.policy_violations
    assert result.report.policy_evaluation.violations == 1
    assert result.artifacts is not None and result.artifacts.report_json.exists()


def test_repair_generated_only_when_requested(tmp_path: Path) -> None:
    result = run_audit(audit_config(tmp_path, same_patient=True, repair=True))
    assert result.exit_code == 2
    assert result.report.repair_proposal is not None
    assert result.artifacts is not None
    assert result.artifacts.repair_proposal_csv is not None
    assert result.artifacts.repair_proposal_csv.is_file()
    assert "researcher review" in result.artifacts.repair_proposal_csv.read_text()
