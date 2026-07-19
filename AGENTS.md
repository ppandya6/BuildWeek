# Slide-of-Life Repository Contract

## Project purpose

Slide-of-Life is a local scientific developer tool for auditing train/test partition relationships in computational-pathology datasets. Its scientific architecture is deterministic-first: factual relationship detection must be performed by deterministic code, then evaluated under an explicit `SplitPolicy`, followed by optional repair proposals and optional GPT-5.6 assistance only for schema interpretation.

Milestone one concerns data provenance and partition validity. It excludes diagnosis, prognosis, treatment advice, biological interpretation, and clinical claims.

## Scientific integrity rules

Future implementation must:

- Separate factual detector output from `SplitPolicy` evaluation. Detector-stage contracts use `FactualFinding`; policy-evaluated contracts use `EvaluatedFinding` with an explicit `PolicyOutcome` and reason.
- Classify exact relationships separately from similarity candidates.
- Avoid inferring patient, specimen, slide, or institution identity from perceptual similarity.
- Preserve evidence provenance for every finding.
- Preserve raw source provenance through ingestion and later transformations.
- Avoid recomputing manifest digests from decoded text; source manifest digests must come from original bytes.
- Avoid semantic interpretation in the ingestion layer.
- Reject normalized header collisions rather than guessing or suffixing.
- Retain zero-based data-row provenance for manifest rows and downstream records.
- Label repair results as proposals requiring researcher review.
- Avoid clinical claims.
- Avoid invented benchmark results.
- Avoid unsupported scientific conclusions.

## Privacy rules

Future implementation must:

- Keep deterministic auditing local.
- Make API access opt-in.
- Avoid storing API keys.
- Use fictional identifiers and generated pixels in demo fixtures.
- Redact samples before future GPT requests.
- Avoid sending complete manifests or images to GPT-5.6.

## Repository conventions

- Use src-layout packaging. Runtime code lives under `src/slidelineage/`.
- Tests live under `tests/` and should use pytest.
- Documentation lives under `docs/`, with user-facing overview material in `README.md`.
- Prefer `pathlib.Path` over string path manipulation.
- Keep public interfaces typed.
- Use deterministic ordering for emitted records, reports, and tests.
- Use stable serialization for machine-readable outputs.
- Prefer platform-compatible commands that work on Windows, macOS, and Linux.
- Do not create empty future modules. Add modules only when their milestone implements behavior.

## Required commands after future edits

Run these commands after future code or documentation edits:

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest -q
```

When optional AI functionality exists later, also verify installation with:

```bash
python -m pip install -e ".[dev,ai]"
```

## Completion reporting

Future Codex tasks must report:

- Files created or edited.
- Design decisions.
- Commands executed.
- Exact command outcomes.
- Remaining limitations.


## Task 5 lineage detector constraints

Future detectors must use only accepted, nonconflicted canonical identifiers for scientific relationship evidence. Preserve canonical record IDs and lineage conflict IDs in downstream provenance, and never treat TCGA parse failure as proof that records are unrelated. Keep direct manifest values and TCGA-derived evidence separate, including conflicted provenance, and never use source row number as a scientific identity; it is row provenance only.


## Task 6 detector constraints

Future stages must keep policy evaluation separate from factual detectors, avoid promoting image similarity to lineage identity, retain detector versions and configured thresholds in image evidence/metrics, preserve failed image evidence, and avoid partial pair comparisons unless explicitly disclosed.

## Task 7 graph, policy, and repair constraints

Future stages must preserve the separation between factual detector output and policy-evaluated findings, including policy profile names, policy rules, and deterministic policy reasons. Similarity candidates must remain outside deterministic repair. Every repair output must be labeled as a proposed partition requiring researcher review, preserve every input record exactly once, and expose tradeoffs rather than hiding ratio, label, institution-grouping, image-similarity, or input-quality limitations.

## Task 8 audit CLI and reporting constraints

Future reporting work must write policy-violation reports before returning exit code 2, avoid raw-row leakage, preserve HTML autoescaping, preserve output-directory safety, retain deterministic artifact ordering, and keep any future AI-generated content separate from deterministic findings and policy outcomes.

## Task 9 demonstration constraints

Future demo changes must remain entirely synthetic, avoid medical claims, preserve
the expected identifier, byte, pixel, similarity, institution, and input-quality
relationship categories, preserve deterministic generation, keep committed data
small, and update end-to-end tests whenever fixture semantics change.

## Task 10 AI schema-assistance constraints

Future work must keep AI optional, send no raw rows or images, deterministically
validate every semantic-column proposal, and require explicit acceptance before
application. AI must never create findings, policy outcomes, or repair decisions.
Record model/provider provenance, mock every AI call, and keep CI network-free.

## Task 11 GitHub Action constraints

Future action inputs must remain backward compatible. Never interpolate user paths
into shell command strings; preserve CLI exit-code meaning, keep AI opt-in, and
exclude secrets from logs and outputs. Action tests must cover Linux and Windows
path behavior. The action may generate review-required repair proposals but must
never commit repairs or replace source manifests automatically.

## AI credential onboarding constraints

Never log API keys or persist pasted keys. Never prompt in CI, and never open a URL
without confirmation; only the official OpenAI API-key and quickstart URLs may be
used for onboarding. Test every interactive branch through injected functions and
keep deterministic no-AI mode functional.


## Task 12 Agent Skill constraints

The skill must wrap the existing CLI rather than duplicate the audit engine, must
not fabricate findings, and must preserve factual detection, policy evaluation,
and repair-proposal separation. Protect secrets and source data, keep examples
synthetic, keep skill references synchronized with CLI behavior, and keep skill
validation network-free.

## Release constraints

Never publish without explicit approval. Validate built artifacts in clean
environments, keep OpenAI optional, and never place credentials in release
workflows. Preserve runtime/metadata version consistency, inspect source and wheel
contents, and never describe an audit as contamination-free certification.
Never create tags automatically during ordinary tasks, use PyPI API tokens, or
publish before an explicitly approved protected-environment deployment. Require a
green dry run and exact runtime/metadata/tag/changelog agreement. Build artifacts
once and reuse those exact files for validation, attestation, publication, and the
GitHub release. Never upload secrets or raw datasets, and never turn an audit into
a scientific certification claim.
