"""Deterministic semantic schema mapping for loaded Slide-of-Life manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    DuplicateSemanticAssignmentError,
    InsufficientSchemaCoverageError,
    InvalidSchemaMapError,
    MissingMappedColumnError,
    SchemaMapFileError,
    UnknownSchemaFieldError,
    UnsupportedSchemaMapFormatError,
)
from slidelineage.models import (
    LoadedManifest,
    LoadedManifestPair,
    SchemaFieldMapping,
    SchemaMapping,
    SchemaMappingSource,
)
from slidelineage.normalization import normalize_header


class SemanticField(Enum):
    """Supported semantic fields with stable serialized values."""

    image_path = "image_path"
    patient_id = "patient_id"
    specimen_id = "specimen_id"
    slide_id = "slide_id"
    institution_id = "institution_id"
    class_label = "class_label"
    partition = "partition"
    source_record_id = "source_record_id"


SEMANTIC_FIELDS: Final[tuple[SemanticField, ...]] = tuple(SemanticField)
_DIRECT_CONFIG_FIELDS: Final[dict[str, SemanticField]] = {
    "patient_column": SemanticField.patient_id,
    "specimen_column": SemanticField.specimen_id,
    "slide_column": SemanticField.slide_id,
    "image_column": SemanticField.image_path,
    "institution_column": SemanticField.institution_id,
    "label_column": SemanticField.class_label,
    "record_id_column": SemanticField.source_record_id,
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

EXACT_SEMANTIC_SCORE: Final[float] = 0.90
STRONG_ALIAS_SCORE: Final[float] = 0.82
WEAK_ALIAS_SCORE: Final[float] = 0.62
TOKEN_OVERLAP_SCORE: Final[float] = 0.20
VALUE_SIGNAL_SCORE: Final[float] = 0.60
HEADER_CONTRADICTION_PENALTY: Final[float] = 0.35
MIN_CONFIDENCE: Final[float] = 0.58
MIN_MARGIN: Final[float] = 0.12
CANDIDATE_LIMIT: Final[int] = 3
_IMAGE_SUFFIXES: Final[tuple[str, ...]] = (
    ".svs",
    ".tif",
    ".tiff",
    ".png",
    ".jpg",
    ".jpeg",
    ".dcm",
    ".ndpi",
    ".mrxs",
)
_SPLIT_VALUES: Final[frozenset[str]] = frozenset(
    {"train", "training", "test", "testing", "val", "valid", "validation"}
)


class ExplicitSchemaMap(BaseModel):
    """User-authored source-column map for supported semantic fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    image_path: str | None = None
    patient_id: str | None = None
    specimen_id: str | None = None
    slide_id: str | None = None
    institution_id: str | None = None
    class_label: str | None = None
    partition: str | None = None
    source_record_id: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _nonblank_string(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("schema-map values must be source-column strings")
        stripped = value.strip()
        if not stripped:
            raise ValueError("schema-map values cannot be blank")
        return stripped

    @model_validator(mode="after")
    def _at_least_one(self) -> ExplicitSchemaMap:
        if not any(getattr(self, field.value) is not None for field in SemanticField):
            raise ValueError("schema map must contain at least one semantic field")
        return self


class ManifestSchemaMappings(BaseModel):
    """Train/test schema mappings plus pair-level consistency validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    train: SchemaMapping
    test: SchemaMapping
    validation_messages: tuple[str, ...] = ()
    mismatch_detected: bool = False


@dataclass(frozen=True)
class _Candidate:
    column: str
    score: float
    messages: tuple[str, ...]


def load_schema_map(path: Path) -> ExplicitSchemaMap:
    """Load a JSON/YAML explicit schema map without inspecting row content."""

    suffix = path.suffix.lower()
    if suffix not in {".yaml", ".yml", ".json"}:
        raise UnsupportedSchemaMapFormatError(
            f"unsupported schema-map extension: {suffix}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaMapFileError(f"schema-map file is unreadable: {path}") from exc
    try:
        data = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
    except json.JSONDecodeError as exc:
        raise InvalidSchemaMapError(f"schema-map JSON is malformed: {path}") from exc
    except yaml.YAMLError as exc:
        raise InvalidSchemaMapError(f"schema-map YAML is malformed: {path}") from exc
    if not isinstance(data, dict):
        raise InvalidSchemaMapError("schema-map top level must be an object")
    unknown = sorted(
        str(key)
        for key in data
        if str(key) not in {field.value for field in SemanticField}
    )
    if unknown:
        raise UnknownSchemaFieldError(
            f"unknown schema-map semantic field: {unknown[0]}"
        )
    try:
        return ExplicitSchemaMap.model_validate(data)
    except ValueError as exc:
        raise InvalidSchemaMapError(str(exc)) from exc


def map_manifest_schema(
    manifest: LoadedManifest,
    config: AuditConfig,
    explicit_map: ExplicitSchemaMap | None = None,
) -> SchemaMapping:
    """Map loaded manifest headers to supported semantic fields deterministically."""

    direct = _direct_overrides(config)
    explicit = _explicit_assignments(explicit_map) if explicit_map is not None else {}
    mappings: dict[SemanticField, SchemaFieldMapping] = {}

    for field in SEMANTIC_FIELDS:
        if field in direct:
            mappings[field] = _resolve_explicit(
                manifest,
                field,
                direct[field],
                SchemaMappingSource.explicit_user_mapping,
            )
        elif field in explicit:
            mappings[field] = _resolve_explicit(
                manifest,
                field,
                explicit[field],
                SchemaMappingSource.explicit_user_mapping,
            )
        else:
            mappings[field] = _deterministic_mapping(manifest, field)

    mappings = _resolve_reuse_conflicts(mappings)
    unresolved = tuple(
        field.value
        for field, mapping in mappings.items()
        if mapping.source is SchemaMappingSource.unresolved
    )
    if (
        mappings[SemanticField.image_path].source is SchemaMappingSource.unresolved
        and mappings[SemanticField.source_record_id].source
        is SchemaMappingSource.unresolved
    ) and not config.ai_schema_map:
        raise InsufficientSchemaCoverageError(
            "schema mapping requires image_path or source_record_id"
        )
    return SchemaMapping(
        **{field.value: mappings[field] for field in SEMANTIC_FIELDS},
        unresolved_fields=unresolved,
    )


def map_manifest_pair(
    pair: LoadedManifestPair, config: AuditConfig
) -> ManifestSchemaMappings:
    """Map train/test schemas and return deterministic consistency messages."""

    explicit = (
        load_schema_map(config.schema_map_path) if config.schema_map_path else None
    )
    train = map_manifest_schema(pair.train, config, explicit)
    test = map_manifest_schema(pair.test, config, explicit)
    messages = _pair_messages(train, test)
    return ManifestSchemaMappings(
        train=train,
        test=test,
        validation_messages=messages,
        mismatch_detected=bool(messages),
    )


def _direct_overrides(config: AuditConfig) -> dict[SemanticField, str]:
    result: dict[SemanticField, str] = {}
    columns: dict[str, SemanticField] = {}
    for attr, field in _DIRECT_CONFIG_FIELDS.items():
        value = getattr(config, attr)
        if value is None:
            continue
        normalized = normalize_header(value)
        if normalized in columns and columns[normalized] is not field:
            raise DuplicateSemanticAssignmentError(
                "one direct override column maps to multiple semantic fields"
            )
        columns[normalized] = field
        result[field] = value
    return result


def _explicit_assignments(explicit_map: ExplicitSchemaMap) -> dict[SemanticField, str]:
    result = {
        field: getattr(explicit_map, field.value)
        for field in SEMANTIC_FIELDS
        if getattr(explicit_map, field.value) is not None
    }
    seen: dict[str, SemanticField] = {}
    for field, column in result.items():
        normalized = normalize_header(column)
        if normalized in seen and seen[normalized] is not field:
            raise DuplicateSemanticAssignmentError(
                "one schema-map column maps to multiple semantic fields"
            )
        seen[normalized] = field
    return result


def _resolve_explicit(
    manifest: LoadedManifest,
    field: SemanticField,
    requested: str,
    source: SchemaMappingSource,
) -> SchemaFieldMapping:
    matches = [header for header in manifest.original_headers if header == requested]
    if not matches:
        normalized = normalize_header(requested)
        matches = [
            orig
            for orig, norm in zip(
                manifest.original_headers, manifest.normalized_headers, strict=True
            )
            if norm == normalized
        ]
    if not matches:
        raise MissingMappedColumnError(f"mapped column for {field.value} is absent")
    if len(matches) > 1:
        raise MissingMappedColumnError(f"mapped column for {field.value} is ambiguous")
    return SchemaFieldMapping(
        semantic_field=field.value,
        source_column=matches[0],
        source=source,
        confidence=1.0,
        alternatives=(),
        validation_messages=(),
    )


def _deterministic_mapping(
    manifest: LoadedManifest, field: SemanticField
) -> SchemaFieldMapping:
    candidates = [
        _score_column(manifest, field, orig, norm)
        for orig, norm in zip(
            manifest.original_headers, manifest.normalized_headers, strict=True
        )
    ]
    candidates = [c for c in candidates if c.score > 0]
    candidates.sort(key=lambda c: (-c.score, c.column))
    alternatives = tuple(c.column for c in candidates[:CANDIDATE_LIMIT])
    if not candidates:
        return _unresolved(field, alternatives, "no deterministic candidate found")
    top = candidates[0]
    runner = candidates[1].score if len(candidates) > 1 else 0.0
    messages = list(top.messages)
    if top.score < MIN_CONFIDENCE:
        messages.append(
            "top candidate confidence is below the deterministic acceptance threshold"
        )
        return _unresolved(field, alternatives, *messages)
    if top.score - runner < MIN_MARGIN:
        messages.append("top deterministic candidates are tied or too close to resolve")
        return _unresolved(field, alternatives, *messages)
    return SchemaFieldMapping(
        semantic_field=field.value,
        source_column=top.column,
        source=SchemaMappingSource.deterministic_mapping,
        confidence=round(min(top.score, 1.0), 3),
        alternatives=alternatives,
        validation_messages=tuple(messages),
    )


def _score_column(
    manifest: LoadedManifest, field: SemanticField, original: str, normalized: str
) -> _Candidate:
    score = 0.0
    messages: list[str] = []
    if normalized == field.value:
        score += EXACT_SEMANTIC_SCORE
        messages.append("exact semantic header match")
    elif normalized in _STRONG_ALIASES[field]:
        score += STRONG_ALIAS_SCORE
        messages.append("strong alias header match")
    elif normalized in _WEAK_ALIASES.get(field, frozenset()):
        score += WEAK_ALIAS_SCORE
        messages.append("weak alias header match")
    else:
        token_overlap = _token_overlap(normalized, field.value)
        if token_overlap >= 0.5:
            score += TOKEN_OVERLAP_SCORE * token_overlap
            messages.append("limited token-overlap header evidence")
    value_score, value_message = _value_signal(manifest, normalized, field)
    if value_score:
        if _strongly_contradictory_header(normalized, field):
            score = max(0.0, score - HEADER_CONTRADICTION_PENALTY)
            messages.append("value evidence ignored due to contradictory strong header")
        else:
            score += value_score
            messages.append(value_message)
    return _Candidate(original, round(min(score, 1.0), 3), tuple(messages))


def _value_signal(
    manifest: LoadedManifest, normalized: str, field: SemanticField
) -> tuple[float, str]:
    values = [row.normalized_header_values.get(normalized) for row in manifest.rows]
    present = [value for value in values if value]
    if not present:
        return 0.0, ""
    distinct = len(set(present))
    total = len(present)
    lowered = [value.lower() for value in present]
    if field is SemanticField.image_path and (
        any(v.endswith(_IMAGE_SUFFIXES) for v in lowered)
        or any("/" in v or "\\" in v for v in present)
    ):
        return VALUE_SIGNAL_SCORE, "image-like value evidence"
    if (
        field is SemanticField.partition
        and set(lowered).issubset(_SPLIT_VALUES)
        and distinct <= 3
    ):
        return VALUE_SIGNAL_SCORE, "split-like categorical values"
    if field is SemanticField.class_label and 1 < distinct <= max(2, total // 2):
        return VALUE_SIGNAL_SCORE, "low-cardinality class-like values"
    if field is SemanticField.source_record_id and distinct == total:
        return VALUE_SIGNAL_SCORE, "unique record-like values"
    if field is SemanticField.institution_id and 1 <= distinct <= max(1, total // 3):
        return VALUE_SIGNAL_SCORE, "repeated institution-like values"
    return 0.0, ""


def _strongly_contradictory_header(normalized: str, field: SemanticField) -> bool:
    for other in SEMANTIC_FIELDS:
        if other is field:
            continue
        if normalized == other.value or normalized in _STRONG_ALIASES[other]:
            return True
    return False


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split("_"))
    right_tokens = set(right.split("_"))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(right_tokens)


def _unresolved(
    field: SemanticField, alternatives: tuple[str, ...], *messages: str
) -> SchemaFieldMapping:
    return SchemaFieldMapping(
        semantic_field=field.value,
        source_column=None,
        source=SchemaMappingSource.unresolved,
        confidence=0.0,
        alternatives=alternatives,
        validation_messages=tuple(messages) or ("semantic field unresolved",),
    )


def _resolve_reuse_conflicts(
    mappings: dict[SemanticField, SchemaFieldMapping],
) -> dict[SemanticField, SchemaFieldMapping]:
    by_column: dict[str, list[SemanticField]] = {}
    for field, mapping in mappings.items():
        if mapping.source_column is not None:
            by_column.setdefault(normalize_header(mapping.source_column), []).append(
                field
            )
    updated = dict(mappings)
    for fields in by_column.values():
        if len(fields) < 2:
            continue
        if any(
            updated[field].source is SchemaMappingSource.explicit_user_mapping
            for field in fields
        ):
            raise DuplicateSemanticAssignmentError(
                "one source column maps to multiple incompatible semantic fields"
            )
        for field in fields:
            prior = updated[field]
            updated[field] = _unresolved(
                field,
                prior.alternatives,
                *prior.validation_messages,
                "joint validation found source-column reuse conflict",
            )
    return updated


def _resolved(mapping: SchemaFieldMapping) -> bool:
    return (
        mapping.source is not SchemaMappingSource.unresolved
        and mapping.source_column is not None
    )


def _pair_messages(train: SchemaMapping, test: SchemaMapping) -> tuple[str, ...]:
    messages: list[str] = []
    train_by_header = _header_meanings(train)
    test_by_header = _header_meanings(test)
    for field in SEMANTIC_FIELDS:
        tm = getattr(train, field.value)
        sm = getattr(test, field.value)
        if _resolved(tm) != _resolved(sm):
            messages.append(f"{field.value} resolves on only one side")
        if (
            tm.source is SchemaMappingSource.explicit_user_mapping
            and sm.source is not SchemaMappingSource.explicit_user_mapping
        ):
            messages.append(f"{field.value} explicit mapping exists only in train")
        if (
            sm.source is SchemaMappingSource.explicit_user_mapping
            and tm.source is not SchemaMappingSource.explicit_user_mapping
        ):
            messages.append(f"{field.value} explicit mapping exists only in test")
    for header in sorted(set(train_by_header) & set(test_by_header)):
        if train_by_header[header] != test_by_header[header]:
            messages.append(
                f"header {header!r} has different semantic meanings across train/test"
            )
    train_cov = _resolved(train.image_path) or _resolved(train.source_record_id)
    test_cov = _resolved(test.image_path) or _resolved(test.source_record_id)
    if train_cov != test_cov:
        messages.append("minimum semantic coverage differs across train/test")
    messages.extend(_reuse_messages("train", train))
    messages.extend(_reuse_messages("test", test))
    return tuple(messages)


def _header_meanings(mapping: SchemaMapping) -> dict[str, str]:
    meanings: dict[str, str] = {}
    for field in SEMANTIC_FIELDS:
        item = getattr(mapping, field.value)
        if item.source_column is not None:
            meanings[item.source_column] = field.value
    return meanings


def _reuse_messages(label: str, mapping: SchemaMapping) -> tuple[str, ...]:
    seen: dict[str, str] = {}
    messages: list[str] = []
    for field in SEMANTIC_FIELDS:
        item = getattr(mapping, field.value)
        if item.source_column is None:
            continue
        norm = normalize_header(item.source_column)
        if norm in seen and seen[norm] != field.value:
            messages.append(
                f"{label} source column is reused by incompatible semantic fields"
            )
        seen[norm] = field.value
    return tuple(messages)
