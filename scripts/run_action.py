#!/usr/bin/env python3
"""Cross-platform entry point for the Slide-of-Life composite GitHub Action."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from slidelineage.models import AuditReport


class ActionInputError(ValueError):
    """A concise, expected action configuration error."""


TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ActionInputError(f"{name} must be a recognized boolean value")


def parse_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise ActionInputError(f"{name} must be an integer") from None
    if parsed < 0:
        raise ActionInputError(f"{name} must be nonnegative")
    return parsed


def parse_float(value: str, name: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise ActionInputError(f"{name} must be a number") from None


@dataclass(frozen=True)
class ActionInputs:
    train_manifest: Path
    test_manifest: Path
    output_dir: Path
    images_dir: Path | None
    schema_map: Path | None
    policy_profile: str
    repair: bool
    force: bool
    group_by_institution: bool
    target_train_fraction: float | None
    max_image_pairs: int
    phash_distance_threshold: int
    dhash_distance_threshold: int
    image_max_pixels: int
    ai_schema_map: bool
    accept_validated_ai_mapping: bool
    ai_model: str
    fail_on_violations: bool


def _value(values: Mapping[str, str], name: str, default: str = "") -> str:
    return values.get(name, default).strip()


def parse_inputs(values: Mapping[str, str]) -> ActionInputs:
    train_text = _value(values, "train-manifest")
    test_text = _value(values, "test-manifest")
    if not train_text:
        raise ActionInputError("train-manifest must not be blank")
    if not test_text:
        raise ActionInputError("test-manifest must not be blank")
    train, test = Path(train_text), Path(test_text)
    if not train.is_file():
        raise ActionInputError(f"train-manifest does not exist: {train}")
    if not test.is_file():
        raise ActionInputError(f"test-manifest does not exist: {test}")

    images_text, schema_text = (
        _value(values, "images-dir"),
        _value(values, "schema-map"),
    )
    images = Path(images_text) if images_text else None
    schema = Path(schema_text) if schema_text else None
    if images is not None and not images.is_dir():
        raise ActionInputError(f"images-dir does not exist: {images}")
    if schema is not None and not schema.is_file():
        raise ActionInputError(f"schema-map does not exist: {schema}")

    output = Path(_value(values, "output-dir", "slide-of-life-artifacts"))
    if output.resolve(strict=False) in {train.resolve(), test.resolve()}:
        raise ActionInputError("output-dir must not equal an input manifest")
    fraction_text = _value(values, "target-train-fraction")
    fraction = (
        parse_float(fraction_text, "target-train-fraction") if fraction_text else None
    )
    if fraction is not None and not 0 < fraction < 1:
        raise ActionInputError(
            "target-train-fraction must be greater than 0 and less than 1"
        )
    ai_enabled = parse_bool(_value(values, "ai-schema-map", "false"), "ai-schema-map")
    ai_accept = parse_bool(
        _value(values, "accept-validated-ai-mapping", "false"),
        "accept-validated-ai-mapping",
    )
    if ai_accept and not ai_enabled:
        raise ActionInputError(
            "accept-validated-ai-mapping requires ai-schema-map to be enabled"
        )
    return ActionInputs(
        train_manifest=train,
        test_manifest=test,
        output_dir=output,
        images_dir=images,
        schema_map=schema,
        policy_profile=_value(
            values, "policy-profile", "patient_independent_pathology_benchmark"
        ),
        repair=parse_bool(_value(values, "repair", "false"), "repair"),
        force=parse_bool(_value(values, "force", "true"), "force"),
        group_by_institution=parse_bool(
            _value(values, "group-by-institution", "false"), "group-by-institution"
        ),
        target_train_fraction=fraction,
        max_image_pairs=parse_int(
            _value(values, "max-image-pairs", "100000"), "max-image-pairs"
        ),
        phash_distance_threshold=parse_int(
            _value(values, "phash-distance-threshold", "8"), "phash-distance-threshold"
        ),
        dhash_distance_threshold=parse_int(
            _value(values, "dhash-distance-threshold", "12"), "dhash-distance-threshold"
        ),
        image_max_pixels=parse_int(
            _value(values, "image-max-pixels", "25000000"), "image-max-pixels"
        ),
        ai_schema_map=ai_enabled,
        accept_validated_ai_mapping=ai_accept,
        ai_model=_value(values, "ai-model", "gpt-5.6"),
        fail_on_violations=parse_bool(
            _value(values, "fail-on-violations", "true"), "fail-on-violations"
        ),
    )


def build_command(inputs: ActionInputs) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "slidelineage",
        "audit",
        "--train",
        str(inputs.train_manifest),
        "--test",
        str(inputs.test_manifest),
        "--output",
        str(inputs.output_dir),
        "--policy-profile",
        inputs.policy_profile,
        "--max-image-pairs",
        str(inputs.max_image_pairs),
        "--phash-distance-threshold",
        str(inputs.phash_distance_threshold),
        "--dhash-distance-threshold",
        str(inputs.dhash_distance_threshold),
        "--image-max-pixels",
        str(inputs.image_max_pixels),
        "--ai-model",
        inputs.ai_model,
    ]
    if inputs.images_dir is not None:
        command.extend(("--images", str(inputs.images_dir)))
    if inputs.schema_map is not None:
        command.extend(("--schema-map", str(inputs.schema_map)))
    if inputs.repair:
        command.append("--repair")
    if inputs.force:
        command.append("--force")
    if inputs.group_by_institution:
        command.append("--group-by-institution")
    if inputs.target_train_fraction is not None:
        command.extend(("--target-train-fraction", str(inputs.target_train_fraction)))
    if inputs.ai_schema_map:
        command.append("--ai-schema-map")
    if inputs.accept_validated_ai_mapping:
        command.append("--accept-validated-ai-mapping")
    return command


def _write_outputs(path: Path, outputs: Mapping[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for name, value in outputs.items():
            if "\n" in value or "\r" in value:
                raise ActionInputError(f"unsafe multiline action output: {name}")
            handle.write(f"{name}={value}\n")


def _artifact_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def _summary(
    inputs: ActionInputs, report: AuditReport, outputs: Mapping[str, str]
) -> str:
    def safe(value: object) -> str:
        return html.escape(str(value), quote=True).replace("`", "&#96;")

    artifacts = [
        outputs["report-json"],
        outputs["report-html"],
        outputs["findings-csv"],
    ]
    if outputs["repair-proposal-csv"]:
        artifacts.append(outputs["repair-proposal-csv"])
    lines = [
        "## Slide-of-Life audit",
        f"- **Status:** {safe(outputs['status'])}",
        f"- **Train manifest:** `{safe(inputs.train_manifest)}`",
        f"- **Test manifest:** `{safe(inputs.test_manifest)}`",
        f"- **Policy profile:** `{safe(inputs.policy_profile)}`",
        f"- **Total findings:** {len(report.evaluated_findings)}",
        f"- **Policy violations:** {report.policy_evaluation.violations}",
        f"- **Review items:** {report.policy_evaluation.review_items}",
        "- **AI schema assistance:** "
        + ("enabled" if inputs.ai_schema_map else "disabled"),
        "- **Repair proposal:** "
        + ("generated" if outputs["repair-proposal-csv"] else "not generated"),
        "- **Artifacts:** " + ", ".join(f"`{safe(item)}`" for item in artifacts),
        "",
        "> Scope: this audit evaluates dataset partition provenance and overlap; "
        "it does not make clinical claims or prove a dataset is contamination-free.",
        "> Image similarity is a review candidate and does not establish lineage "
        "or identity.",
        "> Any repair is a proposal requiring researcher review and is never "
        "applied automatically.",
        "",
    ]
    return "\n".join(lines)


def process_result(inputs: ActionInputs, cli_exit: int, env: Mapping[str, str]) -> int:
    if cli_exit == 1:
        return 1
    if cli_exit not in (0, 2):
        print(
            f"Slide-of-Life action failed: unexpected CLI exit code {cli_exit}",
            file=sys.stderr,
        )
        return 1
    report_path = inputs.output_dir / "report.json"
    expected = [
        report_path,
        inputs.output_dir / "report.html",
        inputs.output_dir / "findings.csv",
    ]
    if not all(path.is_file() for path in expected):
        print(
            "Slide-of-Life action failed: expected audit artifacts are missing",
            file=sys.stderr,
        )
        return 1
    try:
        report = AuditReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError, ValueError) as exc:
        print(
            f"Slide-of-Life action failed: invalid report.json: {exc}", file=sys.stderr
        )
        return 1
    repair_path = inputs.output_dir / "repair_proposal.csv"
    outputs = {
        "status": "violations" if cli_exit == 2 else "passed",
        "exit-code": str(cli_exit),
        "report-json": _artifact_path(report_path),
        "report-html": _artifact_path(inputs.output_dir / "report.html"),
        "findings-csv": _artifact_path(inputs.output_dir / "findings.csv"),
        "repair-proposal-csv": _artifact_path(repair_path)
        if repair_path.is_file()
        else "",
        "violation-count": str(report.policy_evaluation.violations),
        "review-count": str(report.policy_evaluation.review_items),
    }
    output_file = env.get("GITHUB_OUTPUT")
    if output_file:
        _write_outputs(Path(output_file), outputs)
    summary_file = env.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with Path(summary_file).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_summary(inputs, report, outputs))
    return 2 if cli_exit == 2 and inputs.fail_on_violations else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-json",
        type=Path,
        help="JSON object of action inputs; defaults to INPUT_* environment variables",
    )
    return parser


def _environment_inputs(env: Mapping[str, str]) -> dict[str, str]:
    return {
        key[6:].lower().replace("_", "-"): value
        for key, value in env.items()
        if key.startswith("INPUT_")
    }


def main(
    argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None
) -> int:
    args = _parser().parse_args(argv)
    environment = os.environ if env is None else env
    try:
        values = (
            json.loads(args.input_json.read_text(encoding="utf-8"))
            if args.input_json
            else _environment_inputs(environment)
        )
        if not isinstance(values, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in values.items()
        ):
            raise ActionInputError("action inputs must be a string-to-string object")
        inputs = parse_inputs(values)
        completed = subprocess.run(build_command(inputs), check=False)
        return process_result(inputs, completed.returncode, environment)
    except (ActionInputError, OSError, json.JSONDecodeError) as exc:
        print(f"Slide-of-Life action failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
