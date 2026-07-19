# SlideLineage

SlideLineage is a local scientific developer tool planned to audit train/test partition relationships in computational-pathology datasets. It is intended for researchers, benchmark maintainers, data engineers, and scientific software developers who need transparent evidence about partition independence before model training or evaluation.

## Current implementation status

The repository foundation, typed contract layer, and deterministic CSV ingestion boundary exist: packaging, documentation, developer tooling, CI, CLI help/version output, `AuditConfig`, the default `SplitPolicy`, typed domain/report contracts, conservative normalization helpers, source-byte SHA-256 manifest provenance, typed loaded-manifest contracts, deterministic semantic schema mapping, explicit schema overrides, canonical record construction, stable record IDs, strict TCGA parsing, and lineage conflict reporting are implemented. Schema mapping supports explicit YAML/JSON maps, direct column overrides, deterministic header/value scoring, unresolved ambiguity, ranked alternatives, and train/test consistency messages. Canonical record construction preserves source provenance, deterministic digests, direct and TCGA-derived lineage evidence, and partition warnings while avoiding overlap detection. The audit pipeline arrives in later stages. Identifier overlap facts, image path auditing, byte fingerprints, canonical pixel fingerprints, perceptual similarity candidates, and evidence-rich factual findings are now implemented. Relationship graph materialization, policy evaluation, evaluated findings, deterministic repair proposals, report writers, deterministic audit orchestration, standalone HTML/JSON/CSV artifact generation, repair CSV output, and the operational audit CLI are now implemented. The reproducible synthetic demonstration is implemented. Optional OpenAI API integration remains pending.

## Deterministic-first architecture

The planned architecture separates:

1. Deterministic factual relationship detection into `FactualFinding` records.
2. Evaluation under an explicit `SplitPolicy` into `EvaluatedFinding` records.
3. Optional repair proposals requiring researcher review.
4. Optional GPT-5.6 schema interpretation, with deterministic scientific evidence remaining authoritative.

## Operational synthetic demo

All demo identifiers and pixels are synthetic. After development installation,
generate and audit from the repository root:

```bash
python scripts/generate_demo.py --force
slidelineage audit \
  --train examples/demo/generated/train_manifest.csv \
  --test examples/demo/generated/test_manifest.csv \
  --images examples/demo/generated/images \
  --schema-map examples/demo/schema-map.yaml \
  --output artifacts/demo-audit \
  --repair --force
```

Open `artifacts/demo-audit/report.html` locally. Exit code `2` is expected: the
audit completed and wrote artifacts, but deliberate relationships violate the
default policy. No clinical interpretation is performed. Similarity is a review
candidate rather than identity evidence, and repair requires researcher review.
See [`examples/demo/README.md`](examples/demo/README.md) for details and PowerShell
syntax.

## Development installation

```bash
python -m pip install -e ".[dev]"
```

Optional AI-assisted schema interpretation is installed separately:

```bash
python -m pip install -e ".[dev,ai]"
```

AI is explicit opt-in. Headers and aggregate missingness, uniqueness, cardinality,
and abstract pattern flags may leave the machine; raw rows, literal values, image
paths, and image bytes remain local. Because headers can themselves be sensitive,
review them before enabling AI. Proposals are deterministically validated, but
validation alone does not apply them. Explicit acceptance is required, and AI
never creates scientific findings, policy decisions, or repairs.

Proposal-only mode:

```bash
slidelineage audit \
  --train train.csv \
  --test test.csv \
  --output artifacts/audit \
  --ai-schema-map
```

Explicitly accepted mode:

```bash
slidelineage audit \
  --train train.csv \
  --test test.csv \
  --output artifacts/audit \
  --ai-schema-map \
  --accept-validated-ai-mapping
```

## Reusable GitHub Action

Callers must check out their manifests and select Python 3.11 before invoking the
local composite action. Before a tagged package release exists, the action installs
SlideLineage predictably from `${{ github.action_path }}` and wraps the existing
CLI rather than reimplementing the audit engine.

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- id: lineage
  uses: ppandya6/BuildWeek@codex/task-11-github-action
  with:
    train-manifest: data/train.csv
    test-manifest: data/test.csv
    images-dir: data/images
    output-dir: slidelineage-artifacts
    fail-on-violations: "true"
- if: always()
  uses: actions/upload-artifact@v4
  with:
    name: slidelineage-audit
    path: |
      slidelineage-artifacts/report.json
      slidelineage-artifacts/report.html
      slidelineage-artifacts/findings.csv
      slidelineage-artifacts/repair_proposal.csv
```

Required inputs are `train-manifest` and `test-manifest`. Optional inputs configure
the image root, schema map, output directory, policy profile, repair, overwrite
behavior, institution grouping, repair target, image comparison limits and
thresholds, optional AI schema assistance, and `fail-on-violations`. AI is disabled
by default and no API key is an action input; opt-in provider access uses its
standard environment variable supplied through GitHub secrets.

The stable outputs are `status`, `exit-code`, `report-json`, `report-html`,
`findings-csv`, `repair-proposal-csv`, `violation-count`, and `review-count`.
`repair-proposal-csv` is empty when no proposal was generated. CLI exit 0 succeeds,
exit 1 always fails, and exit 2 represents a completed audit with policy
violations. With the default `fail-on-violations: "true"`, exit 2 fails only after
reports and outputs are written; setting it to `"false"` makes the action succeed
with `status=violations` so a workflow can handle policy results itself.

The action creates artifacts but never uploads them, comments on pull requests,
changes manifests, or commits repairs. Use `actions/upload-artifact` with
`if: always()` as above so reports survive policy failures. Raw rows stay within
the runner process. Reports do not prove that a split is contamination-free, and
every generated repair remains a proposal requiring researcher review. See
`.github/workflows/slidelineage-example.yml` for a manual, synthetic, AI-free
Ubuntu and Windows example.

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

Task 9 supplies the reproducible synthetic fixture and end-to-end assertions.

## Privacy and scope

Deterministic auditing is planned to run locally. API access must be opt-in, API keys must not be stored in the repository, and future GPT requests must avoid complete manifests or images. SlideLineage is non-clinical software: it must not make diagnosis, prognosis, treatment, biological interpretation, or clinical claims.

## License

SlideLineage is distributed under the MIT License. See [LICENSE](LICENSE).

## Task 7 implementation status

Relationship graph contracts and deterministic materialization now exist for canonical records and factual findings. Explicit `SplitPolicy` evaluation converts factual findings into evaluated findings with policy outcomes, rules, reasons, counts, exit-code semantics, and repair eligibility. Deterministic repair proposals now construct indivisible components, run a typed greedy train/test assignment, preserve all records, and report proposal metrics and tradeoffs for researcher review.

Still pending for Task 11: packaging and automation work outside milestone Task 10.

## Operational audit quick start

Task 8 adds the operational local audit command:

```bash
slidelineage audit \
  --train examples/demo/train_manifest.csv \
  --test examples/demo/test_manifest.csv \
  --images examples/demo/images \
  --output artifacts/demo-audit
```

The Task 9 generator creates the documented demo files on demand; users may also provide their own train/test CSV manifests and optional image root.

The audit writes:

- `report.json`: typed UTF-8 JSON report.
- `report.html`: standalone local HTML report with embedded CSS and escaped content.
- `findings.csv`: one row per evaluated finding.
- `repair_proposal.csv`: one row per canonical record, only when `--repair` is requested.

Exit codes are `0` for a completed audit without policy violations, `2` for a completed audit with policy violations after artifacts are written, and `1` for input, configuration, execution, or artifact-writing failures.
