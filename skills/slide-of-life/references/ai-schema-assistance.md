# AI schema assistance

AI is optional, secondary to deterministic and manual mapping, and limited to semantic-column proposals. It never creates factual findings, policy outcomes, or repair decisions. API charges may apply.

## Privacy boundary

Do not request a key in chat. Never print, summarize, persist, or place one in skill files. Never send raw rows, literal record values, image paths, manifest bytes, or image bytes to OpenAI. The product sends only headers and aggregate column statistics and deterministically validates every proposal.

Users configure `OPENAI_API_KEY` in their local environment. GitHub Actions must use a GitHub Secret. If a local interactive run has no key, let the CLI perform its approved onboarding flow; do not reproduce that flow in chat. In noninteractive environments, explain that the key must already be supplied through an environment variable or secret.

## Proposal-only run

Bash:

```bash
slide-of-life audit \
  --train train.csv \
  --test test.csv \
  --output slide-of-life-artifacts \
  --ai-schema-map
```

PowerShell:

```powershell
slide-of-life audit `
  --train train.csv `
  --test test.csv `
  --output slide-of-life-artifacts `
  --ai-schema-map
```

## Explicit acceptance

Apply only mappings that the software deterministically validated, and only after explicit user acceptance:

```bash
slide-of-life audit \
  --train train.csv \
  --test test.csv \
  --output slide-of-life-artifacts \
  --ai-schema-map \
  --accept-validated-ai-mapping
```

Acceptance changes schema mapping for that run only; it does not authorize AI findings or repair decisions.
