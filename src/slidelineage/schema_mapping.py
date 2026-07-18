"""Deterministic semantic schema mapping for loaded manifests."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    DuplicateSemanticAssignmentError,
    InvalidSchemaMapError,
    MissingMappedColumnError,
    RequiredSemanticCoverageError,
    SchemaMapFileError,
    UnknownSchemaFieldError,
    UnsupportedSchemaMapFormatError,
)
from slidelineage.models import (
    ExplicitSchemaMap,
    LoadedManifest,
    LoadedManifestPair,
    ManifestSchemaMappings,
    SchemaFieldMapping,
    SchemaMapping,
    SchemaMappingSource,
    SemanticField,
)
from slidelineage.normalization import normalize_header, normalize_identifier_candidate

MIN_ACCEPTED_CONFIDENCE: Final[float] = 0.68
MIN_SCORE_GAP: Final[float] = 0.12
TOP_ALTERNATIVE_COUNT: Final[int] = 3
_IMAGE_SUFFIXES: Final[tuple[str, ...]] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
)
_PARTITION_VALUES: Final[frozenset[str]] = frozenset(
    {"train", "test", "validation", "val", "dev"}
)

_SEMANTIC_FIELDS: Final[tuple[SemanticField, ...]] = tuple(SemanticField)
_FIELD_TO_CONFIG_ATTR: Final[dict[SemanticField, str]] = {
    SemanticField.patient_id: "patient_column",
    SemanticField.specimen_id: "specimen_column",
    SemanticField.slide_id: "slide_column",
    SemanticField.image_path: "image_column",
    SemanticField.institution_id: "institution_column",
    SemanticField.class_label: "label_column",
    SemanticField.source_record_id: "record_id_column",
}
_STRONG_ALIASES: Final[dict[SemanticField, frozenset[str]]] = {
    SemanticField.image_path: frozenset(
        {"image_path", "image", "image_name", "filename", "file_name"}
    ),
    SemanticField.patient_id: frozenset(
        {
            "patient_id",
            "patient",
            "case_id",
            "case_submitter_id",
            "subject",
            "participant",
        }
    ),
    SemanticField.specimen_id: frozenset(
        {"specimen_id", "specimen", "sample_id", "sample"}
    ),
    SemanticField.slide_id: frozenset(
        {"slide_id", "slide", "slide_submitter_id", "slide_barcode"}
    ),
    SemanticField.institution_id: frozenset(
        {
            "institution_id",
            "institution",
            "source_center",
            "tissue_source_site",
            "site",
            "center",
        }
    ),
    SemanticField.class_label: frozenset(
        {"class_label", "label", "class", "target", "diagnosis_group"}
    ),
    SemanticField.partition: frozenset({"partition", "split", "dataset_split"}),
    SemanticField.source_record_id: frozenset(
        {"record_id", "record_uuid", "sample_record_id", "row_id", "uuid"}
    ),
}
_WEAK_ALIASES: Final[dict[SemanticField, frozenset[str]]] = {
    SemanticField.image_path: frozenset({"path"}),
    SemanticField.class_label: frozenset({"diagnosis", "y"}),
    SemanticField.partition: frozenset({"set"}),
    SemanticField.source_record_id: frozenset({"id"}),
}


@dataclass(frozen=True)
class _Candidate:
    column: str
    normalized_column: str
    score: float


def load_schema_map(path: Path) -> ExplicitSchemaMap:
    """Load and validate an explicit YAML or JSON schema map."""

    suffix = path.suffix.casefold()
    if suffix not in {".yaml", ".yml", ".json"}:
        raise UnsupportedSchemaMapFormatError(f"unsupported schema-map format: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaMapFileError(f"schema-map file is unreadable: {path}") from exc
    try:
        data: Any = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise InvalidSchemaMapError(f"schema-map file is malformed: {path}") from exc
    if not isinstance(data, dict):
        raise InvalidSchemaMapError(f"schema-map top level must be an object: {path}")

    mappings: dict[SemanticField, str] = {}
    for raw_key, raw_value in data.items():
        if not isinstance(raw_key, str):
            raise UnknownSchemaFieldError(f"schema-map key must be a string: {path}")
        try:
            field = SemanticField(raw_key)
        except ValueError as exc:
            raise UnknownSchemaFieldError(
                f"unknown schema-map semantic field {raw_key!r}: {path}"
            ) from exc
        if not isinstance(raw_value, str):
            raise InvalidSchemaMapError(
                f"schema-map value for {field.value!r} must be a string: {path}"
            )
        if not raw_value.strip():
            raise InvalidSchemaMapError(
                f"schema-map value for {field.value!r} cannot be blank: {path}"
            )
        mappings[field] = raw_value
    _reject_duplicate_assignments(mappings, path)
    return ExplicitSchemaMap(mappings=mappings, path=path)


def map_manifest_schema(manifest: LoadedManifest, config: AuditConfig) -> SchemaMapping:
    """Map one loaded manifest to semantic columns using deterministic precedence."""

    explicit_map = (
        load_schema_map(config.schema_map_path) if config.schema_map_path else None
    )
    selected: dict[SemanticField, SchemaFieldMapping] = {}
    direct_fields = set(_FIELD_TO_CONFIG_ATTR)
    file_fields = set(explicit_map.mappings) if explicit_map is not None else set()

    for field in _SEMANTIC_FIELDS:
        direct_column = _config_column(config, field)
        if direct_column is not None:
            selected[field] = _explicit_field_mapping(
                manifest, field, direct_column, "direct config override"
            )
        elif explicit_map is not None and field in explicit_map.mappings:
            selected[field] = _explicit_field_mapping(
                manifest,
                field,
                explicit_map.mappings[field],
                "explicit schema-map file",
            )
        else:
            selected[field] = _deterministic_field_mapping(manifest, field)

    _validate_joint_assignments(selected)
    if (
        selected[SemanticField.image_path].source_column is None
        and selected[SemanticField.source_record_id].source_column is None
    ):
        raise RequiredSemanticCoverageError(
            "manifest schema requires at least one of image_path or source_record_id: "
            f"{manifest.source.path}"
        )

    unresolved = tuple(
        field.value
        for field, mapping in selected.items()
        if mapping.source is SchemaMappingSource.unresolved
    )
    return _schema_mapping_from_fields(selected, unresolved, direct_fields, file_fields)


def map_manifest_pair(
    pair: LoadedManifestPair, config: AuditConfig
) -> ManifestSchemaMappings:
    """Map train/test manifests and return deterministic consistency messages."""

    messages: list[str] = []
    fallback_config = config.model_copy(update={"schema_map_path": None})
    try:
        train = map_manifest_schema(pair.train, config)
    except MissingMappedColumnError as exc:
        messages.append(f"train schema-map reference could not be resolved: {exc}")
        train = map_manifest_schema(pair.train, fallback_config)
    try:
        test = map_manifest_schema(pair.test, config)
    except MissingMappedColumnError as exc:
        messages.append(f"test schema-map reference could not be resolved: {exc}")
        test = map_manifest_schema(pair.test, fallback_config)
    messages.extend(_pair_messages(train, test))
    return ManifestSchemaMappings(
        train=train,
        test=test,
        validation_messages=tuple(messages),
        has_mismatch=bool(messages),
    )


def _config_column(config: AuditConfig, field: SemanticField) -> str | None:
    attr = _FIELD_TO_CONFIG_ATTR.get(field)
    if attr is None:
        return None
    value = getattr(config, attr)
    return value if isinstance(value, str) else None


def _explicit_field_mapping(
    manifest: LoadedManifest, field: SemanticField, supplied_column: str, reason: str
) -> SchemaFieldMapping:
    source_column = _resolve_column(manifest, supplied_column)
    return SchemaFieldMapping(
        semantic_field=field.value,
        source_column=source_column,
        source=SchemaMappingSource.explicit_user_mapping,
        confidence=1.0,
        alternatives=(),
        validation_messages=(reason,),
    )


def _resolve_column(manifest: LoadedManifest, supplied_column: str) -> str:
    if supplied_column in manifest.original_headers:
        return supplied_column
    normalized = normalize_header(supplied_column)
    matches = [
        original
        for original, header in zip(
            manifest.original_headers, manifest.normalized_headers, strict=True
        )
        if header == normalized
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise MissingMappedColumnError(
            f"mapped column {supplied_column!r} is absent from manifest: "
            f"{manifest.source.path}"
        )
    raise MissingMappedColumnError(
        f"mapped column {supplied_column!r} is ambiguous after normalization: "
        f"{manifest.source.path}"
    )


def _deterministic_field_mapping(
    manifest: LoadedManifest, field: SemanticField
) -> SchemaFieldMapping:
    candidates = sorted(
        (
            _score_candidate(manifest, field, column, normalized)
            for column, normalized in zip(
                manifest.original_headers, manifest.normalized_headers, strict=True
            )
        ),
        key=lambda candidate: (-candidate.score, candidate.column),
    )
    alternatives = tuple(
        candidate.column
        for candidate in candidates[:TOP_ALTERNATIVE_COUNT]
        if candidate.score > 0
    )
    best = candidates[0]
    second_score = candidates[1].score if len(candidates) > 1 else 0.0
    messages: list[str] = []
    if best.score < MIN_ACCEPTED_CONFIDENCE:
        messages.append(
            f"withheld {field.value}: best confidence {best.score:.2f} "
            f"is below {MIN_ACCEPTED_CONFIDENCE:.2f}"
        )
    if best.score - second_score < MIN_SCORE_GAP:
        messages.append(
            f"withheld {field.value}: top candidates are too close "
            f"({best.score:.2f} vs {second_score:.2f})"
        )
    if messages:
        return SchemaFieldMapping(
            semantic_field=field.value,
            source_column=None,
            source=SchemaMappingSource.unresolved,
            confidence=round(best.score, 4),
            alternatives=alternatives,
            validation_messages=tuple(messages),
        )
    return SchemaFieldMapping(
        semantic_field=field.value,
        source_column=best.column,
        source=SchemaMappingSource.deterministic_mapping,
        confidence=round(best.score, 4),
        alternatives=alternatives,
        validation_messages=(f"deterministic score {best.score:.2f}",),
    )


def _score_candidate(
    manifest: LoadedManifest, field: SemanticField, column: str, normalized: str
) -> _Candidate:
    header = _header_score(field, normalized)
    values = _value_score(manifest, field, normalized)
    if field is SemanticField.class_label and values == 0 and normalized != field.value:
        header = min(header, 0.60)
    score = header + values
    return _Candidate(
        column=column, normalized_column=normalized, score=min(score, 1.0)
    )


def _header_score(field: SemanticField, normalized: str) -> float:
    if normalized == field.value:
        return 0.90
    if normalized in _STRONG_ALIASES[field]:
        return 0.82
    if normalized in _WEAK_ALIASES.get(field, frozenset()):
        return 0.58
    field_tokens = set(field.value.split("_"))
    header_tokens = set(normalized.split("_"))
    if field_tokens and len(field_tokens & header_tokens) >= 2:
        return 0.28
    return 0.0


def _column_values(manifest: LoadedManifest, normalized_header: str) -> list[str]:
    return [
        value
        for row in manifest.rows
        for value in [row.normalized_header_values.get(normalized_header)]
        if value is not None
    ]


def _value_score(
    manifest: LoadedManifest, field: SemanticField, normalized_header: str
) -> float:
    values = _column_values(manifest, normalized_header)
    if not values:
        return 0.0
    row_count = max(len(manifest.rows), 1)
    unique_ratio = len(set(values)) / len(values)
    image_like = sum(_looks_image_like(value) for value in values) / len(values)
    partition_like = sum(_partition_value(value) for value in values) / len(values)
    if field is SemanticField.image_path:
        return (
            min(0.18 + (0.22 * image_like) + (0.08 * unique_ratio), 0.35)
            if image_like
            else 0.0
        )
    if field is SemanticField.partition:
        return 0.36 * partition_like if partition_like >= 0.8 else 0.0
    if field is SemanticField.class_label:
        cardinality = len(set(values))
        if cardinality <= 1:
            return 0.0
        if row_count >= 3 and cardinality >= row_count * 0.8:
            return 0.0
        return 0.20
    if field is SemanticField.source_record_id:
        if image_like >= 0.5:
            return 0.0
        return 0.28 if unique_ratio >= 0.95 else 0.0
    if field is SemanticField.institution_id:
        cardinality = len(set(values))
        return 0.18 if 1 < cardinality <= max(2, row_count // 2) else 0.0
    if field in {SemanticField.patient_id, SemanticField.specimen_id}:
        return 0.10 if unique_ratio < 0.95 else 0.0
    return 0.0


def _looks_image_like(value: str) -> bool:
    comparison = value.casefold()
    return comparison.endswith(_IMAGE_SUFFIXES) or "/" in value or "\\" in value


def _partition_value(value: str) -> bool:
    comparison = normalize_identifier_candidate(value)
    return comparison in _PARTITION_VALUES if comparison is not None else False


def _reject_duplicate_assignments(
    mappings: dict[SemanticField, str], path: Path
) -> None:
    by_column: dict[str, SemanticField] = {}
    for field, column in mappings.items():
        key = normalize_header(column)
        previous = by_column.get(key)
        if previous is not None and previous is not field:
            raise DuplicateSemanticAssignmentError(
                "schema-map assigns one source column to multiple semantic fields "
                f"({previous.value!r}, {field.value!r}): {path}"
            )
        by_column[key] = field


def _validate_joint_assignments(
    selected: dict[SemanticField, SchemaFieldMapping],
) -> None:
    by_column: dict[str, SemanticField] = {}
    for field in _SEMANTIC_FIELDS:
        column = selected[field].source_column
        if column is None:
            continue
        key = normalize_header(column)
        previous = by_column.get(key)
        if previous is not None:
            raise DuplicateSemanticAssignmentError(
                "one source column is assigned to multiple semantic fields "
                f"({previous.value!r}, {field.value!r}): {column!r}"
            )
        by_column[key] = field


def _schema_mapping_from_fields(
    selected: dict[SemanticField, SchemaFieldMapping],
    unresolved: tuple[str, ...],
    direct_fields: set[SemanticField],
    file_fields: set[SemanticField],
) -> SchemaMapping:
    # direct_fields and file_fields document precedence in the call path; they are kept
    # in the signature to make precedence explicit for reviewers without serializing it.
    _ = (direct_fields, file_fields)
    return SchemaMapping(
        image_path=selected[SemanticField.image_path],
        patient_id=selected[SemanticField.patient_id],
        specimen_id=selected[SemanticField.specimen_id],
        slide_id=selected[SemanticField.slide_id],
        institution_id=selected[SemanticField.institution_id],
        class_label=selected[SemanticField.class_label],
        partition=selected[SemanticField.partition],
        source_record_id=selected[SemanticField.source_record_id],
        unresolved_fields=unresolved,
    )


def _pair_messages(train: SchemaMapping, test: SchemaMapping) -> list[str]:
    messages: list[str] = []
    train_by_column = _column_to_field(train)
    test_by_column = _column_to_field(test)
    for field in _SEMANTIC_FIELDS:
        train_mapping = getattr(train, field.value)
        test_mapping = getattr(test, field.value)
        if (train_mapping.source_column is None) != (
            test_mapping.source_column is None
        ):
            messages.append(
                f"semantic field {field.value} is mapped in only one manifest"
            )
    for column in sorted(set(train_by_column) & set(test_by_column)):
        if train_by_column[column] != test_by_column[column]:
            messages.append(
                "same source column is interpreted differently across manifests: "
                f"{column!r} as {train_by_column[column].value} vs "
                f"{test_by_column[column].value}"
            )
    train_core = {SemanticField.image_path, SemanticField.source_record_id} & set(
        train_by_column.values()
    )
    test_core = {SemanticField.image_path, SemanticField.source_record_id} & set(
        test_by_column.values()
    )
    if train_core != test_core:
        messages.append(
            "core semantic coverage differs between train and test manifests"
        )
    return sorted(dict.fromkeys(messages))


def _column_to_field(mapping: SchemaMapping) -> dict[str, SemanticField]:
    result: dict[str, SemanticField] = {}
    for field in _SEMANTIC_FIELDS:
        field_mapping = getattr(mapping, field.value)
        if field_mapping.source_column is not None:
            result[field_mapping.source_column] = field
    return result
