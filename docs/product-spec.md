# Slide-of-Life Product Specification

## Target users

Slide-of-Life targets computational-pathology researchers, benchmark maintainers, dataset curators, and scientific developers responsible for train/test partition integrity.

## User problem

Pathology datasets can contain related samples across partitions through shared patients, specimens, slides, duplicated files, duplicated pixels, institutional provenance, or ambiguous metadata. Users need deterministic evidence that separates observed relationships from policy decisions.

## Milestone-one scope

Milestone one now includes the repository foundation, typed domain models, deterministic configuration contracts, the default `SplitPolicy` profile, deterministic CSV manifest ingestion contracts with source provenance, deterministic semantic schema mapping, canonical record construction, stable record IDs, strict TCGA parsing, and lineage conflict reporting. Schema mapping includes explicit YAML/JSON maps, direct semantic-column overrides, per-field confidence/source metadata, ranked alternatives, unresolved ambiguity, and pair-level train/test consistency checks. Record construction includes explicit source IDs, content-derived fingerprint IDs, duplicate-row suffixes, raw and normalized digests, direct-versus-derived lineage reconciliation, and partition warnings. It implements deterministic factual identifier overlap detection, image path auditing, byte and canonical-pixel fingerprinting, exact image duplicate facts, perceptual image-similarity candidates, and typed input-quality findings. It implements deterministic relationship graph materialization, explicit SplitPolicy evaluation, evaluated findings, deterministic repair proposal contracts, reporting writers, the operational audit CLI, optional privacy-bounded AI schema assistance, and reusable GitHub Action packaging. It also implements the deterministic synthetic demonstration fixture and end-to-end expected-result contract.

## Standard audit workflow

The planned workflow is:

1. Load user-provided train and test manifests.
2. Interpret schema mappings with deterministic rules or explicit user maps.
3. Construct canonical records and reconcile direct/derived lineage metadata.
4. Run deterministic factual relationship detectors.
5. Build a deterministic relationship graph that materializes factual evidence.
6. Convert `FactualFinding` records into `EvaluatedFinding` records by evaluating them under a `SplitPolicy`.
7. Optionally create deterministic repair proposals requiring researcher review.
8. Emit machine-readable and human-readable reports.

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

## Implemented demonstration fixture

The Task 9 fixture uses fictional identifiers and generated pixels, explicit schema
mapping, exact identifier/byte/pixel relationships, an institution warning, a
similarity review candidate, an input-quality issue, clean controls, and an optional
repair proposal. Its smoke test requires reports before expected exit code 2.

## Submission enhancements

Potential submission enhancements include polished HTML reports, reproducibility metadata, explicit warnings, and clear policy summaries.

## Deferred research capabilities

Deferred capabilities include broader institutional provenance modeling, advanced image similarity review queues and optional GPT-5.6 assistance for redacted schema interpretation.

## Success criteria

Success means users can install the package, run documented developer checks, inspect accurate milestone documentation, invoke `slide-of-life --help` and `slide-of-life --version`, load two CSV manifests into deterministic typed ingestion contracts, produce typed deterministic schema mappings, construct canonical records, run factual detectors, materialize relationship graphs, evaluate findings under `SplitPolicy`, generate deterministic repair proposals, optionally request privacy-bounded AI schema proposals with deterministic validation and explicit acceptance, and invoke the same pipeline through the Task 11 composite GitHub Action. Task 11 Action packaging and Task 12 Agent Skill packaging are implemented. Release-readiness packaging and clean artifact installation validation are implemented. Actual PyPI publication and a GitHub release remain pending, and a repository rename remains optional/pending. Broader scientific research capabilities, plugin-directory submission, richer report UI, and extended provenance research remain separate future work.

## Product-hardening status

The public product, distribution, and primary CLI are renamed to Slide-of-Life,
while the `slidelineage` import package and deprecated CLI alias remain compatible.
Local process-only AI credential onboarding is implemented. The GitHub Action
remains noninteractive and AI-disabled by default. Task 12 skill packaging is implemented as repository guidance around the existing CLI; it does not publish a plugin or release.
