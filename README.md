# SlideLineage

SlideLineage is a local scientific developer tool planned to audit train/test partition relationships in computational-pathology datasets. It is intended for researchers, benchmark maintainers, data engineers, and scientific software developers who need transparent evidence about partition independence before model training or evaluation.

## Current implementation status

The repository foundation and typed contract layer exist: packaging, documentation, developer tooling, CI, CLI help/version output, `AuditConfig`, the default `SplitPolicy`, and typed domain/report contracts are implemented. The audit pipeline arrives in later stages. Manifest ingestion, schema inference, detectors, graph construction execution, policy evaluation execution, repair execution, report writers, demo generation, and OpenAI API integration remain pending.

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

This planned two-manifest command is not available at the current stage.

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

Task 2 implements typed report contracts only; report writer execution remains pending.

## Privacy and scope

Deterministic auditing is planned to run locally. API access must be opt-in, API keys must not be stored in the repository, and future GPT requests must avoid complete manifests or images. SlideLineage is non-clinical software: it must not make diagnosis, prognosis, treatment, biological interpretation, or clinical claims.

## License

SlideLineage is distributed under the MIT License. See [LICENSE](LICENSE).
