#!/usr/bin/env python3
"""Generate the deterministic, entirely synthetic Slide-of-Life demonstration."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

DEFAULT_OUTPUT = Path("examples/demo/generated")
HEADERS = (
    "record_uuid",
    "image_name",
    "subject",
    "specimen",
    "slide",
    "source_center",
    "synthetic_group",
)
KNOWN_MANIFESTS = ("train_manifest.csv", "test_manifest.csv")
KNOWN_IMAGES = (
    "train_patient.png",
    "test_patient.png",
    "train_specimen.png",
    "test_specimen.png",
    "train_slide.png",
    "byte_train.png",
    "byte_test.png",
    "pixel_train.png",
    "pixel_test.bmp",
    "similar_train.png",
    "similar_test.png",
)

TRAIN_ROWS = (
    (
        "TRAIN-001",
        "train_patient.png",
        "PATIENT-001",
        "SP-101",
        "SL-101",
        "CENTER-SHARED",
        "class_alpha",
    ),
    (
        "TRAIN-002",
        "train_specimen.png",
        "PATIENT-102",
        "SPECIMEN-001",
        "SL-102",
        "CENTER-TRAIN-A",
        "class_beta",
    ),
    (
        "TRAIN-003",
        "train_slide.png",
        "PATIENT-103",
        "SP-103",
        "SLIDE-001",
        "CENTER-TRAIN-B",
        "class_gamma",
    ),
    (
        "TRAIN-004",
        "byte_train.png",
        "PATIENT-104",
        "SP-104",
        "SL-104",
        "CENTER-TRAIN-C",
        "class_alpha",
    ),
    (
        "TRAIN-005",
        "pixel_train.png",
        "PATIENT-105",
        "SP-105",
        "SL-105",
        "CENTER-TRAIN-D",
        "class_beta",
    ),
    (
        "TRAIN-006",
        "similar_train.png",
        "PATIENT-106",
        "SP-106",
        "SL-106",
        "CENTER-TRAIN-E",
        "class_gamma",
    ),
)
TEST_ROWS = (
    (
        "TEST-001",
        "test_patient.png",
        "PATIENT-001",
        "SP-201",
        "SL-201",
        "CENTER-TEST-A",
        "class_beta",
    ),
    (
        "TEST-002",
        "test_specimen.png",
        "PATIENT-202",
        "SPECIMEN-001",
        "SL-202",
        "CENTER-SHARED",
        "class_gamma",
    ),
    (
        "TEST-003",
        "missing_test.png",
        "PATIENT-203",
        "SP-203",
        "SLIDE-001",
        "CENTER-TEST-C",
        "class_alpha",
    ),
    (
        "TEST-004",
        "byte_test.png",
        "PATIENT-204",
        "SP-204",
        "SL-204",
        "CENTER-TEST-D",
        "class_beta",
    ),
    (
        "TEST-005",
        "pixel_test.bmp",
        "PATIENT-205",
        "SP-205",
        "SL-205",
        "CENTER-TEST-E",
        "class_gamma",
    ),
    (
        "TEST-006",
        "similar_test.png",
        "PATIENT-206",
        "SP-206",
        "SL-206",
        "CENTER-TEST-F",
        "class_alpha",
    ),
)


class DemoGenerationError(Exception):
    """An expected, user-facing demo generation failure."""


def _pattern(kind: int) -> Image.Image:
    image = Image.new("RGB", (64, 64))
    pixels = image.load()
    for y in range(64):
        for x in range(64):
            value = (x * (17 + kind * 2) + y * (31 + kind * 4) + kind * 53) % 256
            pixels[x, y] = (value, (value * 3 + kind * 29) % 256, (255 - value))
    draw = ImageDraw.Draw(image)
    draw.ellipse((10 + kind, 12, 37 + kind, 39), outline=(255, 240, 30), width=3)
    return image


def _similar_image(variant: bool = False) -> Image.Image:
    image = Image.new("RGB", (64, 64), (22, 35, 48))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 55, 55), fill=(62, 130, 190))
    draw.ellipse((18, 16, 47, 45), fill=(230, 180, 35))
    draw.line((7, 56, 56, 7), fill=(245, 245, 245), width=4)
    if variant:
        image.putpixel((2, 2), (23, 35, 48))
    return image


def _write_manifest(path: Path, rows: tuple[tuple[str, ...], ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADERS)
        writer.writerows(rows)


def generate(output: Path, *, force: bool) -> None:
    if output.exists() and not output.is_dir():
        raise DemoGenerationError(f"output path is not a directory: {output}")
    if output.is_dir() and any(output.iterdir()) and not force:
        raise DemoGenerationError(
            f"output directory is not empty: {output}; use --force to replace "
            "known demo files"
        )
    images = output / "images"
    if force:
        for name in KNOWN_MANIFESTS:
            (output / name).unlink(missing_ok=True)
        for name in KNOWN_IMAGES:
            (images / name).unlink(missing_ok=True)
    try:
        images.mkdir(parents=True, exist_ok=True)
        _write_manifest(output / "train_manifest.csv", TRAIN_ROWS)
        _write_manifest(output / "test_manifest.csv", TEST_ROWS)
        for index, name in enumerate(KNOWN_IMAGES[:5]):
            _pattern(index + 1).save(images / name, format="PNG")
        byte_image = _pattern(7)
        byte_image.save(images / "byte_train.png", format="PNG")
        shutil.copyfile(images / "byte_train.png", images / "byte_test.png")
        pixel_image = _pattern(9)
        pixel_image.save(images / "pixel_train.png", format="PNG")
        pixel_image.save(images / "pixel_test.bmp", format="BMP")
        _similar_image().save(images / "similar_train.png", format="PNG")
        _similar_image(variant=True).save(images / "similar_test.png", format="PNG")
    except (OSError, ValueError) as exc:
        raise DemoGenerationError(f"could not write demo files: {exc}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force", action="store_true", help="replace only known generated demo files"
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        generate(args.output, force=args.force)
    except DemoGenerationError as exc:
        print(f"Demo generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Generated train manifest: {args.output / 'train_manifest.csv'}")
    print(f"Generated test manifest: {args.output / 'test_manifest.csv'}")
    print(f"Generated synthetic images: {args.output / 'images'}")
    print(
        "Run: slide-of-life audit --train "
        + str(args.output / "train_manifest.csv")
        + " --test "
        + str(args.output / "test_manifest.csv")
        + " --images "
        + str(args.output / "images")
        + " --schema-map examples/demo/schema-map.yaml"
        + " --output artifacts/demo-audit --repair --force"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
