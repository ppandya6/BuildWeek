"""Extract exactly one version section from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract(changelog: Path, version: str) -> str:
    text = changelog.read_text(encoding="utf-8")
    heading = re.compile(
        rf"^##[ \t]+{re.escape(version)}(?:[ \t]+-[^\n]*)?$", re.MULTILINE
    )
    matches = list(heading.finditer(text))
    if len(matches) != 1:
        count = len(matches)
        raise ValueError(
            f"expected exactly one changelog section for {version}; found {count}"
        )
    start = matches[0].start()
    following = re.search(r"^##[ \t]+", text[matches[0].end() :], re.MULTILINE)
    end = matches[0].end() + following.start() if following else len(text)
    return text[start:end].rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    args = parser.parse_args()
    try:
        notes = extract(args.changelog, args.version)
    except ValueError as error:
        parser.error(str(error))
    args.output.write_text(notes, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
