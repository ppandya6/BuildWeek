# Typed Report Contracts

The report schema is represented by provisional typed Pydantic contracts. The contracts define serialization semantics for later stages, but no report writer or audit pipeline is operational yet.

## Planned output files

- `report.json`: future machine-readable serialization of `AuditReport`.
- `report.html`: future human-readable rendering from `AuditReport`.
- `findings.csv`: future tabular export of factual and evaluated findings.
- `repair_proposal.csv`: future export of `RepairProposal`, generated only with `--repair`.

## Top-level `AuditReport` fields

- `schema_version`: literal `1.0.0`.
- `tool`: `ToolMetadata` with tool name and package version.
- `run`: `RunMetadata` with run ID, timezone-aware timestamps, and command tuple.
- `inputs`: `InputSummary` with source manifest summaries, optional image root, and total record count.
- `configuration`: `AuditConfig`, including deterministic configuration digest behavior.
- `policy`: `SplitPolicy`, beginning with `patient_independent_pathology_benchmark`.
- `schema_mapping`: optional `SchemaMapping` with per-field provenance.
- `summary`: `FindingSummary`.
- `factual_findings`: immutable sequence of `FactualFinding` detector-stage records without policy outcomes.
- `evaluated_findings`: immutable sequence of `EvaluatedFinding` records with `PolicyOutcome` and policy reason.
- `relationship_graph`: `RelationshipGraph` serialization contract.
- `policy_evaluation`: `PolicyEvaluationSummary`.
- `repair_proposal`: optional `RepairProposal` requiring researcher review.
- `reproducibility`: `ReproducibilityMetadata`.
- `warnings`: immutable warning strings.

## Contract status

The typed models prohibit arbitrary extra fields and use immutable tuples where practical. Serialization is deterministic when callers provide canonical ordering. Later stages may add report writers and typed model migrations, but they must preserve the factual-versus-evaluated finding distinction.


## Ingestion provenance contracts

Task 3 adds implemented intermediate contracts for deterministic CSV loading before schema mapping. `RawManifestRow` records each zero-based source data row with the source manifest ID, assigned partition, original-header-keyed raw values, and normalized-header-keyed minimally cleaned values. `LoadedManifest` records the `SourceManifest`, original header tuple, normalized header tuple, loaded rows, deterministic encoding label, newline-style metadata, and nonblank warnings such as short-row notices. `LoadedManifestPair` contains the assigned train and test manifests and validates distinct manifest IDs, train/test partition assignment, and distinct source files.

These ingestion contracts are provenance inputs for later report models. They are not detector findings, do not include schema interpretation, do not generate canonical record IDs, and do not evaluate `SplitPolicy`.

## Schema mapping contracts

Task 4 adds implemented typed contracts for deterministic schema mapping. `SchemaMapping` contains one `SchemaFieldMapping` for each supported semantic field with the selected original source column when resolved, the mapping source, confidence, ranked alternatives, and validation messages. `ManifestSchemaMappings` carries train and test mappings plus pair-level mismatch status and validation messages.

These contracts describe schema interpretation only. They do not create `FactualFinding` objects, canonical record IDs, overlap evidence, graph edges, policy outcomes, repair outputs, or report files.
