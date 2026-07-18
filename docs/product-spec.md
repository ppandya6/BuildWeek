# SlideLineage Product Specification

## Target users

SlideLineage targets computational-pathology researchers, benchmark maintainers, dataset curators, and scientific developers responsible for train/test partition integrity.

## User problem

Pathology datasets can contain related samples across partitions through shared patients, specimens, slides, duplicated files, duplicated pixels, institutional provenance, or ambiguous metadata. Users need deterministic evidence that separates observed relationships from policy decisions.

## Milestone-one scope

Milestone one now includes the repository foundation, typed domain models, deterministic configuration contracts, the default `SplitPolicy` profile, deterministic CSV manifest ingestion contracts with source provenance, and deterministic semantic schema mapping. Schema mapping includes explicit YAML/JSON maps, direct semantic-column overrides, per-field confidence/source metadata, ranked alternatives, unresolved ambiguity, and pair-level train/test consistency checks. It does not implement record-ID generation, TCGA parsing, overlap detection, image analysis, graph construction algorithms, policy evaluation execution, repair algorithms, reporting writers, an operational audit CLI, demos, or GPT integration.

## Standard audit workflow

The planned workflow is:

1. Load user-provided train and test manifests.
2. Interpret schema mappings with deterministic rules or explicit user maps.
3. Run deterministic factual relationship detectors.
4. Build a relationship graph.
5. Convert `FactualFinding` records into `EvaluatedFinding` records by evaluating them under a `SplitPolicy`.
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

Deferred capabilities include record-ID generation, TCGA parsing, overlap detection, broader institutional provenance modeling, advanced image similarity review queues, report writing, repair execution, an operational audit CLI, and optional GPT-5.6 assistance for redacted schema interpretation.

## Success criteria

Success means users can install the package, run documented developer checks, inspect accurate milestone documentation, invoke `slidelineage --help` and `slidelineage --version`, and load two CSV manifests into deterministic typed ingestion contracts, and produce typed deterministic schema mappings before later pipeline implementation begins. Task 4 does not make record-ID generation, detectors, report writing, or the audit command operational.
