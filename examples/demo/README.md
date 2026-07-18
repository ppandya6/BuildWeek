# Synthetic end-to-end demonstration

This example exercises SlideLineage's local deterministic audit with fictional
identifiers and programmatically generated pixels. It contains no external,
patient, or clinical data and performs no clinical interpretation.

## Generate the source fixture

```bash
python scripts/generate_demo.py --force
```

The generator writes two six-row manifests and eleven 64-by-64 images under
`examples/demo/generated/`; one twelfth image path is intentionally missing. It
uses no randomness. Forced reruns replace only known demo files, preserve unrelated
files, and reproduce filenames, ordering, manifest bytes, and image bytes. Add
`--output path/to/generated` to choose a destination. A nonempty destination is
refused without `--force`.

## Run the audit

```bash
slidelineage audit \
  --train examples/demo/generated/train_manifest.csv \
  --test examples/demo/generated/test_manifest.csv \
  --images examples/demo/generated/images \
  --schema-map examples/demo/schema-map.yaml \
  --output artifacts/demo-audit \
  --repair \
  --force
```

In PowerShell, replace each trailing `\` with a backtick (`` ` ``), or put the
command on one line. Generation uses the same command in PowerShell.

**Exit code 2 is expected.** It means the completed audit wrote reports and found
relationships disallowed by the default policy, not that execution failed. The
fixture produces one finding in each category:

- confirmed patient, specimen, and slide overlaps;
- confirmed byte-content and decoded-pixel-content duplicates;
- allowed institution overlap;
- probable image-similarity review candidate; and
- missing-image input-quality review item.

The first five disallowed categories are planted independently. Differently named
byte duplicate files are identical, while the pixel duplicate uses PNG and BMP
encodings of the same RGB pixels. The similar pair differs by one synthetic pixel
and is only a review candidate—not evidence of lineage or identity. Other
identifiers are clean controls.

## Inspect and clean up

- `artifacts/demo-audit/report.json`: typed full report.
- `artifacts/demo-audit/report.html`: standalone local report.
- `artifacts/demo-audit/findings.csv`: evaluated-finding table.
- `artifacts/demo-audit/repair_proposal.csv`: proposed assignment for every record.

Open the HTML file in a browser or run
`python -m webbrowser artifacts/demo-audit/report.html`. The repair CSV is a
proposal requiring researcher review; it does not establish split correctness.
The fixture is illustrative, not a benchmark or publication-readiness claim.

```bash
rm -rf examples/demo/generated artifacts/demo-audit
```

PowerShell: `Remove-Item -Recurse -Force examples/demo/generated,
artifacts/demo-audit`.
