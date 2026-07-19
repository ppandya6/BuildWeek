# Report interpretation

## Artifacts

- `report.html`: primary human-readable report; direct the user here after exit 0 or 2.
- `report.json`: typed machine-readable audit record and the safest source for structured summaries.
- `findings.csv`: one row per policy-evaluated finding.
- `repair_proposal.csv`: optional proposed reassignment, generated only when repair was requested and a proposal was produced. Check existence before mentioning it as an artifact.

## Three-layer interpretation

First group factual findings by detector relationship: patient, specimen, slide, exact bytes, exact pixels, perceptual similarity candidate, institution, or input quality. Preserve evidence provenance and do not infer lineage from similarity.

Then report the explicit policy profile, each recorded outcome (violation, review item, allowed, informational), and its policy reason. A violation is a policy judgment about a separate fact.

Finally describe repair output, if present, as a deterministic proposed partition requiring researcher review. It does not modify input manifests or guarantee scientific validity.

## Summary template

### Audit result
Completed status; exit code; policy profile; total findings; violations; review items.

### Most important factual relationships
Counts grouped by factual type. Avoid raw record identifiers unless necessary and appropriate.

### Policy outcomes
Facts classified as violations or review items and their recorded reasons.

### Input-quality limitations
Unresolved schema fields, failed image evidence, missing images, resource-limited or truncated comparisons, and other report disclosures.

### Repair proposal
Whether requested; whether generated; actual path if present; review requirement.

### Artifacts
Only verified paths.

### Scope
Similarity is a review candidate, not proof of identity. The audit does not prove the dataset is contamination-free. Repair is not automatically applied. No clinical interpretation was performed.
