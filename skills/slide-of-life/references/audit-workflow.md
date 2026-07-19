# Audit workflow

## Preflight

1. Resolve the train and test paths without printing manifest contents; reject missing or identical files.
2. Read only CSV headers when learning columns. Confirm an optional image directory and schema-map file exist.
3. Use deterministic mapping first. If essential semantics remain ambiguous, offer a reviewed manual schema map before optional AI.
4. Confirm output intent, repair, grouping, policy, ratio, thresholds, and AI. Never overwrite without permission.
5. Build an argument list conceptually; quote literal paths only for display. Avoid shell interpolation.

The required arguments are `--train`, `--test`, and `--output`. Optional controls include `--images`, `--schema-map`, `--policy-profile`, `--repair`, `--group-by-institution`, `--target-train-fraction`, `--max-image-pairs`, `--phash-distance-threshold`, `--dhash-distance-threshold`, `--image-max-pixels`, explicit column flags, `--ai-schema-map`, and `--accept-validated-ai-mapping`. Acceptance requires AI schema assistance. Check `slide-of-life audit --help` for the installed version rather than inventing options.

## Bash examples

```bash
slide-of-life audit \
  --train train.csv \
  --test test.csv \
  --images images \
  --output slide-of-life-artifacts
```

```bash
slide-of-life audit \
  --train train.csv \
  --test test.csv \
  --images images \
  --schema-map schema-map.yaml \
  --output slide-of-life-artifacts \
  --repair \
  --force
```

## PowerShell examples

PowerShell uses the backtick continuation character, not Bash's backslash:

```powershell
slide-of-life audit `
  --train train.csv `
  --test test.csv `
  --images images `
  --output slide-of-life-artifacts
```

```powershell
slide-of-life audit `
  --train train.csv `
  --test test.csv `
  --images images `
  --schema-map schema-map.yaml `
  --output slide-of-life-artifacts `
  --repair `
  --force
```

Use `--force` only after explicit authorization. An exit code of 2 means the completed audit found violations; proceed to artifact interpretation.
