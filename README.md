# SlideLineage

SlideLineage is a local scientific developer tool planned to audit train/test partition relationships in computational-pathology datasets. It is intended for researchers, benchmark maintainers, data engineers, and scientific software developers who need transparent evidence about partition independence before model training or evaluation.

## Current implementation status

The repository foundation, typed contract layer, deterministic CSV ingestion boundary, conservative normalization, deterministic schema mapping, and explicit YAML/JSON schema overrides exist. Packaging, documentation, developer tooling, CI, CLI help/version output, `AuditConfig`, the default `SplitPolicy`, typed domain/report contracts, source-byte SHA-256 manifest provenance, typed loaded-manifest contracts, and schema interpretation provenance are implemented. The audit pipeline arrives in later stages. Record-ID generation, TCGA parsing, lineage conflict detection, overlap detectors, image analysis, graph construction execution, policy evaluation execution, report generation, repair execution, demo generation, GPT integration, and the operational audit CLI remain pending.

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
