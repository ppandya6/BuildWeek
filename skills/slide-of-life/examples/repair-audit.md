# Repair-proposal audit

Before running, explain that related records may be indivisible groups; train/test ratio, label balance, and institution grouping may change; similarity candidates do not become identity evidence; and every record should appear exactly once. The researcher must review the proposal.

## Bash

```bash
slide-of-life audit \
  --train fixtures/generated_train.csv \
  --test fixtures/generated_test.csv \
  --images fixtures/generated_images \
  --schema-map fixtures/schema-map.yaml \
  --output slide-of-life-artifacts \
  --repair \
  --force
```

## PowerShell

```powershell
slide-of-life audit `
  --train fixtures/generated_train.csv `
  --test fixtures/generated_test.csv `
  --images fixtures/generated_images `
  --schema-map fixtures/schema-map.yaml `
  --output slide-of-life-artifacts `
  --repair `
  --force
```

Use `--force` only when overwrite authorization was explicit. Check that `repair_proposal.csv` exists and that every input record is represented exactly once before describing it. Never replace or commit source manifests automatically.
