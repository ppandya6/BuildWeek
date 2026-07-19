"""Network-free tests for optional AI schema interpretation."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from slidelineage.ai_schema import (
    _OpenAIClient,
    ai_request_digest,
    apply_validated_ai_schema_proposal,
    build_ai_schema_request,
    canonical_request_json,
    request_ai_schema_proposal,
    validate_ai_schema_proposal,
)
from slidelineage.config import AuditConfig
from slidelineage.errors import (
    AiRequestError,
    AiResponseValidationError,
    AiSdkUnavailableError,
)
from slidelineage.ingest import load_manifest
from slidelineage.models import (
    AiProposedFieldMapping,
    AiSchemaProposal,
    LoadedManifestPair,
    Partition,
    SchemaMappingSource,
)
from slidelineage.schema_mapping import map_manifest_pair


def _pair(tmp_path: Path) -> tuple[LoadedManifestPair, AuditConfig]:
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    train_path.write_text(
        "image_path,Subject Code,other\na.svs,TCGA-AA-0001,x\n,TCGA-AA-0002,x\n",
        encoding="utf-8",
    )
    test_path.write_text(
        "image_path,Case Key,other\nb.svs,TCGA-BB-0003,y\n,TCGA-BB-0004,y\n",
        encoding="utf-8",
    )
    pair = LoadedManifestPair(
        train=load_manifest(train_path, Partition.train, "train_manifest"),
        test=load_manifest(test_path, Partition.test, "test_manifest"),
    )
    config = AuditConfig(
        train_manifest=train_path,
        test_manifest=test_path,
        output_dir=tmp_path / "out",
        ai_schema_map=True,
    )
    return pair, config


def _proposal(request_digest: str, *fields: AiProposedFieldMapping) -> AiSchemaProposal:
    from datetime import UTC, datetime

    return AiSchemaProposal(
        proposal_id="aip-test",
        model="gpt-5.6",
        request_digest=request_digest,
        proposed_fields=fields,
        model_output_digest="0" * 64,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class _FakeStructuredResponse:
    def __init__(self, parsed: object) -> None:
        self.id: str | None = "resp-1"
        self.output_parsed = parsed


class _FakeResponses:
    def __init__(self, parsed: object) -> None:
        self.parsed = parsed
        self.calls = 0

    def parse(
        self,
        *,
        model: str,
        input: list[dict[str, str]],
        text_format: type[BaseModel],
        timeout: float,
    ) -> _FakeStructuredResponse:
        self.calls += 1
        return _FakeStructuredResponse(self.parsed)


class _FakeClient:
    def __init__(self, parsed: object) -> None:
        self.responses = _FakeResponses(parsed)


def test_request_summary_is_aggregate_only_and_stable(tmp_path: Path) -> None:
    pair, config = _pair(tmp_path)
    mappings = map_manifest_pair(pair, config)
    request = build_ai_schema_request(pair.train, pair.test, mappings, config)
    payload = canonical_request_json(request)
    decoded = json.loads(payload)
    assert decoded["train_summary"]["row_count"] == 2
    assert decoded["train_summary"]["columns"][0]["missing_count"] == 1
    assert "Subject Code" in payload
    assert "tcga_like" in payload
    for forbidden in ("TCGA-AA-0001", "a.svs", str(tmp_path), "raw_values"):
        assert forbidden not in payload
    assert payload == canonical_request_json(request)
    assert ai_request_digest(request) == ai_request_digest(request)


def test_fake_structured_client_returns_proposal_without_raw_response(
    tmp_path: Path,
) -> None:
    pair, config = _pair(tmp_path)
    request = build_ai_schema_request(
        pair.train, pair.test, map_manifest_pair(pair, config), config
    )
    parsed = {
        "proposed_fields": [
            {
                "semantic_field": "patient_id",
                "train_source_column": "Subject Code",
                "test_source_column": "Case Key",
                "confidence": 0.91,
                "rationale_code": "cross_manifest_header_alignment",
                "requires_review": True,
            }
        ]
    }
    fake: _OpenAIClient = _FakeClient(parsed)
    proposal = request_ai_schema_proposal(request, config, client=fake)
    assert proposal.response_id == "resp-1"
    assert proposal.proposed_fields[0].test_source_column == "Case Key"
    assert "output_parsed" not in proposal.model_dump_json()


def test_none_client_constructs_sdk_client_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocked_openai_constructor_boundary: None,
) -> None:
    pair, config = _pair(tmp_path)
    request = build_ai_schema_request(
        pair.train, pair.test, map_manifest_pair(pair, config), config
    )
    parsed = {
        "proposed_fields": [
            {
                "semantic_field": "patient_id",
                "train_source_column": "Subject Code",
                "test_source_column": "Case Key",
                "confidence": 0.91,
                "rationale_code": "cross_manifest_header_alignment",
                "requires_review": True,
            }
        ]
    }
    fake = _FakeClient(parsed)
    constructor_calls: list[dict[str, object]] = []

    def fake_openai(**kwargs: object) -> _FakeClient:
        constructor_calls.append(kwargs)
        return fake

    fake_module = SimpleNamespace(OpenAI=fake_openai)
    monkeypatch.setattr(
        "slidelineage.ai_schema.import_module", lambda name: fake_module
    )
    proposal = request_ai_schema_proposal(request, config, client=None)

    assert constructor_calls == [
        {"timeout": config.ai_request_timeout_seconds, "max_retries": 0}
    ]
    assert fake.responses.calls == 1
    assert proposal.response_id == "resp-1"
    assert proposal.proposed_fields[0].test_source_column == "Case Key"


def test_none_client_reports_unavailable_optional_sdk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocked_openai_constructor_boundary: None,
) -> None:
    pair, config = _pair(tmp_path)
    request = build_ai_schema_request(
        pair.train, pair.test, map_manifest_pair(pair, config), config
    )

    def missing_sdk(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("slidelineage.ai_schema.import_module", missing_sdk)
    with pytest.raises(AiSdkUnavailableError, match="pip install"):
        request_ai_schema_proposal(request, config)


def test_live_provider_boundary_is_blocked_by_default(tmp_path: Path) -> None:
    pair, config = _pair(tmp_path)
    request = build_ai_schema_request(
        pair.train, pair.test, map_manifest_pair(pair, config), config
    )
    with pytest.raises(AssertionError, match="live OpenAI client"):
        request_ai_schema_proposal(request, config)


@pytest.mark.parametrize("result", [None, {}, {"proposed_fields": []}])
def test_malformed_or_empty_structured_response_rejected(
    tmp_path: Path, result: object
) -> None:
    pair, config = _pair(tmp_path)
    request = build_ai_schema_request(
        pair.train, pair.test, map_manifest_pair(pair, config), config
    )
    fake = SimpleNamespace(
        responses=SimpleNamespace(
            parse=lambda **_: SimpleNamespace(id=None, output_parsed=result)
        )
    )
    with pytest.raises(AiResponseValidationError):
        request_ai_schema_proposal(request, config, client=fake)


def test_provider_failure_is_chained_and_sanitized(tmp_path: Path) -> None:
    pair, config = _pair(tmp_path)
    request = build_ai_schema_request(
        pair.train, pair.test, map_manifest_pair(pair, config), config
    )

    def fail(**_: object) -> object:
        raise TimeoutError("timed out")

    fake = SimpleNamespace(responses=SimpleNamespace(parse=fail))
    with pytest.raises(AiRequestError, match="request failed"):
        request_ai_schema_proposal(request, config, client=fake)


def test_validation_accepts_existing_normalized_columns_and_application_is_opt_in(
    tmp_path: Path,
) -> None:
    pair, config = _pair(tmp_path)
    mappings = map_manifest_pair(pair, config)
    proposal = _proposal(
        "1" * 64,
        AiProposedFieldMapping(
            semantic_field="patient_id",
            train_source_column="subject_code",
            test_source_column="case_key",
            confidence=0.9,
            rationale_code="header_alias",
        ),
    )
    validated = validate_ai_schema_proposal(proposal, pair, mappings)
    assert validated.accepted_fields == ("patient_id",)
    assert (
        apply_validated_ai_schema_proposal(mappings, validated, accept=False)
        == mappings
    )
    applied = apply_validated_ai_schema_proposal(mappings, validated, accept=True)
    assert applied.train.patient_id.source is SchemaMappingSource.validated_ai_mapping
    assert applied.train.patient_id.confidence == 0.9


def test_validation_rejects_invented_low_confidence_and_protected_fields(
    tmp_path: Path,
) -> None:
    pair, config = _pair(tmp_path)
    mappings = map_manifest_pair(pair, config)
    proposal = _proposal(
        "2" * 64,
        AiProposedFieldMapping(
            semantic_field="patient_id",
            train_source_column="invented",
            test_source_column="Case Key",
            confidence=0.2,
            rationale_code="ambiguous_candidates",
        ),
        AiProposedFieldMapping(
            semantic_field="image_path",
            train_source_column="image_path",
            test_source_column="image_path",
            confidence=0.99,
            rationale_code="header_alias",
        ),
    )
    validated = validate_ai_schema_proposal(proposal, pair, mappings)
    by_field = {item.semantic_field: item for item in validated.field_validations}
    assert "train_column_absent" in by_field["patient_id"].validation_codes
    assert "confidence_below_threshold" in by_field["patient_id"].validation_codes
    assert "protected_existing_mapping" in by_field["image_path"].validation_codes
    assert validated.accepted_fields == ()


def test_duplicate_source_reuse_is_rejected_deterministically(tmp_path: Path) -> None:
    pair, config = _pair(tmp_path)
    mappings = map_manifest_pair(pair, config)
    proposal = _proposal(
        "3" * 64,
        *(
            AiProposedFieldMapping(
                semantic_field=field,
                train_source_column="Subject Code",
                test_source_column="Case Key",
                confidence=0.9,
                rationale_code="header_alias",
            )
            for field in ("patient_id", "specimen_id")
        ),
    )
    validated = validate_ai_schema_proposal(proposal, pair, mappings)
    assert validated.accepted_fields == ("patient_id",)
    assert "train_source_reuse" in validated.field_validations[1].validation_codes
