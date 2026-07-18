"""Validated deterministic configuration contracts for SlideLineage."""

import hashlib
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from slidelineage.policy import DEFAULT_POLICY_PROFILE

_COLUMN_OVERRIDE_FIELDS = {
    "patient_column",
    "specimen_column",
    "slide_column",
    "image_column",
    "institution_column",
    "label_column",
    "record_id_column",
}


def _portable_path_string(path: Path) -> str:
    return path.as_posix().replace("\\", "/")


def _safe_normalized_path(path: Path) -> str:
    return path.as_posix().replace("\\", "/").rstrip("/") or "."


class AuditConfig(BaseModel):
    """External audit configuration contract.

    The configuration digest uses portable path strings (`Path.as_posix()`) exactly as
    supplied after Pydantic path coercion. Paths are not resolved against the current
    machine, so relative paths remain relative while separators are deterministic.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    train_manifest: Path = Field(description="Path to the planned train manifest.")
    test_manifest: Path = Field(description="Path to the planned test manifest.")
    images_dir: Path | None = Field(default=None, description="Optional image root.")
    output_dir: Path = Field(
        description="Output directory for future report artifacts."
    )
    force: bool = False
    repair: bool = False
    group_by_institution: bool = False
    target_train_fraction: float | None = Field(default=None, gt=0, lt=1)
    policy_profile: str = DEFAULT_POLICY_PROFILE
    max_image_pairs: int = Field(default=100_000, gt=0)
    phash_distance_threshold: int = Field(default=8, ge=0, le=64)
    dhash_distance_threshold: int = Field(default=12, ge=0, le=64)
    image_max_pixels: int = Field(default=25_000_000, gt=0)
    schema_map_path: Path | None = None
    ai_schema_map: bool = False
    accept_validated_ai_mapping: bool = False
    patient_column: str | None = None
    specimen_column: str | None = None
    slide_column: str | None = None
    image_column: str | None = None
    institution_column: str | None = None
    label_column: str | None = None
    record_id_column: str | None = None

    @field_validator(*_COLUMN_OVERRIDE_FIELDS, mode="before")
    @classmethod
    def _trim_optional_column(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("semantic column overrides must be nonblank")
            return stripped
        return value

    @model_validator(mode="after")
    def _validate_cross_field_rules(self) -> Self:
        train_path = _safe_normalized_path(self.train_manifest)
        test_path = _safe_normalized_path(self.test_manifest)
        output_path = _safe_normalized_path(self.output_dir)
        if train_path == test_path:
            raise ValueError("train_manifest and test_manifest must differ")
        if output_path in {train_path, test_path}:
            raise ValueError("output_dir must not equal an input manifest path")
        if self.accept_validated_ai_mapping and not self.ai_schema_map:
            raise ValueError(
                "accept_validated_ai_mapping=True requires ai_schema_map=True"
            )
        return self

    def canonical_json(self) -> str:
        """Return deterministic canonical JSON for scientifically relevant config."""

        dumped = self.model_dump(mode="python")
        canonical = _canonicalize_paths(dumped)
        return _json_dumps(canonical)

    def digest(self) -> str:
        """Return a SHA-256 digest of canonical configuration JSON."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _canonicalize_paths(value: Any) -> Any:
    if isinstance(value, Path):
        return _portable_path_string(value)
    if isinstance(value, dict):
        return {key: _canonicalize_paths(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize_paths(item) for item in value]
    return value


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))
