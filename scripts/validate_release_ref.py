"""Fail closed when a release version, Git ref, and repository disagree."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import subprocess
from pathlib import Path

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def validate(version_text: str, *, dry_run: bool, ref: str | None = None) -> Version:
    try:
        version = Version(version_text)
    except InvalidVersion as error:
        raise ValueError(f"invalid PEP 440 version: {version_text}") from error
    if str(version) != version_text:
        raise ValueError(f"version must use canonical PEP 440 form: {version}")
    runtime_text = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        (ROOT / "src/slidelineage/__init__.py").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if runtime_text is None or runtime_text.group(1) != version_text:
        raise ValueError("runtime version does not match supplied version")
    if importlib.metadata.version("slide-of-life") != version_text:
        raise ValueError("installed package metadata does not match supplied version")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if (
        len(
            re.findall(
                rf"^##\s+{re.escape(version_text)}(?:\s+-|\s*$)",
                changelog,
                re.MULTILINE,
            )
        )
        != 1
    ):
        raise ValueError("changelog must contain exactly one matching version section")
    status = git("status", "--porcelain", "--untracked-files=all")
    ignored = {"dist/", "release-notes.md"}
    dirty = [
        line
        for line in status.splitlines()
        if not any(line[3:].startswith(item) for item in ignored)
    ]
    if dirty:
        raise ValueError("working tree is not clean")
    expected_ref = f"v{version_text}"
    if not dry_run:
        actual_ref = ref or git("describe", "--tags", "--exact-match", "HEAD")
        if actual_ref != expected_ref:
            raise ValueError(f"release ref must be exactly {expected_ref}")
        git("merge-base", "--is-ancestor", "HEAD", "origin/main")
    elif ref is not None and ref != expected_ref:
        raise ValueError(f"dry-run ref, when supplied, must be exactly {expected_ref}")
    dist = ROOT / "dist"
    if dist.exists():
        expected = {
            f"slide_of_life-{version_text}-py3-none-any.whl",
            f"slide_of_life-{version_text}.tar.gz",
            "SHA256SUMS",
        }
        conflicts = sorted(
            path.name for path in dist.iterdir() if path.name not in expected
        )
        if conflicts:
            raise ValueError(
                f"conflicting distribution artifacts: {', '.join(conflicts)}"
            )
    release_kind = "prerelease" if version.is_prerelease else "release"
    print(
        f"validated {version_text}: GitHub {release_kind}; expected tag {expected_ref}"
    )
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--ref")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        validate(args.version, dry_run=args.dry_run, ref=args.ref)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
