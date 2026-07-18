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


## Deterministic schema interpretation

Task 4 keeps schema interpretation separate from scientific evidence. Mapping results describe which source columns appear to represent semantic fields, but they are not overlap findings and must not be treated as patient, specimen, slide, institution, or file relationships.

Mapping precedence is deterministic: direct `AuditConfig` semantic-column overrides are applied first, explicit YAML or JSON schema-map entries second, deterministic header/value scoring third, and unresolved ambiguity last. Explicit mappings receive confidence `1.0` only after validation against actual manifest columns; they are not trusted blindly.

Deterministic scoring uses documented signals: exact canonical header matches, strong aliases, weak aliases, limited token-overlap support, and conservative value-pattern support for image-like paths, split-like partition values, categorical labels, unique record identifiers, repeated identifiers, and categorical institution values. The mapper does not inspect external files or databases.

A deterministic mapping is accepted only when it meets the minimum confidence threshold and exceeds the next candidate by the configured ambiguity gap. Otherwise the semantic field remains unresolved with ranked alternatives and validation messages. This preserves ambiguity rather than selecting a column merely because it sorts first.
