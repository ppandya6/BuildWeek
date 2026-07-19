# Scientific Method

## Factual relationship versus policy violation

A detector emits a `FactualFinding`: an observed, provenance-backed factual relationship between records or files without a policy result. A factual relationship becomes an `EvaluatedFinding` and may be called a confirmed disallowed overlap only after policy evaluation under an explicit `SplitPolicy`.

## Confirmed identifier relationships

Confirmed patient, specimen, or slide relationships must come from explicit identifiers or validated deterministic parsing rules. They must preserve source fields, normalization steps, and record identifiers.

## Byte-content equality

Byte-content equality is an exact relationship established by deterministic byte hashing of file content. It should be represented separately from identifier relationships and image-derived relationships.

## Canonical pixel-content equality

Canonical pixel-content equality is an exact relationship established after deterministic image decoding and canonicalization. It is distinct from byte equality because different files can encode identical pixels.

## Perceptual similarity candidates

Perceptual hashes may identify review items. Similarity candidates must not be treated as confirmed patient, specimen, slide, or institution identity. They should remain review items unless later confirmed by independent deterministic evidence.

## Institution provenance warnings

Shared institution provenance can be important context. Under the default milestone-one policy it is a warning dimension rather than a disallowed overlap by itself.

## Metadata conflicts

Conflicting metadata should be reported with the source fields and records involved. Conflicts are review items unless deterministic rules establish a confirmed relationship or policy violation.

## Deterministic evidence requirements

Every factual relationship must retain evidence provenance: detector name, source records, source fields or files, normalized values where relevant, and deterministic comparison method. Scientific evidence must not be invented or inferred from GPT output.

## Repair-proposal limitations

Repair outputs are proposals requiring researcher review. They should explain what policy objective they attempt to satisfy and preserve the evidence that motivated each proposed change.

## Non-clinical scope

Slide-of-Life is limited to dataset provenance and partition validity. It must not make diagnosis, prognosis, treatment advice, biological interpretation, or clinical claims.

## Synthetic demonstration fixture

Task 9 provides an illustrative, non-clinical fixture made only from fictional
identifiers and deterministic 64-by-64 RGB constructions. Independent cross-split
pairs plant one accepted patient identifier, one specimen identifier, one slide
identifier, one shared institution, one byte-identical image, one decoded-pixel-
identical PNG/BMP pair, and one perceptually similar but nonidentical pair. A
referenced image is deliberately absent. All other accepted identifiers are unique
controls, so image similarity is never used to infer lineage identity.

Under the default policy the patient, specimen, slide, byte, and pixel findings are
violations; institution reuse is allowed, while similarity and missing-image facts
remain review items. Exit code 2 is therefore an expected completed-audit result.
Repair uses only eligible deterministic relationships and remains a proposal
requiring researcher review.

The fixture demonstrates code paths, not prevalence, benchmark performance,
publication readiness, or split correctness. Its geometric images do not represent
biological material. Reproducibility covers generated filenames and bytes,
manifest ordering, canonical record IDs, finding IDs, and scientific report
content. Run UUIDs and execution timestamps intentionally vary; dependency and
platform versions are disclosed reproducibility boundaries.


## Manifest ingestion provenance

Task 3 establishes the deterministic input boundary for two CSV manifests before any semantic schema mapping. Original source bytes are hashed with SHA-256 before decoding or parsing, so digests reflect byte-order marks and newline differences rather than reconstructed text. The loader retains original headers, canonical normalized headers, user-supplied source paths, assigned partitions, and zero-based data-row provenance for every loaded row.

## Conservative normalization boundary

Header normalization is deterministic and syntactic only: Unicode NFKC normalization, trimming, case folding, separator and punctuation conversion to underscores, underscore collapse, and empty-result rejection. It does not perform semantic aliasing or infer that different column names refer to patient, specimen, slide, institution, image, label, or record identifiers. Exact duplicate headers and distinct headers that collide after normalization are rejected instead of guessed or suffixed.

Cell normalization at ingestion is intentionally minimal. Loaded row values preserve decoded raw strings, except truly absent trailing cells are represented as null. Normalized-header values apply NFKC, surrounding whitespace trimming, and approved missing-token conversion only. Arbitrary labels and paths are not casefolded, and identifier-like comparison normalization is available only as an explicit helper for later stages.

## Deterministic schema mapping

Task 4 implements semantic schema mapping as a deterministic interpretation layer after ingestion and before overlap evidence. Supported semantic fields are exactly `image_path`, `patient_id`, `specimen_id`, `slide_id`, `institution_id`, `class_label`, `partition`, and `source_record_id`. Mapping precedence is direct user column overrides, explicit YAML/JSON schema maps, deterministic header/value scoring, then unresolved ambiguity.

Schema mapping records per-field source, confidence, ranked alternatives, and validation messages. Header evidence remains primary, value evidence is limited to transparent signals such as image-like paths, split-like categories, cardinality, uniqueness, and repeated institution-like values, and contradictory strong headers remain dominant. Mapping results are not factual overlap findings and do not evaluate `SplitPolicy`.

Report writing, the operational CLI, and optional AI schema proposals are implemented.

## Task 10 optional AI schema interpretation

AI runs only after deterministic schema mapping and before canonical record
construction, and only for unresolved semantic fields. The request contains
headers, row/missing/unique counts, rounded cardinality, abstract pattern flags,
and deterministic mapping status. It excludes literal cells, raw rows, manifest
paths and bytes, identifiers, image paths, and image bytes. Headers may themselves
be sensitive, so provider access is explicit opt-in.

An AI response is a proposal, never evidence. A deterministic validator checks
supported fields, real unambiguous columns, protected prior mappings, confidence,
and source reuse independently for each field. Validated fields remain unapplied
unless the researcher supplies the acceptance flag. Provider or SDK failures are
reported accurately; an already viable deterministic audit can continue, while
missing minimum schema coverage remains a focused failure.

Header-based interpretation is inherently limited and provider/model outputs may
vary. Model, provider, request digest, proposal digest, response ID, validation,
application state, and privacy notice are recorded, but raw provider payloads are
not. Detectors, graph construction, policy evaluation, and repair consume only
canonical records and remain deterministic; AI creates none of their outputs.

## Canonical records and TCGA lineage

Task 5 constructs canonical records after schema mapping and before overlap detection. Record ID precedence is explicit mapped `source_record_id`, canonical row fingerprint, then canonical row fingerprint with a deterministic duplicate-occurrence suffix. Explicit source IDs are normalized conservatively for comparison and namespaced with the source manifest ID; duplicate explicit source IDs within one manifest are rejected, while the same source ID across train and test remains constructible for later detectors.

Raw value digests are SHA-256 over canonical JSON containing original header names, decoded cell values, explicit nulls, and deterministic key ordering. Normalized value digests are SHA-256 over canonical JSON containing mapped semantic values and relevant TCGA-derived lineage values. Identical duplicate rows receive the same base fingerprint and then deterministic suffixes; source row number is retained as provenance and used only as a final duplicate-occurrence differentiator, not as scientific identity.

TCGA parsing is strict, case-insensitive, full-string parsing for participant, sample, portion/analyte, and plate/center barcodes. Malformed TCGA-like values raise parse errors; a parse failure must not be treated as proof of unrelatedness. Derived TCGA patient/specimen identifiers are fallback candidates only. If direct and derived lineage values differ after conservative comparison, the direct value is retained in the canonical record, provenance is marked conflicted, both values are preserved in a `LineageConflict`, and future detectors must exclude that conflicted identifier unless explicitly resolved.

A mapped partition column is metadata only. The CLI-assigned train/test partition remains authoritative; conflicting or validation-like partition-column values become deterministic warnings and never alter the assigned partition.

## Task 6 factual detectors and image fingerprints

Task 6 adds detector-stage `FactualFinding` output only. Identifier overlap detection uses accepted, nonconflicted canonical lineage values; conflicted, unresolved, missing, parse-failed, or unsupported-inference values are excluded and absence is never evidence of independence. Patient, specimen, and slide overlaps are confirmed facts when the same normalized value appears in both assigned partitions. Institution overlap remains a factual provenance warning, not a policy result.

Image auditing resolves relative image paths beneath `AuditConfig.images_dir` with `Path.resolve()` containment checks. Paths escaping the image root, missing files, unreadable files, unsupported milestone formats, and oversized unsafe images become typed nonfatal input-quality findings. Milestone image support is limited to Pillow-decoded PNG, JPEG, TIFF, BMP, and WebP first-frame content; whole-slide-image support is not claimed.

Byte equality is SHA-256 over source bytes and establishes only exact file-content duplication. Canonical pixel equality applies EXIF orientation, converts decoded content to RGB, and hashes mode, dimensions, and raw RGB bytes; it can identify identical pixels across different encodings. Perceptual pHash/dHash similarity is probable review evidence only and must never be promoted to patient, specimen, slide, or institution identity.

Exact byte duplicates are emitted as the strongest exact image relation. Pixel duplicate findings are emitted for cross-partition canonical pixel groups with different byte hashes, avoiding redundant exact findings. Perceptual candidates require different byte and pixel digests and both configured pHash and dHash distances at or below threshold.

All eligible train images are compared against all eligible test images only when `eligible_train_count * eligible_test_count <= max_image_pairs`. If the limit is exceeded, no partial perceptual comparison is performed; a resource-limit factual warning records the requested and configured counts, while exact digest grouping can still proceed.

## Task 7 relationship graph, policy evaluation, and repair

The relationship graph materializes evidence already emitted by deterministic detectors. It creates one node per canonical record, expands multi-record factual findings into deterministic pairwise edges, and does not create new patient, specimen, slide, institution, byte, pixel, or similarity evidence. Connected components are graph structure only and must not be interpreted as patient identity.

Policy evaluation derives outcomes from an explicit `SplitPolicy` profile. Patient, specimen, slide, byte-content duplicate, and pixel-content duplicate findings become violations when the corresponding disjointness rule is enabled and allowed overlaps otherwise. Institution overlap is allowed by the default profile while preserving warning-level provenance. Image-similarity candidates are review items by default and only become violations when the explicit similarity-failure policy flag is enabled. Image-read errors, resource limits, and ambiguous categories remain review items.

Repair eligibility is narrower than policy violation status. Only exact or confirmed patient, specimen, slide, byte duplicate, and pixel duplicate violations are eligible by default. Similarity candidates, input-quality findings, and ambiguous findings remain outside repair. Institution grouping is excluded by default and can only be included through the explicit `group_by_institution` option, which intentionally groups by provenance rather than identity and may reduce split flexibility.

Repair components are indivisible connected components over eligible relationships plus singleton components for unlinked records. The greedy assignment sorts components by descending size, descending cross-partition eligible-finding count, then smallest record ID. For each component, assignment candidates are compared lexicographically by absolute target train-count deviation, aggregate label-distribution deviation when labels are complete, moved-record count, then a deterministic train-before-test tie-break. Missing labels skip the label objective and are reported as a tradeoff.

Every repair output is a proposed partition requiring researcher review. Proposals preserve every input record exactly once, disclose impossible exact target fractions, oversized components, material label differences, institution grouping choices, similarity-candidate exclusion, and input-quality limitations without claiming scientific correctness or publication readiness.

## Task 8 deterministic audit orchestration and reports

The operational audit sequence is: validate configuration, prepare the output directory, load train/test manifests, map schemas, construct canonical records, run factual detectors, materialize the relationship graph, load the requested `SplitPolicy`, evaluate factual findings, optionally propose repair, construct a typed report, write artifacts, print a terminal summary, and return the policy exit code.

Reports preserve evidence boundaries. JSON, CSV, and HTML artifacts include factual detector output and policy-evaluated findings without raw manifest rows, image bytes, API keys, or clinical interpretation. Report writers rely on stable model serialization, deterministic ordering supplied by pipeline stages, compact canonical JSON for CSV metrics, and atomic sibling-file replacement where practical.

Exit code `0` means the audit completed without policy violations. Exit code `2` means the audit completed with policy violations and artifacts are still written. Exit code `1` is reserved for input, configuration, execution, or artifact-writing failures.

The HTML report is standalone and text-oriented for image evidence in this milestone. It uses autoescaping, embeds CSS locally, avoids remote assets, and defers thumbnail embedding to later work. The repair CSV remains a proposed partition output requiring researcher review and must not be treated as an automatic correction.

## Task 11 execution through GitHub Actions

The composite GitHub Action changes the execution context, not the scientific
logic: it invokes the same deterministic audit pipeline and validates the same
typed `AuditReport`. CI status reflects the configured policy behavior. Exit 2
can either fail the step or be retained as a successful completed audit with
violations; exit 1 always fails.

Publishing report artifacts does not turn findings into proof of independence or
contamination. Image similarity remains review evidence rather than lineage or
identity evidence, and repairs remain proposals requiring researcher review. Raw
manifest rows remain local to the runner process. AI is disabled by default; only
when explicitly enabled may a GitHub-hosted runner send manifest headers and
privacy-bounded aggregates to the configured provider, never raw rows or images.

## Local AI credential onboarding

AI remains proposal-only, so credential onboarding does not change scientific
authority. Interactive pasted keys are assigned only to the current process
environment, are never persisted, and are used by the normal requested call; no
extra validation call is made. Noninteractive environments, CI, and GitHub Actions
never prompt or open a browser. Missing credentials produce deterministic fallback
when the already mapped image or record identifiers provide minimum coverage and a
report warning records that no AI request occurred. Without minimum coverage the
run fails with a manual schema-map and environment-secret guidance.


## Task 12 Agent Skill orchestration

The packaged Agent Skill changes orchestration and guidance only. It wraps the
existing public CLI and does not change detectors, policies, scientific evidence,
repair logic, or report semantics. Skill-generated summaries must retain the
separation between factual findings, policy outcomes, and review-required repair
proposals and must never invent scientific evidence.
