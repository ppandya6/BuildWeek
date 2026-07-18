import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

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
from slidelineage.ingest import compute_file_sha256, load_manifest, load_manifest_pair
from slidelineage.models import LoadedManifest, Partition, RawManifestRow


def write_bytes(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def write_text(path: Path, text: str, newline: str = "") -> Path:
    path.write_text(text, encoding="utf-8", newline=newline)
    return path


def config(train: Path, test: Path, out: Path) -> AuditConfig:
    return AuditConfig(train_manifest=train, test_manifest=test, output_dir=out)


def test_compute_file_sha256_known_bytes(tmp_path: Path) -> None:
    path = write_bytes(tmp_path / "manifest.csv", b"Patient ID\nPAT-001\n")
    assert (
        compute_file_sha256(path)
        == hashlib.sha256(b"Patient ID\nPAT-001\n").hexdigest()
    )


def test_file_validation_errors(tmp_path: Path) -> None:
    with pytest.raises(ManifestNotFoundError):
        load_manifest(tmp_path / "missing.csv", Partition.train, "train_manifest")
    with pytest.raises(ManifestUnreadableError):
        load_manifest(tmp_path, Partition.train, "train_manifest")


def test_empty_and_blank_only_files_rejected(tmp_path: Path) -> None:
    with pytest.raises(EmptyManifestError):
        load_manifest(write_bytes(tmp_path / "zero.csv", b""), Partition.train, "m")
    with pytest.raises(EmptyManifestError):
        load_manifest(
            write_text(tmp_path / "blank.csv", "\n  \n"), Partition.train, "m"
        )


def test_strict_utf8_and_bom_and_malformed_utf8(tmp_path: Path) -> None:
    strict = load_manifest(
        write_text(tmp_path / "utf8.csv", "id\nα\n"), Partition.train, "m"
    )
    assert strict.encoding_used == "utf-8"
    bom_path = write_bytes(tmp_path / "bom.csv", b"\xef\xbb\xbfid\n1\n")
    bom = load_manifest(bom_path, Partition.train, "m")
    assert bom.encoding_used == "utf-8-sig"
    assert bom.original_headers == ("id",)
    with pytest.raises(ManifestEncodingError):
        load_manifest(
            write_bytes(tmp_path / "bad.csv", b"id\n\xff\n"), Partition.train, "m"
        )


def test_newline_detection_lf_and_crlf(tmp_path: Path) -> None:
    lf = load_manifest(
        write_bytes(tmp_path / "lf.csv", b"id\n1\n"), Partition.train, "m"
    )
    crlf = load_manifest(
        write_bytes(tmp_path / "crlf.csv", b"id\r\n1\r\n"), Partition.train, "m"
    )
    assert lf.newline_style == "lf"
    assert crlf.newline_style == "crlf"


def test_valid_csv_preserves_headers_rows_quotes_newlines_and_serialization(
    tmp_path: Path,
) -> None:
    content = (
        "Patient ID,Label,Note\n"
        '" PAT-001 ",Tumor,"quoted, comma"\n'
        'PAT-002,Normal,"line\nbreak"\n'
    )
    path = write_text(tmp_path / "train.csv", content)
    loaded = load_manifest(path, Partition.train, "train_manifest")
    assert loaded.original_headers == ("Patient ID", "Label", "Note")
    assert loaded.normalized_headers == ("patient_id", "label", "note")
    assert [row.source_row_number for row in loaded.rows] == [0, 1]
    assert loaded.rows[0].raw_values["Patient ID"] == " PAT-001 "
    assert loaded.rows[0].normalized_header_values["label"] == "Tumor"
    assert loaded.rows[1].raw_values["Note"] == "line\nbreak"
    assert loaded.source.row_count == len(loaded.rows)
    assert (
        loaded.model_dump_json()
        == load_manifest(path, Partition.train, "train_manifest").model_dump_json()
    )


def test_header_errors(tmp_path: Path) -> None:
    with pytest.raises(DuplicateHeaderError):
        load_manifest(
            write_text(tmp_path / "blank_header.csv", "id, \n1,2\n"),
            Partition.train,
            "m",
        )
    with pytest.raises(DuplicateHeaderError):
        load_manifest(
            write_text(tmp_path / "dup.csv", "id,id\n1,2\n"), Partition.train, "m"
        )
    with pytest.raises(NormalizedHeaderCollisionError):
        load_manifest(
            write_text(tmp_path / "collision.csv", "Patient-ID,Patient ID\n1,2\n"),
            Partition.train,
            "m",
        )


def test_short_rows_warn_and_extra_cells_reject(tmp_path: Path) -> None:
    short = load_manifest(
        write_text(tmp_path / "short.csv", "id,label,note\n1,A\n"), Partition.train, "m"
    )
    assert short.rows[0].raw_values["note"] is None
    assert "source row 0" in short.warnings[0]
    with pytest.raises(ManifestCsvError):
        load_manifest(
            write_text(tmp_path / "extra.csv", "id\n1,2\n"), Partition.train, "m"
        )


def test_empty_after_header_and_malformed_csv(tmp_path: Path) -> None:
    with pytest.raises(EmptyManifestError):
        load_manifest(
            write_text(tmp_path / "header_only.csv", "id\n"), Partition.train, "m"
        )
    with pytest.raises(ManifestCsvError):
        load_manifest(
            write_text(tmp_path / "bad_csv.csv", 'id\n"unterminated\n'),
            Partition.train,
            "m",
        )


def test_pair_assignment_ids_same_path_aliases_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    train = write_text(tmp_path / "train.csv", "id\n1\n")
    test = write_text(tmp_path / "test.csv", "id\n2\n")
    pair = load_manifest_pair(config(train, test, tmp_path / "out"))
    assert pair.train.source.assigned_partition is Partition.train
    assert pair.test.source.assigned_partition is Partition.test
    assert pair.train.source.manifest_id == "train_manifest"
    assert pair.test.source.manifest_id == "test_manifest"
    assert pair.train.source.path == train
    assert (
        pair.model_dump_json()
        == load_manifest_pair(config(train, test, tmp_path / "out")).model_dump_json()
    )
    with pytest.raises(ValueError):
        config(train, train, tmp_path / "out")
    rel = Path("train.csv")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SameManifestFileError):
        load_manifest_pair(config(rel, train.resolve(), tmp_path / "out2"))


def test_symlink_alias_rejected_when_supported(tmp_path: Path) -> None:
    target = write_text(tmp_path / "target.csv", "id\n1\n")
    other = write_text(tmp_path / "other.csv", "id\n2\n")
    link = tmp_path / "link.csv"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported in this environment")
    with pytest.raises(SameManifestFileError):
        load_manifest_pair(config(target, link, tmp_path / "out"))
    assert (
        load_manifest_pair(config(link, other, tmp_path / "out2")).train.source.path
        == link
    )


def test_contract_invariants_and_frozen_models(tmp_path: Path) -> None:
    loaded = load_manifest(
        write_text(tmp_path / "train.csv", "id\n1\n"), Partition.train, "m"
    )
    row = loaded.rows[0]
    assert row.source_manifest_id == loaded.source.manifest_id
    assert row.assigned_partition == loaded.source.assigned_partition
    with pytest.raises(ValidationError):
        RawManifestRow(
            source_manifest_id="m",
            source_row_number=0,
            assigned_partition=Partition.train,
            raw_values={},
            normalized_header_values={},
            extra=True,
        )  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        LoadedManifest(**{**loaded.model_dump(), "rows": ()})
    with pytest.raises(ValidationError):
        row.source_row_number = 99  # type: ignore[misc]
