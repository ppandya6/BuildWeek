# Slide-of-Life

**A local, deterministic-first audit for hidden relationships between the train
and test partitions of computational-pathology datasets.**

Slide-of-Life finds explicit lineage overlap, exact image duplication, and image
similarity candidates *before* leakage makes an evaluation look more convincing
than it is. It then evaluates the factual evidence against a named split policy
and can create a review-required repair proposal.

> Built for OpenAI Build Week with Codex and optional GPT-5.6 schema assistance.
> No OpenAI API key is needed for the demo or for normal deterministic audits.

## Judge quick start

The demo is entirely synthetic, deterministic, and small. Allow about two
minutes. **Python 3.11 or newer is required.** The commands below deliberately
select Python 3.11 instead of relying on an ambiguous `python` command.

### Windows PowerShell (tested path)

First confirm that the Windows Python launcher can find Python 3.11:

```powershell
py -0p
py -3.11 --version
```

If the second command fails, install Python 3.11 or newer from
[python.org](https://www.python.org/downloads/windows/) and enable the Python
launcher. Then open a new PowerShell window.

Run the following from the directory in which you want the repository to live.
This path does **not** require virtual-environment activation, so PowerShell's
execution policy cannot block the demo:

```powershell
git clone https://github.com/ppandya6/Slide-of-Life.git
Set-Location Slide-of-Life
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install "slide-of-life==0.1.0a1"
& .\.venv\Scripts\python.exe scripts\generate_demo.py --force
& .\.venv\Scripts\slide-of-life.exe audit --train examples\demo\generated\train_manifest.csv --test examples\demo\generated\test_manifest.csv --images examples\demo\generated\images --schema-map examples\demo\schema-map.yaml --output artifacts\demo-audit --repair --force
```

The final command intentionally returns **exit code 2** because the synthetic
data contains policy violations. That means the audit succeeded and wrote its
reports; it is not a crash. Confirm the result and open the report:

```powershell
$LASTEXITCODE                 # expected: 2
Get-ChildItem artifacts\demo-audit
Invoke-Item artifacts\demo-audit\report.html
```

> If `py -3.11` is unavailable but `py -3.12` is listed by `py -0p`, substitute
> `py -3.12` in the two commands that create/check the environment. If `git` is
> unavailable, download the repository ZIP from GitHub, extract it, open
> PowerShell in that `Slide-of-Life` directory, and begin with the `py -3.11 -m
> venv .venv` command.

### macOS or Linux

Use a Python 3.11+ interpreter. On systems where it is named `python3`, run:

```bash
git clone https://github.com/ppandya6/Slide-of-Life.git
cd Slide-of-Life
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install "slide-of-life==0.1.0a1"
.venv/bin/python scripts/generate_demo.py --force
.venv/bin/slide-of-life audit \
  --train examples/demo/generated/train_manifest.csv \
  --test examples/demo/generated/test_manifest.csv \
  --images examples/demo/generated/images \
  --schema-map examples/demo/schema-map.yaml \
  --output artifacts/demo-audit \
  --repair \
  --force
```

Exit code **2 is expected**. Open the standalone report with:

```bash
python3 -m webbrowser artifacts/demo-audit/report.html
```

If the browser command is unavailable, open
`artifacts/demo-audit/report.html` from Finder or your file manager.

## What just happened?

The generator created two six-row manifests and eleven tiny generated images;
one twelfth image path is intentionally missing. The audit then compared train
and test records, evaluated the evidence under the default policy, proposed a
replacement partition, and wrote four files.

All paths below are relative to the cloned `Slide-of-Life` directory:

| Path | What it contains |
| --- | --- |
| `examples/demo/generated/train_manifest.csv` | Six synthetic training records |
| `examples/demo/generated/test_manifest.csv` | Six synthetic test records |
| `examples/demo/generated/images/` | Eleven deterministic 64×64 generated images |
| `artifacts/demo-audit/report.html` | Standalone, human-readable report; open locally in a browser |
| `artifacts/demo-audit/report.json` | Full typed, machine-readable audit report |
| `artifacts/demo-audit/findings.csv` | Policy-evaluated findings table |
| `artifacts/demo-audit/repair_proposal.csv` | Proposed assignment for every input record; researcher review required |

The HTML is self-contained and does not need a server or internet connection.
Rerunning with `--force` replaces the known generated demo/output files.

## Expected demo findings

The report contains **eight deliberately planted relationship categories**:

| Relationship | Expected policy result | Meaning |
| --- | --- | --- |
| Confirmed patient overlap | Violation | A canonical patient identifier crosses partitions |
| Confirmed specimen overlap | Violation | A canonical specimen identifier crosses partitions |
| Confirmed slide overlap | Violation | A canonical slide identifier crosses partitions |
| Confirmed byte-content duplicate | Violation | Differently named files have identical bytes |
| Confirmed pixel-content duplicate | Violation | PNG and BMP files decode to identical pixels |
| Institution overlap | Allowed | Shared institution provenance is recorded but permitted by the default policy |
| Image-similarity candidate | Review | Two generated images differ by one synthetic pixel; this is not identity evidence |
| Missing-image input quality | Review | One manifest path intentionally has no image |

The five confirmed cross-partition overlaps/duplicates are independently planted
and are repair-eligible under the default policy. Similarity is kept separate
from lineage identity, and the repair CSV is only a proposal—not proof that a
split is correct.

## Why contamination matters

If related patients, specimens, slides, crops, re-encodings, or derived images
occur in both training and testing data, a model can effectively be evaluated on
information it has already seen. This can inflate reported performance and
undermine benchmarks, papers, and product claims. Filenames and ordinary file
hashes alone are insufficient: identifiers can express lineage, and the same
decoded pixels can be stored in different file formats.

Slide-of-Life makes that evidence inspectable without making biological or
clinical claims. It does not certify that a dataset is contamination-free.

## How the pipeline stays scientifically clear

Slide-of-Life keeps three concepts separate:

1. **Factual detection:** deterministic detectors emit evidence with source and
   row provenance.
2. **Policy evaluation:** an explicit `SplitPolicy` marks each factual finding as
   allowed, a violation, or requiring review, with a deterministic reason.
3. **Repair proposal:** an optional deterministic assignment responds only to
   eligible confirmed findings and always requires researcher review.

Exact byte/pixel relationships are distinct from perceptual similarity.
Similarity never establishes patient, specimen, slide, or institution identity.

## Codex, GPT-5.6, and deterministic code

### How Codex was used

Codex assisted the engineering workflow: architecture and implementation of the
Python package and CLI, tests, cross-platform CI, GitHub Action and Agent Skill,
release debugging, packaging, and documentation. Codex helped build the tool; it
is not an inference service used by the deterministic audit pipeline.

### How GPT-5.6 is used

GPT-5.6 is an **optional, explicitly enabled schema assistant**. For unresolved
manifest columns, it can propose semantic column mappings using headers and
privacy-bounded aggregate statistics. Slide-of-Life records model/provider
provenance, validates proposals deterministically, and requires explicit user
acceptance before applying a validated mapping. It sends no raw rows or images.

### What remains deterministic

In both normal use and the demo, local deterministic code performs ingestion,
canonicalization, factual relationship detection, image fingerprinting, policy
evaluation, repair proposal generation, and report serialization. GPT-5.6 never
creates findings, decides policy outcomes, or makes repair decisions. The demo
does not contact OpenAI and needs no credential.

## Install without running the demo

The published alpha requires Python 3.11+:

```bash
python3 -m pip install "slide-of-life==0.1.0a1"
slide-of-life --version
slide-of-life --help
```

On Windows, use the explicit interpreter commands to avoid installing into a
different or unsupported Python:

```powershell
py -3.11 -m pip install "slide-of-life==0.1.0a1"
slide-of-life --help
```

The installed interface is the `slide-of-life` executable, not a
`python -m slide_of_life` module. In a virtual environment, use
`.\.venv\Scripts\slide-of-life.exe --help` as shown in the quick start.
The deprecated `slidelineage` executable remains only as a compatibility alias.

## Optional AI schema assistance

AI is unnecessary for explicit schema maps such as the demo's. To make the
optional feature available, install:

```bash
python3 -m pip install "slide-of-life[ai]==0.1.0a1"
```

Provider access happens only when AI schema mapping is explicitly requested.
Never paste or commit an API key; use the `OPENAI_API_KEY` environment variable
or a CI secret. See the
[scientific method](docs/scientific-method.md#task-10-optional-ai-schema-interpretation)
for the privacy boundary and acceptance workflow.

## Other ways to run it

- The [GitHub Action](action.yml) invokes the same CLI for policy-aware CI, writes
  reports before returning a policy-violation status, and keeps AI off by default.
- The [Slide-of-Life Agent Skill](skills/slide-of-life/SKILL.md) wraps the CLI for
  safe preflight, execution, and artifact interpretation; it does not duplicate
  or replace the audit engine.
- The [detailed demo guide](examples/demo/README.md) documents fixture semantics,
  cleanup, and custom generation destinations.

Pin the published Action release after checking out the repository data:

```yaml
- uses: actions/checkout@v4
- uses: ppandya6/Slide-of-Life@v0.1.0a1
  with:
    train-manifest: data/train.csv
    test-manifest: data/test.csv
    output-dir: slide-of-life-artifacts
```

## Limitations and safety

Slide-of-Life `0.1.0a1` is an alpha prerelease, not a clinical device or
regulatory compliance product. Audit quality depends on the supplied manifests,
accepted identifiers, images, and schema mapping. Missing or ambiguous data
limits what can be detected. Every finding and repair proposal requires human
review.

The demo contains only fictional identifiers and generated pixels. Slide-of-Life
makes no diagnosis, prognosis, treatment, biological interpretation, or clinical
claim. Do not commit raw clinical data or credentials to this repository.

## Project links

- [GitHub repository](https://github.com/ppandya6/Slide-of-Life)
- [PyPI: `slide-of-life` 0.1.0a1](https://pypi.org/project/slide-of-life/0.1.0a1/)
- [GitHub release `v0.1.0a1`](https://github.com/ppandya6/Slide-of-Life/releases/tag/v0.1.0a1)
- [Changelog](CHANGELOG.md)
- [Scientific method](docs/scientific-method.md)
- [Product specification](docs/product-spec.md)

## Development

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest -q
```

Release `0.1.0a1` is unchanged by this documentation update. Publication guidance
is in [the release documentation](docs/releasing.md). Do not publish or create a
release tag without explicit approval.

## License

Slide-of-Life is distributed under the [MIT License](LICENSE).
