from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path, PureWindowsPath

import pytest
import yaml

from slidelineage.models import AuditReport

ROOT = Path(__file__).parents[1]
SPEC = spec_from_file_location("run_action", ROOT / "scripts/run_action.py")
assert SPEC is not None and SPEC.loader is not None
ACTION = module_from_spec(SPEC)
sys.modules[SPEC.name] = ACTION
SPEC.loader.exec_module(ACTION)
ActionInputError = ACTION.ActionInputError
build_command = ACTION.build_command
parse_bool = ACTION.parse_bool
parse_float = ACTION.parse_float
parse_inputs = ACTION.parse_inputs


def _files(tmp_path: Path) -> dict[str, str]:
    train = tmp_path / "train manifest.csv"
    test = tmp_path / "test manifest.csv"
    train.write_text("record_uuid,patient\nTRAIN-1,P1\n", encoding="utf-8")
    test.write_text("record_uuid,patient\nTEST-1,P2\n", encoding="utf-8")
    return {"train-manifest": str(train), "test-manifest": str(test)}


def test_action_metadata_contract() -> None:
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert {"name", "description", "author", "inputs", "outputs", "runs"} <= data.keys()
    assert data["runs"]["using"] == "composite"
    assert data["inputs"]["train-manifest"]["required"] is True
    assert data["inputs"]["test-manifest"]["required"] is True
    assert data["inputs"]["output-dir"]["default"] == "slide-of-life-artifacts"
    assert data["inputs"]["repair"]["default"] == "false"
    assert data["inputs"]["force"]["default"] == "true"
    assert data["inputs"]["ai-schema-map"]["default"] == "false"
    assert data["inputs"]["fail-on-violations"]["default"] == "true"
    assert set(data["outputs"]) == {
        "status",
        "exit-code",
        "report-json",
        "report-html",
        "findings-csv",
        "repair-proposal-csv",
        "violation-count",
        "review-count",
    }
    assert "set-output" not in text
    assert "api-key" not in data["inputs"]
    assert "OPENAI_API_KEY" in data["description"]


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_boolean_true_forms(value: str) -> None:
    assert parse_bool(value, "flag") is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_boolean_false_forms(value: str) -> None:
    assert parse_bool(value, "flag") is False


def test_invalid_boolean_and_number() -> None:
    with pytest.raises(ActionInputError, match="recognized boolean"):
        parse_bool("sometimes", "flag")
    with pytest.raises(ActionInputError, match="number"):
        parse_float("many", "fraction")


def test_required_and_cross_field_validation(tmp_path: Path) -> None:
    with pytest.raises(ActionInputError, match="train-manifest must not be blank"):
        parse_inputs({})
    values = _files(tmp_path)
    values["target-train-fraction"] = "1"
    with pytest.raises(ActionInputError, match="less than 1"):
        parse_inputs(values)
    values = _files(tmp_path)
    values["accept-validated-ai-mapping"] = "true"
    with pytest.raises(ActionInputError, match="requires ai-schema-map"):
        parse_inputs(values)


def test_optional_arguments_are_individual_tokens(tmp_path: Path) -> None:
    values = _files(tmp_path)
    images = tmp_path / "images with spaces"
    images.mkdir()
    schema = tmp_path / "schema map.yaml"
    schema.write_text("{}", encoding="utf-8")
    values.update(
        {
            "images-dir": str(images),
            "schema-map": str(schema),
            "repair": "true",
            "group-by-institution": "true",
            "target-train-fraction": "0.7",
            "max-image-pairs": "17",
            "phash-distance-threshold": "4",
            "dhash-distance-threshold": "6",
            "image-max-pixels": "900",
            "ai-schema-map": "true",
            "accept-validated-ai-mapping": "true",
        }
    )
    command = build_command(parse_inputs(values))
    assert command[:4] == [sys.executable, "-m", "slidelineage", "audit"]
    assert str(Path(values["train-manifest"])) in command
    assert str(images) in command and str(schema) in command
    assert "--repair" in command and "--ai-schema-map" in command
    assert command[command.index("--max-image-pairs") + 1] == "17"
    assert all("shell=" not in token for token in command)


def test_windows_like_path_remains_one_argument(tmp_path: Path) -> None:
    inputs = parse_inputs(_files(tmp_path))
    windows = PureWindowsPath(r"C:\data set\train.csv")
    changed = inputs.__class__(
        **{**inputs.__dict__, "train_manifest": Path(str(windows))}
    )
    command = build_command(changed)
    assert str(windows) in command


@pytest.mark.parametrize(("fail", "expected"), [("true", 2), ("false", 0)])
def test_end_to_end_outputs_exit_and_summary(
    tmp_path: Path, fail: str, expected: int
) -> None:
    generated = tmp_path / "generated"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_demo.py"),
            "--output",
            str(generated),
            "--force",
        ],
        check=True,
    )
    output = tmp_path / f"artifacts-{fail}"
    github_output = tmp_path / f"github-output-{fail}.txt"
    summary = tmp_path / f"summary-{fail}.md"
    env = os.environ.copy()
    env.update(
        {
            "INPUT_TRAIN_MANIFEST": str(generated / "train_manifest.csv"),
            "INPUT_TEST_MANIFEST": str(generated / "test_manifest.csv"),
            "INPUT_IMAGES_DIR": str(generated / "images"),
            "INPUT_SCHEMA_MAP": str(ROOT / "examples/demo/schema-map.yaml"),
            "INPUT_OUTPUT_DIR": str(output),
            "INPUT_REPAIR": "true",
            "INPUT_FORCE": "true",
            "INPUT_FAIL_ON_VIOLATIONS": fail,
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(summary),
        }
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_action.py")],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected
    assert "Traceback" not in result.stderr
    for name in ("report.json", "report.html", "findings.csv", "repair_proposal.csv"):
        assert (output / name).is_file()
    report = AuditReport.model_validate_json(
        (output / "report.json").read_text(encoding="utf-8")
    )
    emitted = github_output.read_text(encoding="utf-8")
    assert "status=violations" in emitted and "exit-code=2" in emitted
    assert f"violation-count={report.policy_evaluation.violations}" in emitted
    assert f"review-count={report.policy_evaluation.review_items}" in emitted
    assert '"canonical_records"' not in emitted
    summary_text = summary.read_text(encoding="utf-8")
    assert "does not make clinical claims" in summary_text
    assert "Image similarity is a review candidate" in summary_text
    assert "proposal requiring researcher review" in summary_text


def test_invalid_configuration_is_concise_and_writes_no_outputs(tmp_path: Path) -> None:
    github_output = tmp_path / "outputs"
    env = os.environ | {
        "INPUT_TRAIN_MANIFEST": "",
        "INPUT_TEST_MANIFEST": "missing.csv",
        "GITHUB_OUTPUT": str(github_output),
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_action.py")],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "must not be blank" in result.stderr
    assert "Traceback" not in result.stderr
    assert not github_output.exists()


def test_missing_summary_environment_is_tolerated(tmp_path: Path) -> None:
    values = _files(tmp_path)
    values["output-dir"] = str(tmp_path / "out")
    input_file = tmp_path / "inputs.json"
    input_file.write_text(json.dumps(values), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_action.py"),
            "--input-json",
            str(input_file),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode in (0, 2)
    assert "Traceback" not in result.stderr
