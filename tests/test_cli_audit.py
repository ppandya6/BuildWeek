from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import audit_manifest
from slidelineage.cli import app
from slidelineage.models import AuditReport

runner = CliRunner()


def _args(tmp_path: Path, same_patient: bool = False) -> list[str]:
    train = audit_manifest(tmp_path / "train.csv", "P1", "R1")
    test = audit_manifest(tmp_path / "test.csv", "P1" if same_patient else "P2", "R2")
    return [
        "audit",
        "--train",
        str(train),
        "--test",
        str(test),
        "--output",
        str(tmp_path / "out"),
        "--image-column",
        "img",
        "--patient-column",
        "patient",
        "--specimen-column",
        "specimen",
        "--slide-column",
        "slide",
        "--institution-column",
        "site",
        "--label-column",
        "label",
        "--record-id-column",
        "rid",
    ]


def test_audit_help_and_minimal_valid_audit(tmp_path: Path) -> None:
    help_result = runner.invoke(app, ["audit", "--help"])
    assert help_result.exit_code == 0
    assert "Default" in help_result.output or "policy" in help_result.output
    result = runner.invoke(app, _args(tmp_path))
    assert result.exit_code == 0
    assert "Status: PASSED" in result.output
    assert "findings.csv" in result.output


def test_cli_exit_two_repair_force_and_missing_manifest(tmp_path: Path) -> None:
    args = _args(tmp_path, same_patient=True) + ["--repair"]
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "POLICY VIOLATIONS" in result.output
    assert (tmp_path / "out" / "repair_proposal.csv").is_file()
    rerun = runner.invoke(app, args + ["--force"])
    assert rerun.exit_code == 2
    missing = runner.invoke(
        app,
        [
            "audit",
            "--train",
            str(tmp_path / "missing.csv"),
            "--test",
            str(tmp_path / "missing2.csv"),
            "--output",
            str(tmp_path / "badout"),
        ],
    )
    assert missing.exit_code == 1
    assert "Traceback" not in missing.output


def test_cli_invalid_policy_and_threshold(tmp_path: Path) -> None:
    bad_policy = runner.invoke(app, _args(tmp_path) + ["--policy-profile", "unknown"])
    assert bad_policy.exit_code == 1
    assert "Unknown SplitPolicy" in bad_policy.output
    bad_threshold = runner.invoke(
        app, _args(tmp_path / "t2") + ["--max-image-pairs", "0"]
    )
    assert bad_threshold.exit_code == 1


def test_cli_ai_help_and_acceptance_requires_enablement(tmp_path: Path) -> None:
    help_result = runner.invoke(app, ["audit", "--help"])
    assert "--ai-schema-map" in help_result.output
    assert "aggregate" in help_result.output and "statistics" in help_result.output
    result = runner.invoke(app, _args(tmp_path) + ["--accept-validated-ai-mapping"])
    assert result.exit_code == 1
    assert "requires ai_schema_map" in result.output
    assert "Traceback" not in result.output


def test_cli_ai_missing_optional_sdk_has_no_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_sdk(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("slidelineage.ai_schema.import_module", missing_sdk)
    args = _args(tmp_path)
    for manifest_name in ("train.csv", "test.csv"):
        manifest = tmp_path / manifest_name
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace("label", "unknown_code"),
            encoding="utf-8",
        )
    label_option = args.index("--label-column")
    del args[label_option : label_option + 2]
    result = runner.invoke(app, args + ["--ai-schema-map"])
    assert result.exit_code == 0
    assert "Traceback" not in result.output
    report = AuditReport.model_validate_json(
        (tmp_path / "out" / "report.json").read_text(encoding="utf-8")
    )
    assert any(
        "AI support requires" in warning
        for warning in report.ai_schema_assistance.warnings
    )


def test_cli_ai_missing_optional_sdk_fails_without_minimum_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_sdk(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("slidelineage.ai_schema.import_module", missing_sdk)
    args = _args(tmp_path)
    for manifest_name in ("train.csv", "test.csv"):
        manifest = tmp_path / manifest_name
        header, row = manifest.read_text(encoding="utf-8").splitlines()
        columns = row.split(",")
        columns[0] = ""
        columns[-1] = ""
        manifest.write_text(
            header.replace("img", "unknown_path").replace("rid", "unknown_record")
            + "\n"
            + ",".join(columns)
            + "\n",
            encoding="utf-8",
        )
    for option in ("--image-column", "--record-id-column"):
        option_index = args.index(option)
        del args[option_index : option_index + 2]
    result = runner.invoke(app, args + ["--ai-schema-map"])
    assert result.exit_code == 1
    assert 'python -m pip install -e ".[ai]"' in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "out" / "report.json").exists()
