# SlideLineage Repository Contract

## Project purpose

SlideLineage is a local scientific developer tool for auditing train/test partition relationships in computational-pathology datasets. Its scientific architecture is deterministic-first: factual relationship detection must be performed by deterministic code, then evaluated under an explicit `SplitPolicy`, followed by optional repair proposals and optional GPT-5.6 assistance only for schema interpretation.

Milestone one concerns data provenance and partition validity. It excludes diagnosis, prognosis, treatment advice, biological interpretation, and clinical claims.

## Scientific integrity rules

Future implementation must:

- Separate factual detector output from `SplitPolicy` evaluation. Detector-stage contracts use `FactualFinding`; policy-evaluated contracts use `EvaluatedFinding` with an explicit `PolicyOutcome` and reason.
- Classify exact relationships separately from similarity candidates.
- Avoid inferring patient, specimen, slide, or institution identity from perceptual similarity.
- Preserve evidence provenance for every finding.
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
