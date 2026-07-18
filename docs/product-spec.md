# SlideLineage Product Specification

## Target users

SlideLineage targets computational-pathology researchers, benchmark maintainers, dataset curators, and scientific developers responsible for train/test partition integrity.

## User problem

Pathology datasets can contain related samples across partitions through shared patients, specimens, slides, duplicated files, duplicated pixels, institutional provenance, or ambiguous metadata. Users need deterministic evidence that separates observed relationships from policy decisions.

## Milestone-one scope

Milestone one establishes the repository foundation only: metadata, packaging, documentation, tooling, CI, CLI help/version output, and foundation tests. It does not implement ingestion, detectors, graph construction, policy evaluation, repair, reporting, demos, or AI integration.

## Standard audit workflow

The planned workflow is:

1. Load user-provided manifests.
2. Interpret schema mappings.
3. Run deterministic factual relationship detectors.
4. Build a relationship graph.
5. Evaluate factual relationships under a `SplitPolicy`.
6. Emit machine-readable and human-readable reports.

## Optional repair workflow

A later `--repair` workflow may generate partition reassignment proposals. These outputs must be labeled as proposals requiring researcher review, not automatic corrections.

## Planned outputs

- `report.json`
- `report.html`
- `findings.csv`
- `repair_proposal.csv`, generated only with `--repair`

## Default policy profile

`patient_independent_pathology_benchmark`:

```yaml
patient_disjoint: true
specimen_disjoint: true
slide_disjoint: true
exact_byte_content_disjoint: true
exact_pixel_content_disjoint: true
institution_disjoint: false
similarity_candidates_fail_audit: false
```

## Core demonstration requirements

A future demonstration should use fictional identifiers and generated pixels, show deterministic evidence provenance, distinguish exact overlaps from similarity candidates, and avoid clinical claims.

## Submission enhancements

Potential submission enhancements include polished HTML reports, reproducibility metadata, explicit warnings, and clear policy summaries.

## Deferred research capabilities

Deferred capabilities include richer schema interpretation, broader institutional provenance modeling, advanced image similarity review queues, and optional GPT-5.6 assistance for redacted schema interpretation.

## Success criteria

Success means users can install the package, run documented developer checks, inspect accurate milestone documentation, and invoke `slidelineage --help` and `slidelineage --version` before later pipeline implementation begins.
