# GitHub Action

Replace `<pinned-ref>` with a reviewed full commit SHA or a future release tag. The placeholder is not production-safe; never recommend an unpinned development branch.

```yaml
steps:
  - uses: actions/checkout@v4

  - uses: actions/setup-python@v5
    with:
      python-version: "3.11"

  - id: audit
    uses: ppandya6/BuildWeek@<pinned-ref>
    with:
      train-manifest: data/generated_train.csv
      test-manifest: data/generated_test.csv
      output-dir: slide-of-life-artifacts
      fail-on-violations: "true"

  - if: always()
    uses: actions/upload-artifact@v4
    with:
      name: slide-of-life-audit
      path: slide-of-life-artifacts
```

With explicitly requested AI schema assistance, use the existing boolean Action input and a GitHub Secret—never an API-key input:

```yaml
  - id: audit
    uses: ppandya6/BuildWeek@<pinned-ref>
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    with:
      train-manifest: data/generated_train.csv
      test-manifest: data/generated_test.csv
      output-dir: slide-of-life-artifacts
      ai-schema-map: "true"
      fail-on-violations: "true"
```

`fail-on-violations: "true"` preserves exit 2 as a failing workflow signal while reports remain available for `if: always()` upload. Do not weaken policy simply to make CI green.
