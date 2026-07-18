# Scientific Method

## Factual relationship versus policy violation

A detector emits a factual relationship: an observed, provenance-backed relationship between records or files. A factual relationship becomes a confirmed disallowed overlap only after policy evaluation under an explicit `SplitPolicy`.

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
