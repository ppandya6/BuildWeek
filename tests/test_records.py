"""Tests for canonical record construction."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    DuplicateSourceRecordIdError,
    MalformedTcgaIdentifierError,
    MissingSourceRecordIdError,
)
from slidelineage.ingest import load_manifest
from slidelineage.models import (
    CanonicalRecordPair,
    IdentifierProvenance,
    IdentifierStatus,
    Partition,
    RecordIdMethod,
)
from slidelineage.records import construct_manifest_records, construct_record_pair
from slidelineage.schema_mapping import (
    ExplicitSchemaMap,
    ManifestSchemaMappings,
    map_manifest_schema,
)


def _csv(tmp_path: Path, name: str, headers: list[str], rows: list[list[str]]) -> Path:
    path = tmp_path / name
    path.write_text(
        ",".join(headers) + "\n" + "\n".join(",".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _config(tmp_path: Path) -> AuditConfig:
    train = tmp_path / "train_cfg.csv"
    test = tmp_path / "test_cfg.csv"
    train.write_text("image_path\na.svs\n", encoding="utf-8")
    test.write_text("image_path\nb.svs\n", encoding="utf-8")
    return AuditConfig(
        train_manifest=train, test_manifest=test, output_dir=tmp_path / "out"
    )


def _records(
    tmp_path: Path,
    headers: list[str],
    rows: list[list[str]],
    explicit: ExplicitSchemaMap,
):
    manifest = load_manifest(
        _csv(tmp_path, "m.csv", headers, rows), Partition.train, "train_manifest"
    )
    mapping = map_manifest_schema(manifest, _config(tmp_path), explicit)
    return construct_manifest_records(manifest, mapping)


def test_direct_record_construction_preserves_values_and_partition(
    tmp_path: Path,
) -> None:
    result = _records(
        tmp_path,
        ["image", "patient", "sample", "slide", "center", "label", "record_uuid"],
        [
            [
                "Slides/A.SVS",
                " Patient A ",
                " Sample 1 ",
                " Slide 1 ",
                " Site 1 ",
                "Tumor",
                "RID-1",
            ]
        ],
        ExplicitSchemaMap(
            image_path="image",
            patient_id="patient",
            specimen_id="sample",
            slide_id="slide",
            institution_id="center",
            class_label="label",
            source_record_id="record_uuid",
        ),
    )
    record = result.records[0]
    assert record.image_path == "Slides/A.SVS"
    assert record.label == "Tumor"
    assert record.patient_id == "patient a"
    assert record.specimen_id == "sample 1"
    assert record.assigned_partition is Partition.train
    assert record.record_id.startswith("rec_src_train_manifest_")
    assert record.record_id_method is RecordIdMethod.source_column


def test_explicit_source_id_missing_and_duplicate_rejected(tmp_path: Path) -> None:
    with pytest.raises(MissingSourceRecordIdError):
        _records(
            tmp_path,
            ["image", "record_uuid"],
            [["a.svs", ""]],
            ExplicitSchemaMap(image_path="image", source_record_id="record_uuid"),
        )
    with pytest.raises(DuplicateSourceRecordIdError):
        _records(
            tmp_path,
            ["image", "record_uuid"],
            [["a.svs", "RID"], ["b.svs", " rid "]],
            ExplicitSchemaMap(image_path="image", source_record_id="record_uuid"),
        )


def test_same_source_id_across_train_test_constructible(tmp_path: Path) -> None:
    train = load_manifest(
        _csv(tmp_path, "tr.csv", ["image", "record_uuid"], [["a.svs", "RID"]]),
        Partition.train,
        "train_manifest",
    )
    test = load_manifest(
        _csv(tmp_path, "te.csv", ["image", "record_uuid"], [["b.svs", "RID"]]),
        Partition.test,
        "test_manifest",
    )
    train_mapping = map_manifest_schema(
        train,
        _config(tmp_path),
        ExplicitSchemaMap(image_path="image", source_record_id="record_uuid"),
    )
    test_mapping = map_manifest_schema(
        test,
        _config(tmp_path),
        ExplicitSchemaMap(image_path="image", source_record_id="record_uuid"),
    )
    pair = construct_record_pair(
        type("Pair", (), {"train": train, "test": test})(),  # type: ignore[arg-type]
        ManifestSchemaMappings(train=train_mapping, test=test_mapping),
    )
    assert isinstance(pair, CanonicalRecordPair)
    assert pair.train.records[0].source_record_id == "rid"
    assert pair.test.records[0].source_record_id == "rid"


def test_fingerprint_ids_stable_under_unrelated_reorder_and_duplicate_suffixes(
    tmp_path: Path,
) -> None:
    headers = ["image", "patient"]
    rows = [["a.svs", "P1"], ["dup.svs", "P2"], ["dup.svs", "P2"], ["z.svs", "P3"]]
    explicit = ExplicitSchemaMap(image_path="image", patient_id="patient")
    first = _records(tmp_path, headers, rows, explicit)
    second = _records(tmp_path, headers, [rows[3], rows[0], rows[1], rows[2]], explicit)
    first_ids = {
        r.image_path: r.record_id for r in first.records if r.image_path != "dup.svs"
    }
    second_ids = {
        r.image_path: r.record_id for r in second.records if r.image_path != "dup.svs"
    }
    assert first_ids == second_ids
    dup_records = [r for r in first.records if r.image_path == "dup.svs"]
    assert [r.record_id_method for r in dup_records] == [
        RecordIdMethod.canonical_row_fingerprint_with_collision_suffix,
        RecordIdMethod.canonical_row_fingerprint_with_collision_suffix,
    ]
    assert dup_records[0].record_id.endswith("_dup0001")
    assert dup_records[1].record_id.endswith("_dup0002")
    assert (
        first.records[0].raw_values_digest != first.records[0].normalized_values_digest
    )


def test_tcga_derived_missing_direct_values(tmp_path: Path) -> None:
    result = _records(
        tmp_path,
        ["image", "record_uuid"],
        [["a.svs", "TCGA-02-0001-01A"]],
        ExplicitSchemaMap(image_path="image", source_record_id="record_uuid"),
    )
    record = result.records[0]
    assert record.patient_id == "tcga-02-0001"
    assert record.specimen_id == "tcga-02-0001-01a"
    assert any(
        p.derivation_method == "tcga_derived" and p.status is IdentifierStatus.accepted
        for p in result.identifier_provenance
    )


def test_tcga_direct_equivalent_and_conflicting_values(tmp_path: Path) -> None:
    equivalent = _records(
        tmp_path,
        ["image", "patient", "record_uuid"],
        [["a.svs", "tcga-02-0001", "TCGA-02-0001-01A"]],
        ExplicitSchemaMap(
            image_path="image", patient_id="patient", source_record_id="record_uuid"
        ),
    )
    assert equivalent.conflicts == ()
    conflicted = _records(
        tmp_path,
        ["image", "patient", "record_uuid"],
        [["a.svs", "PATIENT-X", "TCGA-02-0001-01A"]],
        ExplicitSchemaMap(
            image_path="image", patient_id="patient", source_record_id="record_uuid"
        ),
    )
    assert conflicted.records[0].patient_id == "patient-x"
    assert conflicted.conflicts[0].direct_value == "patient-x"
    assert conflicted.conflicts[0].derived_value == "tcga-02-0001"
    assert "clinical" not in conflicted.conflicts[0].message
    assert any(
        p.status is IdentifierStatus.conflicted
        for p in conflicted.identifier_provenance
    )


def test_malformed_tcga_like_mapped_value_and_arbitrary_column_ignored(
    tmp_path: Path,
) -> None:
    with pytest.raises(MalformedTcgaIdentifierError):
        _records(
            tmp_path,
            ["image", "record_uuid"],
            [["a.svs", "TCGA-02-001"]],
            ExplicitSchemaMap(image_path="image", source_record_id="record_uuid"),
        )
    result = _records(
        tmp_path,
        ["image", "note"],
        [["a.svs", "TCGA-02-001"]],
        ExplicitSchemaMap(image_path="image"),
    )
    assert result.records[0].tcga is None


def test_partition_metadata_warnings_and_cli_authority(tmp_path: Path) -> None:
    matching = _records(
        tmp_path,
        ["image", "split"],
        [["a.svs", "training"]],
        ExplicitSchemaMap(image_path="image", partition="split"),
    )
    assert matching.warnings == ()
    conflicting = _records(
        tmp_path,
        ["image", "split"],
        [["a.svs", "test"], ["b.svs", "validation"]],
        ExplicitSchemaMap(image_path="image", partition="split"),
    )
    assert len(conflicting.warnings) == 2
    assert all(
        record.assigned_partition is Partition.train for record in conflicting.records
    )


def test_contracts_frozen_extras_warnings_and_stable_serialization(
    tmp_path: Path,
) -> None:
    result = _records(
        tmp_path, ["image"], [["a.svs"]], ExplicitSchemaMap(image_path="image")
    )
    assert result.model_dump_json() == result.model_dump_json()
    with pytest.raises(ValidationError):
        IdentifierProvenance(
            semantic_field="patient_id",
            value="x",
            derivation_method="direct_manifest_value",
            confidence=1.0,
            status="accepted",
            extra="no",
        )  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        result.warnings = ("x",)  # type: ignore[misc]
    with pytest.raises(ValidationError):
        IdentifierProvenance(
            semantic_field="patient_id",
            value=None,
            derivation_method="unavailable",
            confidence=1.0,
            status="unresolved",
        )
