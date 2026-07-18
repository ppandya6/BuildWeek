from pathlib import Path

import pytest
from pydantic import ValidationError

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    DuplicateSemanticAssignmentError,
    InvalidSchemaMapError,
    MissingMappedColumnError,
    RequiredSemanticCoverageError,
    UnknownSchemaFieldError,
    UnsupportedSchemaMapFormatError,
)
from slidelineage.ingest import load_manifest
from slidelineage.models import (
    ExplicitSchemaMap,
    ManifestSchemaMappings,
    Partition,
    SchemaFieldMapping,
    SchemaMappingSource,
)
from slidelineage.schema_mapping import (
    load_schema_map,
    map_manifest_pair,
    map_manifest_schema,
)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def cfg(
    tmp_path: Path, train: Path, test: Path | None = None, **kwargs: object
) -> AuditConfig:
    return AuditConfig(
        train_manifest=train,
        test_manifest=test or tmp_path / "test.csv",
        output_dir=tmp_path / "out",
        **kwargs,
    )


def manifest(tmp_path: Path, text: str, name: str = "train.csv"):
    return load_manifest(
        write(tmp_path / name, text), Partition.train, "train_manifest"
    )


def test_valid_yaml_and_json_schema_maps(tmp_path: Path) -> None:
    yaml_path = write(
        tmp_path / "schema.yaml", "patient_id: subject\nimage_path: image_name\n"
    )
    json_path = write(tmp_path / "schema.json", '{"source_record_id": "record_uuid"}')
    assert load_schema_map(yaml_path).mappings
    assert load_schema_map(json_path).mappings


@pytest.mark.parametrize(
    ("name", "content", "error"),
    [
        ("schema.txt", "patient_id: subject\n", UnsupportedSchemaMapFormatError),
        ("bad.yaml", "patient_id: [", InvalidSchemaMapError),
        ("bad.json", '{"patient_id": ', InvalidSchemaMapError),
        ("list.yaml", "- patient_id\n", InvalidSchemaMapError),
        ("unknown.yaml", "bad_field: subject\n", UnknownSchemaFieldError),
        ("nonstring.yaml", "patient_id: 1\n", InvalidSchemaMapError),
        ("blank.yaml", "patient_id: '  '\n", InvalidSchemaMapError),
        (
            "duplicate.yaml",
            "patient_id: subject\nimage_path: SUBJECT\n",
            DuplicateSemanticAssignmentError,
        ),
    ],
)
def test_invalid_schema_map_files(
    tmp_path: Path, name: str, content: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        load_schema_map(write(tmp_path / name, content))


def test_explicit_map_missing_column_and_normalized_lookup(tmp_path: Path) -> None:
    loaded = manifest(tmp_path, "Image Name,subject\nslide1.png,P1\n")
    schema_path = write(
        tmp_path / "schema.yaml", "image_path: image-name\npatient_id: missing\n"
    )
    with pytest.raises(MissingMappedColumnError):
        map_manifest_schema(
            loaded, cfg(tmp_path, loaded.source.path, schema_map_path=schema_path)
        )
    schema_path.write_text(
        "image_path: image-name\npatient_id: subject\n", encoding="utf-8"
    )
    mapping = map_manifest_schema(
        loaded, cfg(tmp_path, loaded.source.path, schema_map_path=schema_path)
    )
    assert mapping.image_path.source_column == "Image Name"
    assert mapping.patient_id.source_column == "subject"


def test_direct_flag_overrides_file_mapping(tmp_path: Path) -> None:
    loaded = manifest(tmp_path, "image_name,actual_patient,file_patient\na.png,P1,P2\n")
    schema_path = write(
        tmp_path / "schema.yaml", "image_path: image_name\npatient_id: file_patient\n"
    )
    mapping = map_manifest_schema(
        loaded,
        cfg(
            tmp_path,
            loaded.source.path,
            schema_map_path=schema_path,
            patient_column="actual_patient",
        ),
    )
    assert mapping.patient_id.source_column == "actual_patient"
    assert mapping.patient_id.source is SchemaMappingSource.explicit_user_mapping
    assert mapping.patient_id.confidence == 1.0


def test_deterministic_header_mapping_aliases_no_substring_and_alternatives(
    tmp_path: Path,
) -> None:
    loaded = manifest(
        tmp_path,
        "filename,subject,sample,slide_barcode,source_center,diagnosis_group,split,record_uuid,not_patientish\n"
        "a.png,P1,S1,SL1,C1,Tumor,train,R1,foo\n"
        "b.png,P1,S2,SL2,C1,Normal,test,R2,bar\n",
    )
    mapping = map_manifest_schema(loaded, cfg(tmp_path, loaded.source.path))
    assert mapping.image_path.source_column == "filename"
    assert mapping.patient_id.source_column == "subject"
    assert mapping.specimen_id.source_column == "sample"
    assert mapping.slide_id.source_column == "slide_barcode"
    assert mapping.institution_id.source_column == "source_center"
    assert mapping.class_label.source_column == "diagnosis_group"
    assert mapping.partition.source_column == "split"
    assert mapping.source_record_id.source_column == "record_uuid"
    assert "not_patientish" not in mapping.patient_id.alternatives
    assert (
        mapping.model_dump_json()
        == map_manifest_schema(
            loaded, cfg(tmp_path, loaded.source.path)
        ).model_dump_json()
    )


def test_weak_aliases_can_map_with_value_support(tmp_path: Path) -> None:
    loaded = manifest(
        tmp_path, "path,set,id\nimgs/a.png,train,R1\nimgs/b.png,test,R2\n"
    )
    mapping = map_manifest_schema(loaded, cfg(tmp_path, loaded.source.path))
    assert mapping.image_path.source_column == "path"
    assert mapping.partition.source_column == "set"
    assert mapping.source_record_id.source_column == "id"


def test_value_pattern_scoring_and_contradictory_header(tmp_path: Path) -> None:
    loaded = manifest(
        tmp_path,
        "image_path,class_label,source_record_id,institution_id,patient_id\n"
        "slides/a.tif,Tumor,R1,SiteA,P1\n"
        "slides/b.tif,Normal,R2,SiteA,P1\n"
        "slides/c.tif,Tumor,R3,SiteB,P2\n",
    )
    mapping = map_manifest_schema(loaded, cfg(tmp_path, loaded.source.path))
    assert mapping.image_path.confidence and mapping.image_path.confidence > 0.9
    assert mapping.class_label.source_column == "class_label"
    assert mapping.source_record_id.source_column == "source_record_id"
    assert mapping.institution_id.source_column == "institution_id"
    near_unique = manifest(
        tmp_path, "image_path,label\na.png,A\nb.png,B\nc.png,C\n", "near.csv"
    )
    weak = map_manifest_schema(near_unique, cfg(tmp_path, near_unique.source.path))
    assert weak.class_label.source_column is None


def test_ambiguity_and_low_confidence_are_preserved(tmp_path: Path) -> None:
    tied = manifest(tmp_path, "patient,subject,image_path\nP1,S1,a.png\nP2,S2,b.png\n")
    mapping = map_manifest_schema(tied, cfg(tmp_path, tied.source.path))
    assert mapping.patient_id.source_column is None
    assert mapping.patient_id.source is SchemaMappingSource.unresolved
    assert mapping.patient_id.alternatives == ("patient", "subject")
    assert mapping.patient_id.validation_messages
    low = manifest(tmp_path, "foo,bar\nA,B\nC,D\n", "low.csv")
    with pytest.raises(RequiredSemanticCoverageError):
        map_manifest_schema(low, cfg(tmp_path, low.source.path))


def test_joint_validation_rejects_reused_column_and_mixed_sources(
    tmp_path: Path,
) -> None:
    loaded = manifest(tmp_path, "image,subject,record_uuid\na.png,P1,R1\n")
    schema_path = write(
        tmp_path / "schema.yaml", "image_path: image\nsource_record_id: record_uuid\n"
    )
    mapping = map_manifest_schema(
        loaded,
        cfg(
            tmp_path,
            loaded.source.path,
            schema_map_path=schema_path,
            patient_column="subject",
        ),
    )
    assert mapping.image_path.source is SchemaMappingSource.explicit_user_mapping
    assert mapping.patient_id.source is SchemaMappingSource.explicit_user_mapping
    schema_path.write_text(
        "image_path: image\nsource_record_id: image\n", encoding="utf-8"
    )
    with pytest.raises(DuplicateSemanticAssignmentError):
        load_schema_map(schema_path)


def test_pair_consistency_compatible_different_names_and_mismatches(
    tmp_path: Path,
) -> None:
    train = load_manifest(
        write(tmp_path / "train.csv", "subject,image_path\nP1,a.png\n"),
        Partition.train,
        "train_manifest",
    )
    test = load_manifest(
        write(tmp_path / "test.csv", "case_submitter_id,image_name\nP2,b.png\n"),
        Partition.test,
        "test_manifest",
    )
    from slidelineage.models import LoadedManifestPair

    compatible = map_manifest_pair(
        LoadedManifestPair(train=train, test=test),
        cfg(tmp_path, train.source.path, test.source.path),
    )
    assert not compatible.has_mismatch
    assert (
        compatible.model_dump_json()
        == map_manifest_pair(
            LoadedManifestPair(train=train, test=test),
            cfg(tmp_path, train.source.path, test.source.path),
        ).model_dump_json()
    )

    bad_test = load_manifest(
        write(tmp_path / "bad_test.csv", "patient_id,image_path\nP2,b.png\n"),
        Partition.test,
        "test_manifest",
    )
    schema_path = write(
        tmp_path / "schema.yaml", "patient_id: subject\nimage_path: image_path\n"
    )
    mismatched = map_manifest_pair(
        LoadedManifestPair(train=train, test=bad_test),
        cfg(
            tmp_path,
            train.source.path,
            bad_test.source.path,
            schema_map_path=schema_path,
        ),
    )
    assert mismatched.has_mismatch
    assert mismatched.validation_messages


def test_same_header_interpreted_differently_is_reported(tmp_path: Path) -> None:
    train = load_manifest(
        write(tmp_path / "train.csv", "subject,image_path\nP1,a.png\n"),
        Partition.train,
        "train_manifest",
    )
    train_map_path = write(
        tmp_path / "schema.yaml", "patient_id: subject\nimage_path: image_path\n"
    )
    # One shared schema file cannot make subject image_path for only test.
    train_mapping = map_manifest_schema(
        train, cfg(tmp_path, train.source.path, schema_map_path=train_map_path)
    )
    test_mapping = train_mapping.model_copy(
        update={
            "image_path": SchemaFieldMapping(
                semantic_field="image_path",
                source_column="subject",
                source=SchemaMappingSource.explicit_user_mapping,
                confidence=1.0,
            ),
            "patient_id": SchemaFieldMapping(
                semantic_field="patient_id",
                source_column=None,
                source=SchemaMappingSource.unresolved,
                confidence=0.0,
                validation_messages=("withheld for test",),
            ),
        }
    )
    result = ManifestSchemaMappings(
        train=train_mapping,
        test=test_mapping,
        validation_messages=("same source column differs",),
        has_mismatch=True,
    )
    assert result.has_mismatch


def test_contract_behavior() -> None:
    field = SchemaFieldMapping(
        semantic_field="image_path",
        source_column="image",
        source=SchemaMappingSource.deterministic_mapping,
        confidence=0.7,
        alternatives=("image",),
    )
    assert field.source is SchemaMappingSource.deterministic_mapping
    with pytest.raises(ValidationError):
        SchemaFieldMapping(
            semantic_field="image_path",
            source_column="image",
            source=SchemaMappingSource.deterministic_mapping,
            confidence=2.0,
        )
    with pytest.raises(ValidationError):
        ExplicitSchemaMap(mappings={}, path=Path("schema.yaml"), extra=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        field.source_column = "other"  # type: ignore[misc]
