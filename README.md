# SlideLineage

SlideLineage is a local scientific developer tool planned to audit train/test partition relationships in computational-pathology datasets. It is intended for researchers, benchmark maintainers, data engineers, and scientific software developers who need transparent evidence about partition independence before model training or evaluation.

## Current implementation status

The repository foundation, typed contract layer, and deterministic CSV ingestion boundary exist: packaging, documentation, developer tooling, CI, CLI help/version output, `AuditConfig`, the default `SplitPolicy`, typed domain/report contracts, conservative normalization helpers, source-byte SHA-256 manifest provenance, typed loaded-manifest contracts, deterministic semantic schema mapping, explicit schema overrides, canonical record construction, stable record IDs, strict TCGA parsing, and lineage conflict reporting are implemented. Schema mapping supports explicit YAML/JSON maps, direct column overrides, deterministic header/value scoring, unresolved ambiguity, ranked alternatives, and train/test consistency messages. Canonical record construction preserves source provenance, deterministic digests, direct and TCGA-derived lineage evidence, and partition warnings while avoiding overlap detection. The audit pipeline arrives in later stages. Identifier overlap facts, image path auditing, byte fingerprints, canonical pixel fingerprints, perceptual similarity candidates, and evidence-rich factual findings are now implemented. Relationship graph materialization, policy evaluation, evaluated findings, deterministic repair proposals, report writers, deterministic audit orchestration, standalone HTML/JSON/CSV artifact generation, repair CSV output, and the operational audit CLI are now implemented. Demo generation and OpenAI API integration remain pending.

## Deterministic-first architecture

The planned architecture separates:

1. Deterministic factual relationship detection into `FactualFinding` records.
2. Evaluation under an explicit `SplitPolicy` into `EvaluatedFinding` records.
3. Optional repair proposals requiring researcher review.
4. Optional GPT-5.6 schema interpretation, with deterministic scientific evidence remaining authoritative.

## Planned command example

A later milestone is expected to introduce an audit command similar to:

```bash
slidelineage audit \
  --train examples/demo/train_manifest.csv \
  --test examples/demo/test_manifest.csv \
  --images examples/demo/images \
  --output artifacts/demo-audit
```

This two-manifest command is now operational; the example fixture files arrive in the next demo-fixture task if absent.

## Development installation

```bash
python -m pip install -e ".[dev]"
```

Optional AI dependencies are intentionally separate and should only be installed when later AI-assisted schema interpretation is implemented:

```bash
python -m pip install -e ".[dev,ai]"
```

## Verification commands

Bash:

```bash
ruff format --check .
ruff check .
mypy src
pytest -q
slidelineage --help
slidelineage --version
```

PowerShell:

```powershell
ruff format --check .
ruff check .
mypy src
pytest -q
slidelineage --help
slidelineage --version
```

## Planned output files

Later reporting stages plan to produce:

- `report.json`
- `report.html`
- `findings.csv`
- `repair_proposal.csv`, only when repair proposal generation is requested

Task 8 implements operational report writers; richer demo fixtures remain pending.

## Privacy and scope

Deterministic auditing is planned to run locally. API access must be opt-in, API keys must not be stored in the repository, and future GPT requests must avoid complete manifests or images. SlideLineage is non-clinical software: it must not make diagnosis, prognosis, treatment, biological interpretation, or clinical claims.

## License

SlideLineage is distributed under the MIT License. See [LICENSE](LICENSE).

## Task 7 implementation status

Relationship graph contracts and deterministic materialization now exist for canonical records and factual findings. Explicit `SplitPolicy` evaluation converts factual findings into evaluated findings with policy outcomes, rules, reasons, counts, exit-code semantics, and repair eligibility. Deterministic repair proposals now construct indivisible components, run a typed greedy train/test assignment, preserve all records, and report proposal metrics and tradeoffs for researcher review.

Still pending for later tasks: report writers, the operational audit CLI, synthetic demonstration fixtures, GPT integration, and repository automation.

## Operational audit quick start

Task 8 adds the operational local audit command:

```bash
slidelineage audit \
  --train examples/demo/train_manifest.csv \
  --test examples/demo/test_manifest.csv \
  --images examples/demo/images \
  --output artifacts/demo-audit
```

The demo files in that example are scheduled for the next demo-fixture task if they are absent in the current checkout. For current use, provide your own train/test CSV manifests and optional image root.

The audit writes:

- `report.json`: typed UTF-8 JSON report.
- `report.html`: standalone local HTML report with embedded CSS and escaped content.
- `findings.csv`: one row per evaluated finding.
- `repair_proposal.csv`: one row per canonical record, only when `--repair` is requested.

Exit codes are `0` for a completed audit without policy violations, `2` for a completed audit with policy violations after artifacts are written, and `1` for input, configuration, execution, or artifact-writing failures.
