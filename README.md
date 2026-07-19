# Slide-of-Life

Slide-of-Life audits computational-pathology dataset partitions for hidden
patient, slide, lineage, and image contamination before those errors invalidate
model evaluation.

> Built for OpenAI Build Week using Codex and GPT-5.6.

## The problem

Train/test leakage can make a model appear better than it is. Pathology datasets
often contain related patients, slides, crops, re-encodings, or derived images,
and filenames or simple file hashes do not expose every relationship. Undetected
contamination can undermine papers, benchmarks, and product claims.

## What Slide-of-Life does

Slide-of-Life runs a local, deterministic-first pipeline:

1. Ingest manifests and explicit schema mappings.
2. Normalize records while retaining source and row provenance.
3. Detect factual identifier overlaps, exact image relationships, and separate
   image-similarity review candidates.
4. Evaluate those facts under an explicit partition policy.
5. Produce findings with reviewable evidence and policy reasons.
6. Propose a deterministic replacement partition when requested.
7. Write JSON, CSV, and standalone HTML reports.

These outputs are deliberately distinct: a **factual finding** records detected
evidence; a **policy violation** is that fact evaluated against a named rule; and
a **repair proposal** is a suggested partition that still requires researcher
review. Image similarity is never promoted to patient or slide identity.

## Install from PyPI

**Python 3.11 or newer is required.** Version `0.1.0a1` is an alpha prerelease.

Install the exact verified release:

```bash
python -m pip install "slide-of-life==0.1.0a1"
```

Or ask pip to select the available prerelease:

```bash
python -m pip install --pre slide-of-life
```

In PowerShell, select Python 3.11 explicitly when multiple versions are installed:

```powershell
py -3.11 -m pip install "slide-of-life==0.1.0a1"
```

## Verify installation

```bash
slide-of-life --version
slide-of-life --help
```

`slide-of-life` is the primary command. The deprecated `slidelineage --help`
command remains available as a compatibility alias.

## Fastest demo

The repository includes a deterministic, entirely synthetic fixture. Starting
after the PyPI installation above:

```bash
git clone https://github.com/ppandya6/Slide-of-Life.git
cd Slide-of-Life
python scripts/generate_demo.py --force

slide-of-life audit \
  --train examples/demo/generated/train_manifest.csv \
  --test examples/demo/generated/test_manifest.csv \
  --images examples/demo/generated/images \
  --schema-map examples/demo/schema-map.yaml \
  --output artifacts/demo-audit \
  --repair \
  --force
```

**Exit code 2 is expected.** It means the audit completed, wrote its reports, and
found relationships disallowed by the default policy. It is not an execution
failure. Open `artifacts/demo-audit/report.html` to inspect the result. The output
directory contains:

- `report.html` — standalone human-readable report;
- `report.json` — typed machine-readable report;
- `findings.csv` — evaluated findings; and
- `repair_proposal.csv` — review-required proposed assignments.

PowerShell users can replace each trailing `\` with a backtick or place the audit
command on one line. See the [demo guide](examples/demo/README.md) for details.

## What the demo reveals

The fixture plants one finding in each supported relationship category:

- confirmed patient, specimen, and slide overlaps across train and test;
- exact byte-content and decoded-pixel-content duplicates;
- an allowed institution overlap with provenance;
- a near-duplicate image-similarity candidate for human review; and
- a missing-image input-quality review item.

The default policy marks the five confirmed cross-partition overlap/duplicate
categories as violations. Similarity remains review evidence, and the generated
repair remains only a proposal.

## Visual report preview

<!-- TODO: Add final demo report screenshot before Devpost submission. -->

Run the synthetic demo and open `artifacts/demo-audit/report.html` for the current
standalone report.

## Built with Codex and GPT-5.6

### Codex

Codex was used extensively to design and implement the CLI and Python package,
build tests and cross-platform CI, package the GitHub Action and Agent Skill,
debug release failures, create the guarded Trusted Publishing infrastructure,
and publish and verify the PyPI alpha. The result is a complete developer tool,
not a model wrapper.

### GPT-5.6

GPT-5.6 support is implemented for bounded schema interpretation: when explicitly
enabled, it can propose mappings for unresolved manifest columns from headers and
privacy-bounded aggregate statistics. The CLI and GitHub Action currently select
`gpt-5.6` by default and record model/provider provenance.

GPT-5.6 does **not** determine contamination findings, decide policy violations,
or invent repair proposals. Deterministic code owns all three outputs. AI support
is optional, and normal auditing works without an OpenAI key.

## Optional AI support

Install the optional OpenAI dependency with:

```bash
python -m pip install "slide-of-life[ai]==0.1.0a1"
```

No API key is needed for deterministic auditing. Provider access occurs only when
AI schema mapping is explicitly requested. Never paste keys into chat or commit
them; provide credentials through standard environment configuration such as the
`OPENAI_API_KEY` environment variable or a CI secret. Slide-of-Life sends no raw
rows or images, validates every proposal deterministically, and requires explicit
acceptance before applying a validated mapping. See the
[scientific method](docs/scientific-method.md#task-10-optional-ai-schema-interpretation).

## GitHub Action

The composite Action invokes the same CLI and supports policy-aware CI. Pin the
published release tag and check out the data before invoking it:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- id: audit
  uses: ppandya6/Slide-of-Life@v0.1.0a1
  with:
    train-manifest: data/train.csv
    test-manifest: data/test.csv
    images-dir: data/images
    schema-map: data/schema-map.yaml
    output-dir: slide-of-life-artifacts
    repair: "true"
    fail-on-violations: "true"
- if: always()
  uses: actions/upload-artifact@v4
  with:
    name: slide-of-life-audit
    path: slide-of-life-artifacts/
```

The Action writes reports before treating policy violations as a failure. AI is
off by default; keys are never Action inputs. See [`action.yml`](action.yml) for
all supported inputs and outputs.

## Agent Skill

The repository includes a reusable
[Slide-of-Life Agent Skill](skills/slide-of-life/SKILL.md) for safe preflight,
execution, and artifact interpretation. It wraps the public CLI instead of
reimplementing detectors, policies, or repair logic.

## Why it is different

- Audits lineage and preserved provenance, not only filenames.
- Keeps detected facts, explicit policy decisions, and repair proposals separate.
- Leaves scientific findings deterministic while constraining optional AI to
  schema assistance.
- Operates locally by default and emits both machine-readable and human-readable
  reports.
- Ships as a PyPI package, CLI, GitHub Action, and Agent Skill.

## Use cases

- ML researchers validating experimental splits.
- Pathology teams auditing dataset preparation.
- Reviewers reproducing partition evidence.
- CI systems blocking datasets that violate a declared policy.
- Research teams preparing benchmarks or publications.

## Limitations and safety

Slide-of-Life is alpha software. It is not a clinical device or regulatory
compliance product, and it does not certify a dataset as contamination-free.
Findings and every repair proposal require human review. Audit quality depends on
the available manifests, identifiers, images, and schema mapping; missing or
ambiguous inputs limit what can be detected.

The committed demo uses only fictional identifiers and generated pixels. Do not
commit raw clinical data to this repository. Slide-of-Life makes no diagnosis,
prognosis, treatment, biological interpretation, or clinical claim.

## Project status

- Current version: `0.1.0a1` (alpha prerelease).
- Published on PyPI as a wheel and source distribution.
- Public GitHub repository, prerelease, and build attestation available.
- Active OpenAI Build Week submission preparation.
- Post-alpha feedback, validation, and hardening are planned.

## Links

- [GitHub repository](https://github.com/ppandya6/Slide-of-Life)
- [PyPI project](https://pypi.org/project/slide-of-life/0.1.0a1/)
- [GitHub release `v0.1.0a1`](https://github.com/ppandya6/Slide-of-Life/releases/tag/v0.1.0a1)
- [Changelog](CHANGELOG.md)
- [Scientific method](docs/scientific-method.md)
- [Product specification](docs/product-spec.md)
- [Agent Skill](skills/slide-of-life/SKILL.md)

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
mypy src
```

Run `ruff format --check .` before contributing. Deeper packaging and publication
guidance is in [the release documentation](docs/releasing.md).

## License

Slide-of-Life is distributed under the [MIT License](LICENSE).
