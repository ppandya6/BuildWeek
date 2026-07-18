# Planned Report Schema

The report schema remains provisional until the typed models stage.

## Planned output files

- `report.json`: machine-readable report containing the complete planned schema.
- `report.html`: human-readable report rendered from the same evidence.
- `findings.csv`: tabular factual findings and policy evaluation rows.
- `repair_proposal.csv`: generated only with `--repair`; contains proposed partition changes requiring researcher review.

## Planned top-level report sections

- Tool metadata: package name, version, and command metadata.
- Run metadata: timestamps, platform details, and invocation summary.
- Inputs: manifests, file roots, and declared partitions.
- Configuration: policy profile and runtime options.
- Schema mapping: resolved column meanings and mapping provenance.
- Summary: counts of records, relationships, confirmed disallowed overlaps, and review items.
- Factual findings: detector outputs before policy evaluation.
- Relationship graph: planned graph nodes and edges representing relationships.
- Policy evaluation: confirmed disallowed overlap decisions under the active `SplitPolicy`.
- Repair proposal: optional proposal details when `--repair` is requested.
- Reproducibility metadata: dependency versions and deterministic settings.
- Warnings: metadata conflicts, institution provenance warnings, and review items.
