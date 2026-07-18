"""Tests for deterministic semantic schema mapping."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    DuplicateSemanticAssignmentError,
    InsufficientSchemaCoverageError,
    InvalidSchemaMapError,
    MissingMappedColumnError,
    UnknownSchemaFieldError,
    UnsupportedSchemaMapFormatError,
)
from slidelineage.ingest import load_manifest
from slidelineage.models import LoadedManifestPair, Partition
from slidelineage.schema_mapping import (
    ExplicitSchemaMap,
    ManifestSchemaMappings,
    SemanticField,
    load_schema_map,
    map_manifest_pair,
    map_manifest_schema,
)


def _csv(tmp_path: Path, name: str, headers: list[str], rows: list[list[str]]) -> Path:
    path = tmp_path / name
    path.write_text(
        ",".join(headers) + "\n" + "\n".join(",".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _manifest(tmp_path: Path, headers: list[str], rows: list[list[str]] | None = None):
    if rows is None:
        base = ["img/a.svs", "P1", "S1", "A"]
        rows = [base[: len(headers)], ["img/b.svs", "P2", "S2", "B"][: len(headers)]]
    return load_manifest(_csv(tmp_path, "m.csv", headers, rows), Partition.train, "m")


def _config(tmp_path: Path, **kwargs: object) -> AuditConfig:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    train.write_text("image_path\ntrain.svs\n", encoding="utf-8")
    test.write_text("image_path\ntest.svs\n", encoding="utf-8")
    return AuditConfig(
        train_manifest=train, test_manifest=test, output_dir=tmp_path / "out", **kwargs
    )


@pytest.mark.parametrize("suffix", [".yaml", ".yml"])
def test_load_schema_map_valid_yaml_and_yml(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"map{suffix}"
    path.write_text("patient_id: subject\nimage_path: image_name\n", encoding="utf-8")
    loaded = load_schema_map(path)
    assert loaded.patient_id == "subject"
    assert loaded.image_path == "image_name"


def test_load_schema_map_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"source_record_id": "record_uuid"}), encoding="utf-8")
    assert load_schema_map(path).source_record_id == "record_uuid"


def test_load_schema_map_rejects_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "map.yaml"
    path.write_text("patient_id: [", encoding="utf-8")
    with pytest.raises(InvalidSchemaMapError):
        load_schema_map(path)


def test_load_schema_map_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text('{"patient_id":', encoding="utf-8")
    with pytest.raises(InvalidSchemaMapError):
        load_schema_map(path)


def test_load_schema_map_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "map.toml"
    path.write_text("patient_id='subject'", encoding="utf-8")
    with pytest.raises(UnsupportedSchemaMapFormatError):
        load_schema_map(path)


def test_load_schema_map_rejects_unknown_key(tmp_path: Path) -> None:
    path = tmp_path / "map.yaml"
    path.write_text("patient: subject\n", encoding="utf-8")
    with pytest.raises(UnknownSchemaFieldError):
        load_schema_map(path)


@pytest.mark.parametrize(
    "content", ["patient_id: 7\n", "patient_id: '   '\n", "- patient_id\n"]
)
def test_load_schema_map_rejects_invalid_values_and_top_level(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "map.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(InvalidSchemaMapError):
        load_schema_map(path)


def test_explicit_mapping_exact_and_normalized_lookup(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, ["Image Name", "Subject", "slide"])
    cfg = _config(tmp_path)
    mapping = map_manifest_schema(
        manifest, cfg, ExplicitSchemaMap(image_path="Image Name", patient_id="subject")
    )
    assert mapping.image_path.source_column == "Image Name"
    assert mapping.patient_id.source_column == "Subject"


def test_explicit_mapping_missing_column_and_duplicate_assignment(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path, ["image_path", "subject"])
    cfg = _config(tmp_path)
    with pytest.raises(MissingMappedColumnError):
        map_manifest_schema(manifest, cfg, ExplicitSchemaMap(patient_id="missing"))
    with pytest.raises(DuplicateSemanticAssignmentError):
        map_manifest_schema(
            manifest,
            cfg,
            ExplicitSchemaMap(patient_id="subject", specimen_id="subject"),
        )


def test_direct_flag_precedence_and_mixed_file_mapping(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, ["img", "subject", "override_patient", "slide"])
    cfg = _config(tmp_path, patient_column="override_patient")
    mapping = map_manifest_schema(
        manifest,
        cfg,
        ExplicitSchemaMap(patient_id="subject", slide_id="slide", image_path="img"),
    )
    assert mapping.patient_id.source_column == "override_patient"
    assert mapping.slide_id.source_column == "slide"
    assert mapping.patient_id.confidence == 1.0


def test_deterministic_canonical_strong_and_weak_aliases(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, ["image_path", "subject", "diagnosis", "set"])
    mapping = map_manifest_schema(manifest, _config(tmp_path))
    assert mapping.image_path.source_column == "image_path"
    assert mapping.patient_id.source_column == "subject"
    assert mapping.class_label.source_column == "diagnosis"
    assert mapping.partition.source_column == "set"


def test_no_substring_only_false_match_and_low_confidence_unresolved(
    tmp_path: Path,
) -> None:
    manifest = _manifest(
        tmp_path,
        ["patientology", "note", "record_uuid"],
        [["a", "x", "r1"], ["b", "y", "r2"]],
    )
    mapping = map_manifest_schema(manifest, _config(tmp_path))
    assert mapping.patient_id.source_column is None
    assert "patient_id" in mapping.unresolved_fields


def test_value_evidence_signals_and_contradictory_header(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        ["file", "split_col", "diagnosis_group", "uuid", "center_col", "patient_id"],
        [
            ["a/b.svs", "train", "A", "r1", "C1", "slide.svs"],
            ["c/d.tif", "test", "B", "r2", "C1", "other.svs"],
        ],
    )
    mapping = map_manifest_schema(manifest, _config(tmp_path))
    assert mapping.image_path.source_column == "file"
    assert mapping.partition.source_column == "split_col"
    assert mapping.class_label.source_column == "diagnosis_group"
    assert mapping.source_record_id.source_column == "uuid"
    assert mapping.institution_id.source_column == "center_col"
    assert mapping.patient_id.source_column == "patient_id"


def test_tied_close_candidates_unresolved_and_alternatives_deterministic(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path, ["subject", "participant", "image_path"])
    mapping = map_manifest_schema(manifest, _config(tmp_path))
    assert mapping.patient_id.source_column is None
    assert mapping.patient_id.alternatives == ("participant", "subject")
    assert mapping.patient_id.validation_messages


def test_close_value_candidates_unresolved(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        ["pic_a", "pic_b", "record_uuid"],
        [["a.svs", "b.svs", "r1"], ["c.svs", "d.svs", "r2"]],
    )
    mapping = map_manifest_schema(manifest, _config(tmp_path))
    assert mapping.image_path.source_column is None
    assert len(mapping.image_path.alternatives) == 2


def test_coverage_accepts_image_or_record_and_rejects_neither(tmp_path: Path) -> None:
    assert (
        map_manifest_schema(
            _manifest(tmp_path, ["image_path"]), _config(tmp_path)
        ).image_path.source_column
        == "image_path"
    )
    assert (
        map_manifest_schema(
            _manifest(tmp_path, ["record_uuid"], [["r1"], ["r2"]]), _config(tmp_path)
        ).source_record_id.source_column
        == "record_uuid"
    )
    with pytest.raises(InsufficientSchemaCoverageError):
        map_manifest_schema(
            _manifest(tmp_path, ["foo"], [["x"], ["y"]]), _config(tmp_path)
        )


def test_model_contracts_confidence_frozen_and_extras(tmp_path: Path) -> None:
    mapping = map_manifest_schema(
        _manifest(tmp_path, ["image_path"]), _config(tmp_path)
    )
    assert 0 <= mapping.image_path.confidence <= 1
    with pytest.raises(ValidationError):
        ExplicitSchemaMap(image_path="x", extra="no")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ExplicitSchemaMap()
    with pytest.raises(ValidationError):
        mapping.image_path.confidence = 0.2  # type: ignore[misc]


def test_pair_checks_compatible_different_column_names(tmp_path: Path) -> None:
    train = load_manifest(
        _csv(tmp_path, "tr.csv", ["image_name", "subject"], [["a.svs", "p1"]]),
        Partition.train,
        "train_manifest",
    )
    test = load_manifest(
        _csv(tmp_path, "te.csv", ["filename", "patient"], [["b.svs", "p2"]]),
        Partition.test,
        "test_manifest",
    )
    result = map_manifest_pair(
        LoadedManifestPair(train=train, test=test), _config(tmp_path)
    )
    assert isinstance(result, ManifestSchemaMappings)
    assert result.mismatch_detected is False


def test_pair_checks_one_sided_unresolved_and_same_header_different_meaning(
    tmp_path: Path,
) -> None:
    train = load_manifest(
        _csv(tmp_path, "tr.csv", ["image_path", "foo"], [["a.svs", "x"]]),
        Partition.train,
        "train_manifest",
    )
    test = load_manifest(
        _csv(tmp_path, "te.csv", ["image_path", "subject"], [["p1", "p2"]]),
        Partition.test,
        "test_manifest",
    )
    result = map_manifest_pair(
        LoadedManifestPair(train=train, test=test), _config(tmp_path)
    )
    assert result.mismatch_detected is True
    assert result.validation_messages
    assert result.model_dump_json() == result.model_dump_json()


def test_semantic_fields_exact_set() -> None:
    assert tuple(field.value for field in SemanticField) == (
        "image_path",
        "patient_id",
        "specimen_id",
        "slide_id",
        "institution_id",
        "class_label",
        "partition",
        "source_record_id",
    )
