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

SlideLineage is limited to dataset provenance and partition validity. It must not make diagnosis, prognosis, treatment advice, biological interpretation, or clinical claims.


## Manifest ingestion provenance

Task 3 establishes the deterministic input boundary for two CSV manifests before any semantic schema mapping. Original source bytes are hashed with SHA-256 before decoding or parsing, so digests reflect byte-order marks and newline differences rather than reconstructed text. The loader retains original headers, canonical normalized headers, user-supplied source paths, assigned partitions, and zero-based data-row provenance for every loaded row.

## Conservative normalization boundary

Header normalization is deterministic and syntactic only: Unicode NFKC normalization, trimming, case folding, separator and punctuation conversion to underscores, underscore collapse, and empty-result rejection. It does not perform semantic aliasing or infer that different column names refer to patient, specimen, slide, institution, image, label, or record identifiers. Exact duplicate headers and distinct headers that collide after normalization are rejected instead of guessed or suffixed.

Cell normalization at ingestion is intentionally minimal. Loaded row values preserve decoded raw strings, except truly absent trailing cells are represented as null. Normalized-header values apply NFKC, surrounding whitespace trimming, and approved missing-token conversion only. Arbitrary labels and paths are not casefolded, and identifier-like comparison normalization is available only as an explicit helper for later stages.

## Deterministic schema mapping

Task 4 implements semantic schema mapping as a deterministic interpretation layer after ingestion and before overlap evidence. Supported semantic fields are exactly `image_path`, `patient_id`, `specimen_id`, `slide_id`, `institution_id`, `class_label`, `partition`, and `source_record_id`. Mapping precedence is direct user column overrides, explicit YAML/JSON schema maps, deterministic header/value scoring, then unresolved ambiguity.

Schema mapping records per-field source, confidence, ranked alternatives, and validation messages. Header evidence remains primary, value evidence is limited to transparent signals such as image-like paths, split-like categories, cardinality, uniqueness, and repeated institution-like values, and contradictory strong headers remain dominant. Mapping results are not factual overlap findings and do not evaluate `SplitPolicy`.

Overlap detection, image analysis, graph construction, policy evaluation execution, repair execution, report writing, operational audit CLI behavior, and GPT integration remain pending.

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
