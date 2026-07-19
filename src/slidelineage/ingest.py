"""Deterministic CSV manifest ingestion boundary for Slide-of-Life."""

import codecs
import csv
import hashlib
from pathlib import Path
from typing import Final

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    DuplicateHeaderError,
    EmptyManifestError,
    ManifestCsvError,
    ManifestEncodingError,
    ManifestNotFoundError,
    ManifestUnreadableError,
    NormalizedHeaderCollisionError,
    SameManifestFileError,
)
from slidelineage.models import (
    LoadedManifest,
    LoadedManifestPair,
    Partition,
    RawManifestRow,
    SourceManifest,
)
from slidelineage.normalization import normalize_header, normalize_missing_value

_CHUNK_SIZE: Final[int] = 1024 * 1024
_TRAIN_MANIFEST_ID: Final[str] = "train_manifest"
_TEST_MANIFEST_ID: Final[str] = "test_manifest"


def compute_file_sha256(path: Path) -> str:
    """Stream source bytes and return lowercase SHA-256 hex digest."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ManifestUnreadableError(f"manifest is unreadable: {path}") from exc
    return digest.hexdigest()


def load_manifest(path: Path, partition: Partition, manifest_id: str) -> LoadedManifest:
    """Load one CSV manifest with source provenance and conservative normalization."""

    _validate_manifest_path(path)
    sha256 = compute_file_sha256(path)
    source_bytes = _read_source_bytes(path)
    if not source_bytes:
        raise EmptyManifestError(f"manifest is empty: {path}")
    newline_style = _detect_newline_style(source_bytes)
    text, encoding_used = _decode_utf8(path, source_bytes)
    if not text.strip():
        raise EmptyManifestError(f"manifest contains only blank lines: {path}")

    rows = _parse_csv(path, text)
    if not rows:
        raise EmptyManifestError(f"manifest requires a header row: {path}")
    original_headers = tuple(rows[0])
    _validate_original_headers(path, original_headers)
    normalized_headers = _normalize_headers(path, original_headers)

    loaded_rows: list[RawManifestRow] = []
    warnings: list[str] = []
    for source_row_number, parsed_row in enumerate(rows[1:]):
        row: list[str | None] = list(parsed_row)
        if len(row) > len(original_headers):
            raise ManifestCsvError(
                f"manifest row {source_row_number} has more cells than headers: {path}"
            )
        if len(row) < len(original_headers):
            warnings.append(
                f"source row {source_row_number} has fewer cells than headers; "
                "missing trailing cells were recorded as null"
            )
            row = [*row, *([None] * (len(original_headers) - len(row)))]

        raw_values = dict(zip(original_headers, row, strict=True))
        normalized_header_values = {
            header: normalize_missing_value(value)
            for header, value in zip(normalized_headers, row, strict=True)
        }
        loaded_rows.append(
            RawManifestRow(
                source_manifest_id=manifest_id,
                source_row_number=source_row_number,
                assigned_partition=partition,
                raw_values=raw_values,
                normalized_header_values=normalized_header_values,
            )
        )

    if not loaded_rows:
        raise EmptyManifestError(f"manifest contains no data rows: {path}")

    source = SourceManifest(
        manifest_id=manifest_id,
        path=path,
        assigned_partition=partition,
        sha256=sha256,
        row_count=len(loaded_rows),
        columns=normalized_headers,
    )
    return LoadedManifest(
        source=source,
        original_headers=original_headers,
        normalized_headers=normalized_headers,
        rows=tuple(loaded_rows),
        encoding_used=encoding_used,
        newline_style=newline_style,
        warnings=tuple(warnings),
    )


def load_manifest_pair(config: AuditConfig) -> LoadedManifestPair:
    """Load train and test manifests, rejecting same-file aliases."""

    train_path = config.train_manifest
    test_path = config.test_manifest
    _validate_manifest_path(train_path)
    _validate_manifest_path(test_path)
    if _same_manifest_file(train_path, test_path):
        raise SameManifestFileError(
            "train and test manifests resolve to the same file: "
            f"{train_path} and {test_path}"
        )
    return LoadedManifestPair(
        train=load_manifest(train_path, Partition.train, _TRAIN_MANIFEST_ID),
        test=load_manifest(test_path, Partition.test, _TEST_MANIFEST_ID),
    )


def _validate_manifest_path(path: Path) -> None:
    if not path.exists():
        raise ManifestNotFoundError(f"manifest does not exist: {path}")
    if not path.is_file():
        raise ManifestUnreadableError(f"manifest is not a regular file: {path}")


def _read_source_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ManifestUnreadableError(f"manifest is unreadable: {path}") from exc


def _decode_utf8(path: Path, source_bytes: bytes) -> tuple[str, str]:
    encoding_used = "utf-8-sig" if source_bytes.startswith(codecs.BOM_UTF8) else "utf-8"
    bytes_to_decode = (
        source_bytes[len(codecs.BOM_UTF8) :]
        if encoding_used == "utf-8-sig"
        else source_bytes
    )
    try:
        return bytes_to_decode.decode("utf-8", errors="strict"), encoding_used
    except UnicodeDecodeError as exc:
        raise ManifestEncodingError(f"manifest is not valid UTF-8: {path}") from exc


def _parse_csv(path: Path, text: str) -> list[list[str]]:
    try:
        return list(csv.reader(text.splitlines(keepends=True), strict=True))
    except csv.Error as exc:
        raise ManifestCsvError(
            f"manifest CSV could not be parsed: {path}: {exc}"
        ) from exc


def _validate_original_headers(path: Path, headers: tuple[str, ...]) -> None:
    if not headers or all(header == "" for header in headers):
        raise EmptyManifestError(f"manifest has no headers: {path}")
    for header in headers:
        if not header.strip():
            raise DuplicateHeaderError(f"manifest contains a blank header: {path}")
    seen: set[str] = set()
    duplicates: list[str] = []
    for header in headers:
        if header in seen:
            duplicates.append(header)
        seen.add(header)
    if duplicates:
        conflicting = ", ".join(repr(header) for header in duplicates)
        raise DuplicateHeaderError(
            f"manifest contains duplicate original headers {conflicting}: {path}"
        )


def _normalize_headers(path: Path, headers: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(normalize_header(header) for header in headers)
    by_normalized: dict[str, str] = {}
    for original, canonical in zip(headers, normalized, strict=True):
        previous = by_normalized.get(canonical)
        if previous is not None and previous != original:
            raise NormalizedHeaderCollisionError(
                "manifest headers normalize to the same value "
                f"{canonical!r}: {previous!r} and {original!r}: {path}"
            )
        by_normalized[canonical] = original
    return normalized


def _detect_newline_style(source_bytes: bytes) -> str:
    crlf = source_bytes.count(b"\r\n")
    without_crlf = source_bytes.replace(b"\r\n", b"")
    lf = without_crlf.count(b"\n")
    cr = without_crlf.count(b"\r")
    styles = sum(count > 0 for count in (crlf, lf, cr))
    if styles == 0:
        return "none"
    if styles > 1:
        return "mixed"
    if crlf:
        return "crlf"
    if lf:
        return "lf"
    return "cr"


def _same_manifest_file(left: Path, right: Path) -> bool:
    try:
        if left.samefile(right):
            return True
    except OSError:
        pass
    try:
        return left.resolve(strict=True) == right.resolve(strict=True)
    except OSError:
        return left.absolute() == right.absolute()
