# Release process

This repository currently prepares release candidates only; **nothing in this task
publishes to PyPI or creates a tag or GitHub release**. The Agent Skill is included
in the source distribution for repository users, but intentionally excluded from
the wheel because the runtime CLI does not depend on it.

For a future explicitly approved release:

1. Confirm a clean, reviewed `main` and synchronize the runtime and distribution version.
2. Run formatting, lint, mypy, tests, skill validation, and `python scripts/validate_distribution.py`.
3. Run `python -m build` and `python -m twine check dist/*`; inspect both archive file lists.
4. Install and exercise the wheel and source distribution in clean environments.
5. Review privacy, dependencies, credentials, provenance, release notes, and archive contents.
6. In a separate approved task, create a reviewed or signed tag.
7. Use a protected GitHub environment and PyPI trusted publishing; do not use stored API tokens.
8. Verify the published metadata, hashes, installation, and CLI before creating release notes.

The build backend may embed archive timestamps, so matching names, metadata, and
file lists do not by themselves prove byte-for-byte reproducibility.
