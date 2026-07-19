---
name: slide-of-life
description: Guide local, deterministic Slide-of-Life train/test partition audits and explain their reports. Use for requests to audit manifests for leakage or shared patients/specimens/slides, inspect pathology dataset partitions, generate a review-required repair proposal, explain a Slide-of-Life report, map unusual manifest columns, run the CLI, or integrate its GitHub Action. Do not use for diagnosis, pathology interpretation, treatment advice, generic image analysis, model-performance evaluation without partition auditing, or automatic manifest replacement.
---

# Slide-of-Life Dataset Audit

Wrap the installed `slide-of-life` CLI; never duplicate its audit logic, calculate findings independently, or invent results. Require local command/file access and Python 3.11+ with `slide-of-life` installed. The skill grants no data access: use only files the user has made available.

## Gather inputs

Require only the train and test manifest paths. Ask one minimal question if either is missing. Treat these as optional: image directory, schema map, output directory, policy profile, repair, institution grouping, target train fraction, image thresholds, AI schema assistance, and acceptance of validated AI mappings. Never ask for an API key in chat.

Read [input preparation](references/input-preparation.md) when paths or mapping are unclear. Read [audit workflow](references/audit-workflow.md) before constructing a non-basic command.

## Run the workflow

1. Confirm both manifest files exist and resolve to distinct files.
2. Inspect headers only; do not expose full rows unnecessarily. Never infer exact mappings without verifying actual headers.
3. Determine whether deterministic mapping plus an optional manual schema map is sufficient. Prefer a manual map when ambiguity remains.
4. Confirm whether images, repair, institution grouping, custom policy/thresholds, or optional AI were explicitly requested.
5. Confirm the output directory. Do not add `--force` unless overwriting was authorized.
6. Construct the command as an argument list, using the public `slide-of-life audit` interface. Do not interpolate user paths into a shell command string.
7. Present the intended command before execution when confirmation is appropriate, then run it locally.
8. Interpret the exit code and inspect which artifacts actually exist.
9. Summarize the typed reports; do not derive findings from raw data yourself.

Do not manually inspect image contents when the deterministic CLI can compare them. Use the platform-specific command patterns in [audit workflow](references/audit-workflow.md) and the walkthroughs in [basic audit](examples/basic-audit.md) or [repair audit](examples/repair-audit.md).

## Preserve the reasoning layers

Keep these layers separate in every explanation:

1. **Factual detection:** describe computed patient, specimen, or slide overlap; exact byte or pixel duplication; perceptual-similarity candidates; input-quality findings; and institution relationships as observed relationships with provenance. Similarity is a review candidate, never identity proof.
2. **Policy evaluation:** explain that the named `SplitPolicy` separately classifies each fact as a violation, review item, allowed, or informational, with a reason. Never rewrite a policy outcome as the raw fact.
3. **Repair proposal:** describe deterministic reassignment output only as a proposed partition requiring researcher review. Never apply, commit, or substitute it for source manifests; never claim it guarantees scientific validity.

Read [report interpretation](references/report-interpretation.md) before explaining artifacts or findings.

## Handle exit codes

- **0:** audit completed and no policy violations were found.
- **1:** input, configuration, execution, or artifact-writing failure. Do not claim an audit result exists; inspect the concise error and suggest focused remediation without dumping a traceback unless debugging was requested.
- **2:** audit completed, wrote reports, and found policy violations. This is not a crash. Confirm reports exist, summarize the violation count, and direct the user to `report.html`.

For failures and edge cases, read [troubleshooting](references/troubleshooting.md).

## Protect data and credentials

Keep deterministic auditing local. Do not paste raw manifest rows into external prompts unnecessarily, send image bytes to OpenAI, or send image paths outside the local workflow. Never request, print, summarize, or store API keys. AI stays disabled unless explicitly requested and can only propose schema mappings; it cannot create findings, policy outcomes, or repair decisions. Read [AI schema assistance](references/ai-schema-assistance.md) before using either AI flag.

## Summarize a completed audit

Use this structure, omitting unavailable details rather than guessing:

1. **Audit result:** completed status, exit code, policy profile, total findings, violation count, review count.
2. **Most important factual relationships:** group by finding type without exposing raw identifiers unless needed and appropriate.
3. **Policy outcomes:** state which facts became violations or review items and the recorded policy reasons.
4. **Input-quality limitations:** list missing images, unresolved fields, truncated comparisons, and other disclosed limits.
5. **Repair proposal:** state whether requested and whether `repair_proposal.csv` actually exists; reiterate review requirements.
6. **Artifacts:** list actual paths for `report.html`, `report.json`, `findings.csv`, and, only if present, `repair_proposal.csv`.
7. **Scope:** similarity is not identity proof; the report does not prove contamination-free data; repair requires researcher review; no clinical interpretation occurred.

For CI integration, read [the GitHub Action example](examples/github-action.md). Mention the old `slidelineage` command only as deprecated compatibility guidance in troubleshooting.
