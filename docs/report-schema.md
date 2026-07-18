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

## Canonical record contracts

Task 5 adds canonical record collection contracts for later reports. `CanonicalManifestRecords` groups source-row ordered `CanonicalRecord` objects with identifier provenance, typed lineage conflicts, and deterministic warnings for one manifest. `CanonicalRecordPair` validates train/test partitions and distinct manifest IDs.

`IdentifierProvenance` records whether a semantic identifier came from a direct manifest value, TCGA derivation, or was unavailable, with status `accepted`, `conflicted`, or `unresolved`. `LineageConflict` preserves direct and derived values, parser version, source column, stable conflict ID, and non-clinical review messaging. These contracts still do not emit overlap findings, graph edges, policy outcomes, repairs, or report files.

## Task 6 image fingerprint and factual detector contracts

`ImageReadStatus` records local image-read outcomes: `resolved`, `missing`, `outside_root`, `unreadable`, `unsafe_image`, and `unsupported_format`.

`ImageFingerprint` is frozen and forbids extras. It preserves record ID, assigned partition, manifest ID, zero-based source row number, original source image path, optional local resolved path, status, byte SHA-256, canonical RGB pixel SHA-256, dimensions, image format, 64-bit lowercase pHash/dHash, optional error code/message, and detector version. Successful fingerprints require hashes, dimensions, format, and resolved path. Failed fingerprints keep error evidence and do not pretend hashes exist.

`ImageFingerprintCollection` stores deterministic fingerprint tuples plus resolved, missing, unreadable, unsafe, all-pairs count, pair-limit, and warning fields.

`FactualDetectionResult` separates `identifier_findings`, exact/probable `image_findings`, and `input_quality_findings`. `all_findings` must equal those categories concatenated in that deterministic order. These findings do not contain `PolicyOutcome`; policy evaluation remains a later stage.

## Task 7 graph, policy, and repair schemas

`RelationshipGraph` contains deterministic `GraphNode` records with record ID, partition, and optional label, plus `GraphEdge` records with ordered source/target record IDs, finding ID, relationship type, confirmation level, and optional policy outcome after evaluation.

`EvaluatedFinding` preserves the detector-stage factual fields and adds `policy_outcome`, `policy_rule`, `policy_reason`, `policy_profile`, and `repair_eligible`. `PolicyEvaluationResult` contains the policy profile, evaluated findings, violation/allowed-overlap/review-item/not-applicable counts, repair-eligible finding IDs, deterministic reasons, and exit code `0` for completed evaluations without violations or `2` when violations exist.

`RepairComponent` records deterministic component IDs derived from sorted record IDs and finding IDs, member record IDs, confirming finding IDs, original partition counts, label counts, optional proposed partition, and conflict status. `RepairDecision` records the proposed partition, moved records, reason, ratio deviation, label-distribution deviation, and deterministic tie-break explanation.

`RepairProposal` is generated only as a proposal requiring researcher review. It records the policy profile, included and excluded relationship types, components, decisions, unresolved conflicts, deterministic tradeoffs, and metrics such as original/proposed/target train fractions, moved-record count, component count, largest component size, and before/after label distributions. Report file writers remain pending.
