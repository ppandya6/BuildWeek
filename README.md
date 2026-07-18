# SlideLineage

SlideLineage is a local scientific developer tool planned to audit train/test partition relationships in computational-pathology datasets. It is intended for researchers, benchmark maintainers, data engineers, and scientific software developers who need transparent evidence about partition independence before model training or evaluation.

## Current implementation status

Task 1 establishes the repository foundation: packaging, documentation, developer tooling, CI, a package entry point, and CLI help/version output. The audit pipeline arrives in later stages. No detector, manifest ingestion command, schema mapping, graph construction, policy evaluation, repair workflow, report generator, demo generator, or OpenAI API integration is implemented yet.

## Deterministic-first architecture

The planned architecture separates:

1. Deterministic factual relationship detection.
2. Evaluation under an explicit `SplitPolicy`.
3. Optional repair proposals requiring researcher review.
4. Optional GPT-5.6 schema interpretation, with deterministic scientific evidence remaining authoritative.

## Planned command example

A later milestone is expected to introduce an audit command similar to:

```bash
slidelineage audit --manifest dataset.csv --policy patient_independent_pathology_benchmark --out reports/
```

This command is not available in Task 1.

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

## Privacy and scope

Deterministic auditing is planned to run locally. API access must be opt-in, API keys must not be stored in the repository, and future GPT requests must avoid complete manifests or images. SlideLineage is non-clinical software: it must not make diagnosis, prognosis, treatment, biological interpretation, or clinical claims.

## License

SlideLineage is distributed under the MIT License. See [LICENSE](LICENSE).
