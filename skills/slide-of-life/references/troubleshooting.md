# Troubleshooting

- **Command not found / package absent:** from a trusted checkout run `python -m pip install -e .`; install `.[ai]` only for explicitly requested AI assistance. Confirm Python 3.11 or newer.
- **Manifest missing:** correct `--train` or `--test`; do not claim an audit result exists.
- **Schema ambiguity:** inspect actual headers, prefer a reviewed manual schema map, and never fabricate column names.
- **Normalized header collision:** create a reviewed manifest copy with distinct headers; do not guess or suffix silently.
- **Missing image files:** verify `--images` and relative paths; report failed image evidence as an input-quality limitation.
- **Output already populated:** choose a new directory or obtain explicit authorization before `--force`.
- **OpenAI SDK missing:** for explicitly requested AI, install with `python -m pip install -e ".[ai]"`; deterministic mode remains available without it.
- **OpenAI key missing:** never request it in chat. Let an interactive local CLI run onboard; for noninteractive use, configure `OPENAI_API_KEY` through the environment or GitHub Secrets.
- **Authentication failure:** verify the local environment or secret configuration without printing the credential.
- **Exit code 2:** the audit completed and found policy violations. Inspect generated reports; do not suppress violations merely to make CI green.
- **Repair proposal absent:** verify repair was requested and check the report; never claim `repair_proposal.csv` exists without checking.
- **GitHub artifacts absent:** use `if: always()` for upload, verify the configured output directory, and inspect Action outputs and exit-code policy.
- **Legacy command:** `slidelineage` is retained only as a deprecated compatibility command. Migrate automation and examples to `slide-of-life`.
