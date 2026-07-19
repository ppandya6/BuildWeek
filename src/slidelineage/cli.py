"""Command-line interface for Slide-of-Life."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from slidelineage import __version__
from slidelineage.audit import run_audit
from slidelineage.config import AuditConfig
from slidelineage.errors import SlideLineageError
from slidelineage.policy import DEFAULT_POLICY_PROFILE

APP_NAME = "Slide-of-Life"
APP_PURPOSE = (
    "Local deterministic-first tooling for auditing computational-pathology "
    "train/test partition lineage."
)
DOCS_HINT = (
    "See docs/product-spec.md and docs/scientific-method.md for milestone scope."
)

app = typer.Typer(
    name="slide-of-life",
    help=(
        f"{APP_NAME}: {APP_PURPOSE} Default policy profile: "
        f"{DEFAULT_POLICY_PROFILE}. Image similarity is a review candidate, not "
        "lineage proof. Repair outputs require researcher review."
    ),
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{APP_NAME} {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the Slide-of-Life version and exit.",
        ),
    ] = False,
) -> None:
    """Run deterministic Slide-of-Life commands."""
    _ = version


@app.command()
def audit(
    train: Annotated[Path, typer.Option("--train", help="Train manifest CSV path.")],
    test: Annotated[Path, typer.Option("--test", help="Test manifest CSV path.")],
    output: Annotated[Path, typer.Option("--output", help="Audit output directory.")],
    images: Annotated[Path | None, typer.Option("--images")] = None,
    schema_map: Annotated[Path | None, typer.Option("--schema-map")] = None,
    policy_profile: Annotated[
        str, typer.Option("--policy-profile")
    ] = DEFAULT_POLICY_PROFILE,
    repair: Annotated[bool, typer.Option("--repair")] = False,
    group_by_institution: Annotated[
        bool, typer.Option("--group-by-institution")
    ] = False,
    target_train_fraction: Annotated[
        float | None, typer.Option("--target-train-fraction")
    ] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
    patient_column: Annotated[str | None, typer.Option("--patient-column")] = None,
    specimen_column: Annotated[str | None, typer.Option("--specimen-column")] = None,
    slide_column: Annotated[str | None, typer.Option("--slide-column")] = None,
    image_column: Annotated[str | None, typer.Option("--image-column")] = None,
    institution_column: Annotated[
        str | None, typer.Option("--institution-column")
    ] = None,
    label_column: Annotated[str | None, typer.Option("--label-column")] = None,
    record_id_column: Annotated[str | None, typer.Option("--record-id-column")] = None,
    max_image_pairs: Annotated[int, typer.Option("--max-image-pairs")] = 100_000,
    phash_distance_threshold: Annotated[
        int, typer.Option("--phash-distance-threshold")
    ] = 8,
    dhash_distance_threshold: Annotated[
        int, typer.Option("--dhash-distance-threshold")
    ] = 12,
    image_max_pixels: Annotated[int, typer.Option("--image-max-pixels")] = 25_000_000,
    ai_schema_map: Annotated[
        bool,
        typer.Option(
            "--ai-schema-map",
            help=(
                "Optional AI mapping: sends headers and aggregate statistics, never "
                "raw rows or images; proposals are deterministically validated but "
                "not applied without acceptance."
            ),
        ),
    ] = False,
    accept_validated_ai_mapping: Annotated[
        bool,
        typer.Option(
            "--accept-validated-ai-mapping",
            help="Explicitly apply only deterministically validated AI mappings.",
        ),
    ] = False,
    ai_model: Annotated[str, typer.Option("--ai-model")] = "gpt-5.6",
) -> None:
    """Run a local deterministic audit and write report artifacts."""

    try:
        config = AuditConfig(
            train_manifest=train,
            test_manifest=test,
            output_dir=output,
            images_dir=images,
            schema_map_path=schema_map,
            policy_profile=policy_profile,
            repair=repair,
            group_by_institution=group_by_institution,
            target_train_fraction=target_train_fraction,
            force=force,
            patient_column=patient_column,
            specimen_column=specimen_column,
            slide_column=slide_column,
            image_column=image_column,
            institution_column=institution_column,
            label_column=label_column,
            record_id_column=record_id_column,
            max_image_pairs=max_image_pairs,
            phash_distance_threshold=phash_distance_threshold,
            dhash_distance_threshold=dhash_distance_threshold,
            image_max_pixels=image_max_pixels,
            ai_schema_map=ai_schema_map,
            accept_validated_ai_mapping=accept_validated_ai_mapping,
            ai_model=ai_model,
        )
        result = run_audit(config)
    except (SlideLineageError, ValidationError, ValueError) as exc:
        typer.echo(f"Slide-of-Life audit failed: {exc}", err=True)
        raise typer.Exit(1) from None
    typer.echo(result.terminal_summary)
    raise typer.Exit(result.exit_code)


def compatibility_app() -> None:
    """Run the deprecated ``slidelineage`` console-command alias."""

    typer.echo(
        "`slidelineage` is retained for compatibility. "
        "Use `slide-of-life` for new workflows.",
        err=True,
    )
    app()
