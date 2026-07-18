"""Deterministic local image path auditing and fingerprinting."""

from __future__ import annotations

import hashlib
from pathlib import Path, PureWindowsPath
from typing import Final

import imagehash
from PIL import Image, ImageOps, UnidentifiedImageError

from slidelineage.config import AuditConfig
from slidelineage.models import (
    CanonicalRecord,
    CanonicalRecordPair,
    ImageFingerprint,
    ImageFingerprintCollection,
    ImageReadStatus,
    Partition,
)

IMAGE_FINGERPRINT_DETECTOR_VERSION: Final[str] = "task6-image-fingerprints-v1"
_SUPPORTED_FORMATS: Final[frozenset[str]] = frozenset(
    {"PNG", "JPEG", "TIFF", "BMP", "WEBP"}
)
_CHUNK_SIZE: Final[int] = 1024 * 1024


def fingerprint_record_images(
    pair: CanonicalRecordPair, config: AuditConfig
) -> ImageFingerprintCollection:
    """Fingerprint records with mapped image paths using a local image root."""

    records = sorted(pair.train.records + pair.test.records, key=_record_sort_key)
    warnings: list[str] = []
    fps: list[ImageFingerprint] = []
    if config.images_dir is None:
        if any(r.image_path for r in records):
            warnings.append("images_dir is required to audit mapped image paths")
        return _collection(tuple(), warnings, 0, False)
    root = config.images_dir.resolve()
    for record in records:
        if record.image_path is None:
            continue
        fps.append(_fingerprint_one(record, root, config))
    resolved = [f for f in fps if f.status is ImageReadStatus.resolved]
    train = sum(1 for f in resolved if f.assigned_partition is Partition.train)
    test = sum(1 for f in resolved if f.assigned_partition is Partition.test)
    pair_count = train * test
    exceeded = pair_count > config.max_image_pairs
    if exceeded:
        warnings.append(
            "image pair comparison limit exceeded: "
            f"requested {pair_count}, maximum {config.max_image_pairs}"
        )
    return _collection(tuple(fps), warnings, pair_count, exceeded)


def _fingerprint_one(
    record: CanonicalRecord, root: Path, config: AuditConfig
) -> ImageFingerprint:
    source = record.image_path or ""
    resolved, status, code, message = _resolve(source, root)
    if status is not ImageReadStatus.resolved or resolved is None:
        return _failed(record, source, resolved, status, code, message)
    try:
        byte_sha = _sha256_file(resolved)
        Image.MAX_IMAGE_PIXELS = config.image_max_pixels
        with Image.open(resolved) as img:
            fmt = (img.format or "").upper()
            if fmt not in _SUPPORTED_FORMATS:
                return _failed(
                    record,
                    source,
                    resolved,
                    ImageReadStatus.unsupported_format,
                    "unsupported_format",
                    f"unsupported image format: {fmt or 'unknown'}",
                )
            img.load()
            safe = ImageOps.exif_transpose(img)
            if safe.width * safe.height > config.image_max_pixels:
                return _failed(
                    record,
                    source,
                    resolved,
                    ImageReadStatus.unsafe_image,
                    "image_too_large",
                    (
                        "image has "
                        f"{safe.width * safe.height} pixels; maximum is "
                        f"{config.image_max_pixels}"
                    ),
                )
            canonical = safe.convert("RGB")
            pixel_sha = _pixel_sha(canonical)
            phash = f"{int(str(imagehash.phash(canonical)), 16):016x}"
            dhash = f"{int(str(imagehash.dhash(canonical)), 16):016x}"
            return ImageFingerprint(
                record_id=record.record_id,
                assigned_partition=record.assigned_partition,
                source_manifest_id=record.source_manifest_id,
                source_row_number=record.source_row_number,
                source_image_path=source,
                resolved_path=str(resolved),
                status=ImageReadStatus.resolved,
                byte_sha256=byte_sha,
                canonical_pixel_sha256=pixel_sha,
                width=canonical.width,
                height=canonical.height,
                image_format=fmt,
                phash=phash,
                dhash=dhash,
                detector_version=IMAGE_FINGERPRINT_DETECTOR_VERSION,
            )
    except Image.DecompressionBombError as exc:
        return _failed(
            record,
            source,
            resolved,
            ImageReadStatus.unsafe_image,
            "decompression_bomb",
            str(exc),
        )
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        return _failed(
            record, source, resolved, ImageReadStatus.unreadable, "unreadable", str(exc)
        )


def _resolve(
    source: str, root: Path
) -> tuple[Path | None, ImageReadStatus, str | None, str | None]:
    normalized = source.replace("\\", "/")
    candidate = Path(normalized)
    if PureWindowsPath(source).is_absolute() or candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / normalized).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return (
            resolved,
            ImageReadStatus.outside_root,
            "outside_root",
            "image path resolves outside images_dir",
        )
    if not resolved.is_file():
        return (
            resolved,
            ImageReadStatus.missing,
            "missing",
            "referenced image file does not exist",
        )
    return resolved, ImageReadStatus.resolved, None, None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pixel_sha(image: Image.Image) -> str:
    digest = hashlib.sha256()
    digest.update(b"mode=RGB\n")
    digest.update(f"width={image.width}\nheight={image.height}\n".encode())
    digest.update(image.tobytes())
    return digest.hexdigest()


def _failed(
    record: CanonicalRecord,
    source: str,
    resolved: Path | None,
    status: ImageReadStatus,
    code: str | None,
    message: str | None,
) -> ImageFingerprint:
    return ImageFingerprint(
        record_id=record.record_id,
        assigned_partition=record.assigned_partition,
        source_manifest_id=record.source_manifest_id,
        source_row_number=record.source_row_number,
        source_image_path=source,
        resolved_path=str(resolved) if resolved is not None else None,
        status=status,
        error_code=code,
        error_message=message,
        detector_version=IMAGE_FINGERPRINT_DETECTOR_VERSION,
    )


def _collection(
    fingerprints: tuple[ImageFingerprint, ...],
    warnings: list[str],
    pair_count: int,
    exceeded: bool,
) -> ImageFingerprintCollection:
    return ImageFingerprintCollection(
        fingerprints=fingerprints,
        resolved_count=sum(
            1 for f in fingerprints if f.status is ImageReadStatus.resolved
        ),
        missing_count=sum(
            1 for f in fingerprints if f.status is ImageReadStatus.missing
        ),
        unreadable_count=sum(
            1
            for f in fingerprints
            if f.status
            in {ImageReadStatus.unreadable, ImageReadStatus.unsupported_format}
        ),
        unsafe_count=sum(
            1
            for f in fingerprints
            if f.status in {ImageReadStatus.unsafe_image, ImageReadStatus.outside_root}
        ),
        pair_count_considered=pair_count,
        pair_limit_exceeded=exceeded,
        warnings=tuple(sorted(warnings)),
    )


def _record_sort_key(record: CanonicalRecord) -> tuple[int, int, str]:
    return (
        0 if record.assigned_partition is Partition.train else 1,
        record.source_row_number,
        record.record_id,
    )
