# Secure publication checklist

- [ ] Runtime, metadata, exact tag, and one changelog section agree.
- [ ] Cross-platform CI, skill validation, and the manual dry run pass.
- [ ] The protected `pypi` environment has reviewers, no self-review where
      available, tag-only restrictions, and no secrets.
- [ ] The matching Trusted Publisher is configured on PyPI (not merely in YAML).
- [ ] Wheel and sdist contents, Twine results, and `SHA256SUMS` are reviewed.
- [ ] Clean artifact installation and deterministic synthetic audit pass.
- [ ] Provenance/attestation is reviewed where the repository plan supports it.
- [ ] Security/privacy review confirms no credentials, raw datasets, API tokens,
      generated audits, or unsupported scientific claims are present.
- [ ] An authorized reviewer grants explicit environment approval.
- [ ] The rollback/yank plan is understood before publication.
- [ ] The PyPI page, metadata, hashes, and clean install are verified.
- [ ] The GitHub release attachments, notes, and prerelease/stable flag are verified.
