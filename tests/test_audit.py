from pathlib import Path

from conftest import audit_config
from slidelineage.audit import run_audit
from slidelineage.models import AiProposedFieldMapping, AiSchemaProposal, AuditStatus


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
    assert "Slide-of-Life audit complete" in result.terminal_summary


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


def test_ai_proposal_only_does_not_change_deterministic_findings(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    baseline = run_audit(audit_config(tmp_path / "base", same_patient=True))
    config = audit_config(tmp_path / "ai", same_patient=True).model_copy(
        update={"ai_schema_map": True}
    )

    def fake(request, config):  # type: ignore[no-untyped-def]
        return AiSchemaProposal(
            proposal_id="aip-audit-test",
            model=config.ai_model,
            response_id="resp-test",
            request_digest="1" * 64,
            proposed_fields=(
                AiProposedFieldMapping(
                    semantic_field="partition",
                    train_source_column="invented",
                    test_source_column="invented",
                    confidence=0.9,
                    rationale_code="header_alias",
                ),
            ),
            model_output_digest="2" * 64,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setattr("slidelineage.audit.request_ai_schema_proposal", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-only-key")
    result = run_audit(config)
    assert result.report.ai_schema_assistance.proposal_received
    assert not result.report.ai_schema_assistance.validated_proposal.applied
    assert [f.finding_id for f in result.report.factual_findings] == [
        f.finding_id for f in baseline.report.factual_findings
    ]
    assert result.report.policy_evaluation == baseline.report.policy_evaluation
