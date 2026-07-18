"""Tests for deterministic AuditConfig validation."""

import pytest
from pydantic import ValidationError

from slidelineage.config import AuditConfig


def make_config(**overrides: object) -> AuditConfig:
    values: dict[str, object] = {
        "train_manifest": "data/train.csv",
        "test_manifest": "data/test.csv",
        "images_dir": "data/images",
        "output_dir": "artifacts/audit",
    }
    values.update(overrides)
    return AuditConfig(**values)


def test_valid_config_preserves_relative_paths() -> None:
    config = make_config(patient_column=" patient_id ")

    assert config.train_manifest.as_posix() == "data/train.csv"
    assert config.patient_column == "patient_id"


@pytest.mark.parametrize("field", ["max_image_pairs", "image_max_pixels"])
def test_positive_numeric_bounds(field: str) -> None:
    with pytest.raises(ValidationError):
        make_config(**{field: 0})


@pytest.mark.parametrize(
    "field", ["phash_distance_threshold", "dhash_distance_threshold"]
)
@pytest.mark.parametrize("value", [-1, 65])
def test_hash_threshold_bounds(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        make_config(**{field: value})


def test_distinct_manifest_paths_required() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        make_config(test_manifest="data/train.csv")


def test_output_path_cannot_equal_input_manifest() -> None:
    with pytest.raises(ValidationError, match="output_dir"):
        make_config(output_dir="data/train.csv")


def test_ai_acceptance_requires_ai_schema_mapping() -> None:
    with pytest.raises(ValidationError, match="requires ai_schema_map"):
        make_config(accept_validated_ai_mapping=True)


def test_blank_semantic_override_rejected() -> None:
    with pytest.raises(ValidationError, match="nonblank"):
        make_config(patient_column="   ")


def test_digest_is_deterministic_and_uses_portable_path_strings() -> None:
    first = make_config(train_manifest="data\\train.csv")
    second = make_config(train_manifest="data\\train.csv")

    assert first.canonical_json() == second.canonical_json()
    assert first.digest() == second.digest()
    assert "data\\train.csv" not in first.canonical_json()
    assert "data/train.csv" in first.canonical_json()


def test_digest_changes_when_scientific_field_changes() -> None:
    first = make_config(phash_distance_threshold=8)
    second = make_config(phash_distance_threshold=9)

    assert first.digest() != second.digest()
