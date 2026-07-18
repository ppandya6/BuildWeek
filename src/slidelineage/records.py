"""Canonical record construction from loaded manifests and schema mappings."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Final

from slidelineage.errors import (
    DuplicateSourceRecordIdError,
    MalformedTcgaIdentifierError,
    MissingSourceRecordIdError,
    SemanticColumnAccessError,
)
from slidelineage.models import (
    CanonicalManifestRecords,
    CanonicalRecord,
    CanonicalRecordPair,
    IdentifierDerivationMethod,
    IdentifierProvenance,
    IdentifierStatus,
    LineageConflict,
    LoadedManifest,
    LoadedManifestPair,
    Partition,
    RawManifestRow,
    RecordIdMethod,
    SchemaFieldMapping,
    SchemaMapping,
    SchemaMappingSource,
    TcgaLineage,
)
from slidelineage.normalization import (
    normalize_identifier_candidate,
    normalize_missing_value,
)
from slidelineage.schema_mapping import ManifestSchemaMappings
from slidelineage.tcga import parse_tcga_identifier

_ID_FIELDS: Final[tuple[str, ...]] = (
    "patient_id",
    "specimen_id",
    "slide_id",
    "institution_id",
    "source_record_id",
)
_SEMANTIC_FIELDS: Final[tuple[str, ...]] = (
    "image_path",
    "patient_id",
    "specimen_id",
    "slide_id",
    "institution_id",
    "class_label",
    "source_record_id",
)
_PARTITION_VALUES: Final[dict[str, Partition]] = {
    "train": Partition.train,
    "training": Partition.train,
    "test": Partition.test,
    "testing": Partition.test,
}


def construct_manifest_records(
    manifest: LoadedManifest, mapping: SchemaMapping
) -> CanonicalManifestRecords:
    """Construct source-row ordered canonical records for one mapped manifest."""

    semantic_values_by_row = [
        _extract_semantic_values(row, mapping) for row in manifest.rows
    ]
    record_ids, methods = _record_ids(manifest, mapping, semantic_values_by_row)
    records: list[CanonicalRecord] = []
    provenance: list[IdentifierProvenance] = []
    conflicts: list[LineageConflict] = []
    warnings: list[str] = []

    for row, record_id, method, semantic_values in zip(
        manifest.rows, record_ids, methods, semantic_values_by_row, strict=True
    ):
        row_warnings = _partition_warnings(manifest, mapping, row)
        warnings.extend(row_warnings)
        tcga = _first_tcga_lineage(row, mapping)
        reconciled, row_provenance, row_conflicts = _reconcile_lineage(
            record_id, semantic_values, mapping, tcga
        )
        provenance.extend(row_provenance)
        conflicts.extend(row_conflicts)
        raw_digest = _digest(_canonical_raw_payload(row.raw_values))
        normalized_digest = _digest(_canonical_normalized_payload(reconciled, tcga))
        records.append(
            CanonicalRecord(
                record_id=record_id,
                record_id_method=method,
                source_manifest_id=manifest.source.manifest_id,
                source_row_number=row.source_row_number,
                assigned_partition=manifest.source.assigned_partition,
                source_record_id=reconciled["source_record_id"],
                image_path=reconciled["image_path"],
                patient_id=reconciled["patient_id"],
                specimen_id=reconciled["specimen_id"],
                slide_id=reconciled["slide_id"],
                institution_id=reconciled["institution_id"],
                label=reconciled["class_label"],
                tcga=tcga,
                raw_values_digest=raw_digest,
                normalized_values_digest=normalized_digest,
            )
        )
    return CanonicalManifestRecords(
        source_manifest_id=manifest.source.manifest_id,
        partition=manifest.source.assigned_partition,
        records=tuple(records),
        identifier_provenance=tuple(provenance),
        conflicts=tuple(conflicts),
        warnings=tuple(warnings),
    )


def construct_record_pair(
    pair: LoadedManifestPair, mappings: ManifestSchemaMappings
) -> CanonicalRecordPair:
    """Construct canonical train/test record collections."""

    return CanonicalRecordPair(
        train=construct_manifest_records(pair.train, mappings.train),
        test=construct_manifest_records(pair.test, mappings.test),
    )


def _extract_semantic_values(
    row: RawManifestRow, mapping: SchemaMapping
) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for field in _SEMANTIC_FIELDS:
        field_mapping: SchemaFieldMapping = getattr(mapping, field)
        if field_mapping.source is SchemaMappingSource.unresolved:
            values[field] = None
            continue
        column = field_mapping.source_column
        if column is None or column not in row.raw_values:
            raise SemanticColumnAccessError(
                "mapped column for "
                f"{field} is unavailable at source row {row.source_row_number}"
            )
        cleaned = normalize_missing_value(row.raw_values[column])
        if field in _ID_FIELDS:
            values[field] = normalize_identifier_candidate(cleaned)
        else:
            values[field] = cleaned
    return values


def _record_ids(
    manifest: LoadedManifest,
    mapping: SchemaMapping,
    semantic_values_by_row: list[dict[str, str | None]],
) -> tuple[tuple[str, ...], tuple[RecordIdMethod, ...]]:
    source_mapping = mapping.source_record_id
    if source_mapping.source is not SchemaMappingSource.unresolved:
        ids: list[str] = []
        seen: set[str] = set()
        for row, values in zip(manifest.rows, semantic_values_by_row, strict=True):
            source_id = values["source_record_id"]
            if source_id is None:
                raise MissingSourceRecordIdError(
                    "source_record_id is missing in manifest "
                    f"{manifest.source.manifest_id} row {row.source_row_number}"
                )
            if source_id in seen:
                raise DuplicateSourceRecordIdError(
                    "duplicate source_record_id in manifest "
                    f"{manifest.source.manifest_id}: {source_id}"
                )
            seen.add(source_id)
            ids.append(
                f"rec_src_{manifest.source.manifest_id}_{_digest(source_id)[:16]}"
            )
        return tuple(ids), tuple(RecordIdMethod.source_column for _ in ids)

    bases = [_fingerprint_base(row) for row in manifest.rows]
    counts = Counter(bases)
    duplicate_ordinals: dict[str, int] = defaultdict(int)
    ids = []
    methods = []
    for base, _row in zip(bases, manifest.rows, strict=True):
        if counts[base] == 1:
            ids.append(f"rec_{base[:24]}")
            methods.append(RecordIdMethod.canonical_row_fingerprint)
        else:
            duplicate_ordinals[base] += 1
            ids.append(f"rec_{base[:24]}_dup{duplicate_ordinals[base]:04d}")
            methods.append(
                RecordIdMethod.canonical_row_fingerprint_with_collision_suffix
            )
    return tuple(ids), tuple(methods)


def _fingerprint_base(row: RawManifestRow) -> str:
    return _digest({"normalized_header_values": row.normalized_header_values})


def _first_tcga_lineage(
    row: RawManifestRow, mapping: SchemaMapping
) -> TcgaLineage | None:
    for field in ("patient_id", "specimen_id", "slide_id", "source_record_id"):
        mapped: SchemaFieldMapping = getattr(mapping, field)
        if (
            mapped.source is SchemaMappingSource.unresolved
            or mapped.source_column is None
        ):
            continue
        value = normalize_missing_value(row.raw_values.get(mapped.source_column))
        if value is None:
            continue
        try:
            parsed = parse_tcga_identifier(value)
        except MalformedTcgaIdentifierError as exc:
            raise MalformedTcgaIdentifierError(
                "malformed TCGA-like identifier in source row "
                f"{row.source_row_number} field {field}"
            ) from exc
        if parsed is not None:
            return parsed
    return None


def _reconcile_lineage(
    record_id: str,
    direct: dict[str, str | None],
    mapping: SchemaMapping,
    tcga: TcgaLineage | None,
) -> tuple[
    dict[str, str | None], tuple[IdentifierProvenance, ...], tuple[LineageConflict, ...]
]:
    result = dict(direct)
    provenance: list[IdentifierProvenance] = []
    conflicts: list[LineageConflict] = []
    derived = {
        "patient_id": tcga.derived_patient_id if tcga else None,
        "specimen_id": tcga.derived_specimen_id if tcga else None,
    }
    for field in _ID_FIELDS:
        field_mapping: SchemaFieldMapping = getattr(mapping, field)
        source_column = field_mapping.source_column
        direct_value = direct[field]
        derived_value = derived.get(field)
        derived_cmp = normalize_identifier_candidate(derived_value)
        if direct_value is None and derived_cmp is not None:
            result[field] = derived_cmp
            provenance.append(
                _prov(
                    field,
                    derived_cmp,
                    None,
                    IdentifierDerivationMethod.tcga_derived,
                    tcga,
                    IdentifierStatus.accepted,
                )
            )
        elif (
            direct_value is not None
            and derived_cmp is not None
            and direct_value != derived_cmp
        ):
            conflict = _conflict(
                record_id, field, direct_value, derived_cmp, source_column, tcga
            )
            conflicts.append(conflict)
            provenance.append(
                _prov(
                    field,
                    direct_value,
                    source_column,
                    IdentifierDerivationMethod.direct_manifest_value,
                    None,
                    IdentifierStatus.conflicted,
                )
            )
            provenance.append(
                _prov(
                    field,
                    derived_cmp,
                    None,
                    IdentifierDerivationMethod.tcga_derived,
                    tcga,
                    IdentifierStatus.conflicted,
                )
            )
        elif direct_value is not None:
            provenance.append(
                _prov(
                    field,
                    direct_value,
                    source_column,
                    IdentifierDerivationMethod.direct_manifest_value,
                    None,
                    IdentifierStatus.accepted,
                )
            )
            if derived_cmp is not None:
                provenance.append(
                    _prov(
                        field,
                        derived_cmp,
                        None,
                        IdentifierDerivationMethod.tcga_derived,
                        tcga,
                        IdentifierStatus.accepted,
                    )
                )
        else:
            provenance.append(
                _prov(
                    field,
                    None,
                    source_column,
                    IdentifierDerivationMethod.unavailable,
                    None,
                    IdentifierStatus.unresolved,
                )
            )
    return result, tuple(provenance), tuple(conflicts)


def _prov(
    field: str,
    value: str | None,
    source_column: str | None,
    method: IdentifierDerivationMethod,
    tcga: TcgaLineage | None,
    status: IdentifierStatus,
) -> IdentifierProvenance:
    return IdentifierProvenance(
        semantic_field=field,
        value=value,
        source_column=source_column,
        derivation_method=method,
        parser_version=tcga.parser_version if tcga is not None else None,
        confidence=1.0 if status is not IdentifierStatus.unresolved else 0.0,
        status=status,
    )


def _conflict(
    record_id: str,
    field: str,
    direct_value: str,
    derived_value: str,
    source_column: str | None,
    tcga: TcgaLineage | None,
) -> LineageConflict:
    payload = {
        "record_id": record_id,
        "semantic_field": field,
        "direct_value": direct_value,
        "derived_value": derived_value,
        "parser_version": tcga.parser_version if tcga is not None else None,
    }
    return LineageConflict(
        conflict_id=f"linconf_{_digest(payload)[:24]}",
        record_id=record_id,
        semantic_field=field,
        direct_value=direct_value,
        derived_value=derived_value,
        direct_source_column=source_column,
        parser_version=tcga.parser_version if tcga is not None else "unknown",
        message="direct manifest lineage value differs from TCGA-derived value",
    )


def _partition_warnings(
    manifest: LoadedManifest, mapping: SchemaMapping, row: RawManifestRow
) -> tuple[str, ...]:
    mapped = mapping.partition
    if mapped.source is SchemaMappingSource.unresolved or mapped.source_column is None:
        return ()
    raw = normalize_identifier_candidate(row.raw_values.get(mapped.source_column))
    if raw is None:
        return ()
    parsed = _PARTITION_VALUES.get(raw)
    if parsed is manifest.source.assigned_partition:
        return ()
    if parsed is None:
        detail = "unsupported two-partition value"
    else:
        detail = f"value indicates {parsed.value}"
    return (
        "manifest "
        f"{manifest.source.manifest_id} row {row.source_row_number} partition column "
        "conflicts with CLI-assigned "
        f"{manifest.source.assigned_partition.value}: {detail}",
    )


def _canonical_raw_payload(raw_values: dict[str, str | None]) -> dict[str, object]:
    return {"raw_values": {key: raw_values[key] for key in sorted(raw_values)}}


def _canonical_normalized_payload(
    values: dict[str, str | None], tcga: TcgaLineage | None
) -> dict[str, object]:
    return {
        "semantic_values": {key: values.get(key) for key in sorted(_SEMANTIC_FIELDS)},
        "tcga": tcga.model_dump(mode="json") if tcga is not None else None,
    }


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
