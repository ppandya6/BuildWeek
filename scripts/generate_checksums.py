"""Generate deterministic SHA-256 checksums for Python distributions."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

CHECKSUM_NAME = "SHA256SUMS"


def generate(directory: Path) -> Path:
    if not directory.is_dir():
        raise ValueError(f"distribution directory does not exist: {directory}")
    entries = sorted(path for path in directory.iterdir() if path.name != CHECKSUM_NAME)
    if not entries:
        raise ValueError(f"no distributions found in {directory}")
    invalid = [
        path.name
        for path in entries
        if not path.is_file() or not path.name.endswith((".whl", ".tar.gz"))
    ]
    if invalid:
        raise ValueError(f"unexpected distribution entries: {', '.join(invalid)}")
    wheels = [path for path in entries if path.name.endswith(".whl")]
    sdists = [path for path in entries if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("expected exactly one wheel and one source distribution")
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in entries
    ]
    output = directory / CHECKSUM_NAME
    output.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        output = generate(args.directory)
    except ValueError as error:
        parser.error(str(error))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
