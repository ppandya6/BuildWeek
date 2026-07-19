# Secure release and publication process

Slide-of-Life `0.1.0a1` is a prerelease candidate, not a published-package claim.
The repository prepares a Trusted Publishing workflow; it does not configure the
PyPI publisher or GitHub environment. Publication always requires a reviewed tag
and a different human's environment approval.

## Roles and approval

- A **release preparer** updates the version and changelog, runs the dry run, and
  proposes the exact tag. This role must not approve its own deployment.
- A **reviewer** checks tests, archives, `SHA256SUMS`, release notes, provenance
  (when available), and version/tag agreement.
- An authorized **environment approver** permits the `pypi` deployment only after
  all checks pass. Enable “prevent self-review” where the plan supports it.

No workflow stores a PyPI username, password, API token, or repository secret.
Never publish without explicit authorization.

## One-time repository setup

The guarded `.github/workflows/publish.yml` accepts manual dry runs and version
tags only. It builds once, validates and uploads the candidate, then reuses that
workflow-run artifact. The existing `release.yml` remains a nonpublishing release
candidate builder.

Pin and review every release action by immutable commit. The repository identity
is finalized as `ppandya6/Slide-of-Life`; any future identity change must happen
before Trusted Publisher registration because it changes Action references,
documentation/release URLs, and the publisher's repository identity.

## One-time GitHub environment setup

In repository **Settings → Environments**, create `pypi` manually:

1. Add required reviewers and require explicit approval.
2. Prevent self-review where available.
3. Restrict deployments to protected tags and allow only the reviewed `v*`
   release-tag pattern; do not permit branch deployments.
4. Add no environment secrets.

Environment protection options depend on repository visibility and GitHub plan.
Repository YAML cannot establish these administrative protections.

## One-time PyPI project/account setup

After the project exists and before production, an owner must register a PyPI
Trusted Publisher for owner `ppandya6`, repository `Slide-of-Life`, workflow
`publish.yml`, and environment `pypi`. Confirm these values on PyPI rather than
assuming repository code configured them. The publish job requests an OIDC token
and supplies no password. PyPI and TestPyPI have separate publisher configuration.

## Version and changelog preparation

1. Update `src/slidelineage/__init__.py` to the canonical PEP 440 version.
2. Confirm installed package metadata reports the same version.
3. Add exactly one `## <version> - ...` section to `CHANGELOG.md`; never invent
   notes or scientific claims.
4. For production, use exactly `v<version>` (for example `v0.1.0a1`). A PEP 440
   prerelease creates a GitHub prerelease; a stable version creates a normal
   release and is not automatically treated as the newest stable release by this
   workflow.

## Local validation and release-candidate dry run

From a clean checkout run:

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
python scripts/validate_skill.py
pytest -q
python scripts/validate_distribution.py
python scripts/generate_checksums.py dist
python scripts/extract_release_notes.py 0.1.0a1 --output release-notes.md
python scripts/validate_release_ref.py --version 0.1.0a1 --dry-run
```

Then manually dispatch **Guarded package publication** with the exact version.
Manual dispatch is unconditionally dry-run: it runs gates, builds and validates
wheel/sdist once, creates checksums, performs isolated local-wheel verification,
uploads candidate artifacts, and reports `DRY RUN: NOTHING WAS PUBLISHED`. It
cannot call PyPI or create a GitHub release.

## Per-release production execution

1. Require green CI and a reviewed manual dry run; inspect archive contents,
   checksums, extracted notes, dependency changes, and privacy boundaries.
2. Obtain explicit authorization, then separately create and push the exact tag
   from a clean commit contained in `main`. Ordinary maintenance tasks must never
   create tags.
3. The tag run performs preflight, one build, Twine check, distribution validation,
   checksum generation, artifact upload/download, and an approval gate.
4. The `pypi` environment approver confirms the tag, version, changelog, artifacts,
   and rollback plan. Approval allows the exact downloaded artifacts to be
   attested where supported and published using PyPI Trusted Publishing.
5. A clean environment installs `slide-of-life==<version>` from PyPI, checks
   metadata and module location, exercises help/version and a deterministic
   synthetic audit, and verifies report artifacts.
6. Only then does GitHub CLI create `Slide-of-Life <version>` with the wheel,
   sdist, checksums, and exact changelog notes. `0.1.0a1` is marked prerelease and
   is not marked latest stable.

Any invariant failure stops downstream jobs. The publish job never rebuilds.
Artifact attestations require `id-token: write` and `attestations: write` in that
protected job; availability and visibility depend on GitHub repository visibility
and plan. Their absence must not be described as proof of artifact safety.

## Post-release verification and rollback

Verify the PyPI project/version page, hashes, metadata, install, CLI output, module
location, synthetic report files, GitHub attachments, notes, and prerelease flag.
If publication is defective, stop further release creation where possible, retain
evidence, notify maintainers, and follow PyPI's project-management guidance to
yank (rather than silently replace) a release. Published files and versions are
immutable; fix forward with a new version. Understand this plan before approval.

## Optional TestPyPI rehearsal

TestPyPI is a separate, optional future rehearsal and is not a target of the
current workflow. It requires its own Trusted Publisher registration and protected
environment. Never reuse assumptions from PyPI, and do not introduce API tokens.

## Official references

- [PyPI: Adding a Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [PyPI: Using a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [PyPA publish action](https://github.com/pypa/gh-action-pypi-publish)
- [GitHub: OIDC in PyPI](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-pypi)
- [GitHub: Managing environments](https://docs.github.com/actions/deployment/targeting-different-environments/managing-environments-for-deployment)
- [GitHub: Artifact attestations](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations)
- [GitHub CLI: `gh release create`](https://cli.github.com/manual/gh_release_create)
