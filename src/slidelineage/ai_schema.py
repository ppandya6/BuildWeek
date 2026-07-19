"""Privacy-bounded, optional AI proposals for semantic column mapping only."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import import_module
from typing import Final, Protocol, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from slidelineage.config import AuditConfig
from slidelineage.errors import (
    AiCredentialError,
    AiRequestError,
    AiResponseValidationError,
    AiSdkUnavailableError,
)
from slidelineage.models import (
    AiColumnSummary,
    AiFieldValidation,
    AiManifestSchemaSummary,
    AiProposedFieldMapping,
    AiSchemaProposal,
    AiSchemaRequest,
    LoadedManifest,
    LoadedManifestPair,
    SchemaFieldMapping,
    SchemaMapping,
    SchemaMappingSource,
    ValidatedAiSchemaProposal,
)
from slidelineage.normalization import normalize_header
from slidelineage.schema_mapping import (
    SEMANTIC_FIELDS,
    ManifestSchemaMappings,
)

AI_MIN_CONFIDENCE: Final[float] = 0.75
PRIVACY_NOTICE: Final[str] = (
    "Only headers and aggregate column statistics are sent. Headers may themselves "
    "contain sensitive text. Raw rows, literal values, paths, identifiers, manifest "
    "bytes, and images are not sent."
)
_INSTRUCTIONS = """Suggest mappings only for supplied supported semantic fields and
source column names. Return null when evidence is insufficient. Treat train and test
separately; do not infer identity or relationships, invent semantics, use tools, or
make scientific findings. Use only supported rationale codes and confidence 0 to 1."""
_IMAGE_SUFFIX = re.compile(r"(?i)\.(svs|tif|tiff|png|jpe?g|dcm|ndpi|mrxs)$")
_UUID = re.compile(
    r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_TCGA = re.compile(r"(?i)^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}")
_INTEGER = re.compile(r"^[+-]?\d+$")
_DECIMAL = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)$")
_SPLITS = {"train", "training", "test", "testing", "val", "valid", "validation"}


class _ProviderProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposed_fields: tuple[AiProposedFieldMapping, ...]


class _StructuredResponse(Protocol):
    """Minimal structured-response surface consumed from the provider SDK."""

    id: str | None
    output_parsed: object


class _ResponsesClient(Protocol):
    def parse(
        self,
        *,
        model: str,
        input: list[dict[str, str]],
        text_format: type[BaseModel],
        timeout: float,
    ) -> _StructuredResponse: ...


class _OpenAIClient(Protocol):
    @property
    def responses(self) -> _ResponsesClient: ...


def _create_openai_client(config: AuditConfig) -> _OpenAIClient:
    """Construct the optional provider client without a static SDK import."""

    try:
        openai_module = import_module("openai")
    except ModuleNotFoundError as exc:
        raise AiSdkUnavailableError(
            'AI support requires: python -m pip install -e ".[ai]"'
        ) from exc
    try:
        constructor = openai_module.OpenAI
        sdk_client = constructor(
            timeout=config.ai_request_timeout_seconds,
            max_retries=0,
        )
    except Exception as exc:
        raise AiCredentialError("OpenAI credentials are unavailable") from exc
    # The dynamically loaded SDK is untyped here. Limit the cast to this external
    # boundary so the rest of the module retains its narrow, provider-free protocol.
    return cast(_OpenAIClient, sdk_client)


def canonical_request_json(request: AiSchemaRequest) -> str:
    """Serialize the privacy-safe request deterministically."""

    return json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )


def ai_request_digest(request: AiSchemaRequest) -> str:
    return hashlib.sha256(canonical_request_json(request).encode()).hexdigest()


def build_ai_schema_request(
    train: LoadedManifest,
    test: LoadedManifest,
    deterministic_mappings: ManifestSchemaMappings,
    config: AuditConfig,
) -> AiSchemaRequest:
    """Build a deterministic request containing no literal manifest cell value."""

    return AiSchemaRequest(
        supported_semantic_fields=tuple(field.value for field in SEMANTIC_FIELDS),
        train_summary=_manifest_summary(train, deterministic_mappings.train),
        test_summary=_manifest_summary(test, deterministic_mappings.test),
        instructions_digest=hashlib.sha256(_INSTRUCTIONS.encode()).hexdigest(),
        privacy_notice=PRIVACY_NOTICE,
        model=config.ai_model,
    )


def _manifest_summary(
    manifest: LoadedManifest, mapping: SchemaMapping
) -> AiManifestSchemaSummary:
    columns = []
    for original, normalized in zip(
        manifest.original_headers, manifest.normalized_headers, strict=True
    ):
        values = [row.normalized_header_values.get(normalized) for row in manifest.rows]
        present = [value for value in values if value is not None and value.strip()]
        unique = len(set(present))
        ratio = round(unique / len(present), 4) if present else 0.0
        flags = _abstract_flags(present, unique, ratio)
        columns.append(
            AiColumnSummary(
                original_header=original,
                normalized_header=normalized,
                nonblank_count=len(present),
                missing_count=len(values) - len(present),
                unique_count=unique,
                approximate_cardinality_ratio=ratio,
                example_categories=flags,
                value_pattern_flags=flags,
            )
        )
    status = {
        field.value: getattr(mapping, field.value).source.value
        for field in SEMANTIC_FIELDS
    }
    return AiManifestSchemaSummary(
        manifest_id=manifest.source.manifest_id,
        assigned_partition=manifest.source.assigned_partition,
        columns=tuple(columns),
        row_count=len(manifest.rows),
        unresolved_semantic_fields=mapping.unresolved_fields,
        deterministic_mapping_summary=status,
    )


def _abstract_flags(values: list[str], unique: int, ratio: float) -> tuple[str, ...]:
    lowered = [value.lower() for value in values]
    flags: set[str] = set()
    if values and ratio >= 0.9:
        flags.add("mostly_unique")
    if values and unique <= max(2, len(values) // 5):
        flags.add("low_cardinality")
    if values and unique < len(values):
        flags.add("repeated_categorical")
    checks: dict[str, Callable[[str], bool]] = {
        "image_extension_like": lambda value: bool(_IMAGE_SUFFIX.search(value)),
        "uuid_like": lambda value: bool(_UUID.match(value)),
        "tcga_like": lambda value: bool(_TCGA.match(value)),
        "integer_like": lambda value: bool(_INTEGER.match(value)),
        "decimal_like": lambda value: bool(_DECIMAL.match(value)),
        "path_separator_like": lambda value: "/" in value or "\\" in value,
    }
    for name, check in checks.items():
        if values and all(check(value) for value in values):
            flags.add(name)
    if lowered and set(lowered).issubset(_SPLITS):
        flags.add("split_value_like")
    if "integer_like" in flags or "decimal_like" in flags:
        flags.add("numeric_like")
    return tuple(sorted(flags))


def request_ai_schema_proposal(
    request: AiSchemaRequest,
    config: AuditConfig,
    *,
    client: _OpenAIClient | None = None,
) -> AiSchemaProposal:
    """Request one non-streaming structured proposal through the OpenAI SDK."""

    if client is None:
        client = _create_openai_client(config)
    try:
        responses = client.responses
        response = responses.parse(
            model=config.ai_model,
            input=[
                {"role": "system", "content": _INSTRUCTIONS},
                {"role": "user", "content": canonical_request_json(request)},
            ],
            text_format=_ProviderProposal,
            timeout=config.ai_request_timeout_seconds,
        )
        parsed = response.output_parsed
    except (ValidationError, ValueError, TypeError, AttributeError) as exc:
        raise AiResponseValidationError("AI structured response was malformed") from exc
    except Exception as exc:
        name = type(exc).__name__.lower()
        if "auth" in name or "permission" in name or "api_key" in str(exc).lower():
            raise AiCredentialError("AI provider authentication failed") from exc
        raise AiRequestError("AI schema request failed") from exc
    try:
        provider = (
            parsed
            if isinstance(parsed, _ProviderProposal)
            else _ProviderProposal.model_validate(parsed)
        )
        if not provider.proposed_fields:
            raise ValueError("empty proposal")
    except (ValidationError, ValueError) as exc:
        raise AiResponseValidationError(
            "AI structured response was empty or invalid"
        ) from exc
    normalized = json.dumps(
        [item.model_dump(mode="json") for item in provider.proposed_fields],
        sort_keys=True,
        separators=(",", ":"),
    )
    output_digest = hashlib.sha256(normalized.encode()).hexdigest()
    request_digest = ai_request_digest(request)
    proposal_id = (
        "aip-"
        + hashlib.sha256(f"{request_digest}:{output_digest}".encode()).hexdigest()[:24]
    )
    return AiSchemaProposal(
        proposal_id=proposal_id,
        model=config.ai_model,
        response_id=getattr(response, "id", None),
        request_digest=request_digest,
        proposed_fields=provider.proposed_fields,
        model_output_digest=output_digest,
        generated_at=datetime.now(UTC),
    )


def validate_ai_schema_proposal(
    proposal: AiSchemaProposal,
    pair: LoadedManifestPair,
    deterministic_mappings: ManifestSchemaMappings,
) -> ValidatedAiSchemaProposal:
    """Independently validate proposal fields without applying any of them."""

    validations = []
    used_train = _used_columns(deterministic_mappings.train)
    used_test = _used_columns(deterministic_mappings.test)
    seen_fields: set[str] = set()
    supported = {field.value for field in SEMANTIC_FIELDS}
    for item in sorted(
        proposal.proposed_fields, key=lambda value: value.semantic_field
    ):
        codes: list[str] = []
        messages: list[str] = []
        field = item.semantic_field
        existing_train = getattr(deterministic_mappings.train, field, None)
        existing_test = getattr(deterministic_mappings.test, field, None)
        if field not in supported:
            codes.append("unsupported_semantic_field")
            existing_train = None
            existing_test = None
        elif field in seen_fields:
            codes.append("duplicate_semantic_field")
        elif (
            existing_train is not None
            and existing_test is not None
            and (
                existing_train.source is not SchemaMappingSource.unresolved
                or existing_test.source is not SchemaMappingSource.unresolved
            )
        ):
            codes.append("protected_existing_mapping")
        train_column = _resolve_column(
            pair.train, item.train_source_column, codes, "train"
        )
        test_column = _resolve_column(pair.test, item.test_source_column, codes, "test")
        if item.confidence < AI_MIN_CONFIDENCE:
            codes.append("confidence_below_threshold")
        if train_column and normalize_header(train_column) in used_train:
            codes.append("train_source_reuse")
        if test_column and normalize_header(test_column) in used_test:
            codes.append("test_source_reuse")
        accepted = not codes
        if accepted:
            used_train.add(normalize_header(train_column or ""))
            used_test.add(normalize_header(test_column or ""))
            codes.append("validated_ai_mapping")
            messages.append(
                "Field came from a deterministically validated AI proposal."
            )
        else:
            messages.extend(code.replace("_", " ") for code in codes)
        validations.append(
            AiFieldValidation(
                semantic_field=field,
                accepted=accepted,
                train_source_column=train_column or item.train_source_column,
                test_source_column=test_column or item.test_source_column,
                confidence=item.confidence,
                validation_codes=tuple(codes),
                validation_messages=tuple(messages),
            )
        )
        seen_fields.add(field)
    accepted_fields = tuple(v.semantic_field for v in validations if v.accepted)
    rejected_fields = tuple(v.semantic_field for v in validations if not v.accepted)
    return ValidatedAiSchemaProposal(
        proposal=proposal,
        field_validations=tuple(validations),
        accepted_fields=accepted_fields,
        rejected_fields=rejected_fields,
        fully_valid=not rejected_fields,
    )


def _resolve_column(
    manifest: LoadedManifest, requested: str | None, codes: list[str], side: str
) -> str | None:
    if requested is None:
        codes.append(f"{side}_column_missing")
        return None
    exact = [header for header in manifest.original_headers if header == requested]
    matches = exact or [
        original
        for original, normalized in zip(
            manifest.original_headers, manifest.normalized_headers, strict=True
        )
        if normalized == normalize_header(requested)
    ]
    if not matches:
        codes.append(f"{side}_column_absent")
        return None
    if len(matches) != 1:
        codes.append(f"{side}_column_ambiguous")
        return None
    return matches[0]


def _used_columns(mapping: SchemaMapping) -> set[str]:
    return {
        normalize_header(item.source_column)
        for field in SEMANTIC_FIELDS
        if (item := getattr(mapping, field.value)).source_column is not None
    }


def apply_validated_ai_schema_proposal(
    deterministic_mappings: ManifestSchemaMappings,
    validated: ValidatedAiSchemaProposal,
    *,
    accept: bool,
) -> ManifestSchemaMappings:
    """Apply technically valid fields only after the explicit acceptance control."""

    if not accept:
        return deterministic_mappings
    train_updates: dict[str, SchemaFieldMapping] = {}
    test_updates: dict[str, SchemaFieldMapping] = {}
    for result in validated.field_validations:
        if not result.accepted:
            continue
        for updates, column in (
            (train_updates, result.train_source_column),
            (test_updates, result.test_source_column),
        ):
            updates[result.semantic_field] = SchemaFieldMapping(
                semantic_field=result.semantic_field,
                source_column=column,
                source=SchemaMappingSource.validated_ai_mapping,
                confidence=result.confidence,
                validation_messages=(
                    "Field came from a deterministically validated and explicitly "
                    "accepted AI proposal.",
                ),
            )
    train = _updated_mapping(deterministic_mappings.train, train_updates)
    test = _updated_mapping(deterministic_mappings.test, test_updates)
    return deterministic_mappings.model_copy(update={"train": train, "test": test})


def _updated_mapping(
    mapping: SchemaMapping, updates: dict[str, SchemaFieldMapping]
) -> SchemaMapping:
    values = {
        field.value: updates.get(field.value, getattr(mapping, field.value))
        for field in SEMANTIC_FIELDS
    }
    values["unresolved_fields"] = tuple(
        field.value
        for field in SEMANTIC_FIELDS
        if values[field.value].source is SchemaMappingSource.unresolved
    )
    return SchemaMapping.model_validate(values)
