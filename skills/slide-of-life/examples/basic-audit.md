# Basic local audit

Use fictional paths and let the CLI perform all scientific computation.

## Bash

```bash
slide-of-life audit \
  --train data/generated_train.csv \
  --test data/generated_test.csv \
  --images data/generated_images \
  --output slide-of-life-artifacts
status=$?
```

## PowerShell

```powershell
slide-of-life audit `
  --train data/generated_train.csv `
  --test data/generated_test.csv `
  --images data/generated_images `
  --output slide-of-life-artifacts
$status = $LASTEXITCODE
```

Treat status 0 as completed without violations, 1 as a focused failure, and 2 as completed with violations. For 0 or 2, verify `report.html`, `report.json`, and `findings.csv`, then summarize facts separately from policy outcomes.
