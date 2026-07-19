"""Prepare and validate the distributions passed to the PyPI publishing action."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def validate_publication_directory(directory: Path) -> None:
    """Require exactly one wheel and one sdist, with no other files."""
    files = sorted(path for path in directory.iterdir() if path.is_file())
    wheels = [path for path in files if path.suffix == ".whl"]
    sdists = [path for path in files if path.name.endswith(".tar.gz")]
    expected = {*wheels, *sdists}

    if len(wheels) != 1:
        raise ValueError(f"expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        raise ValueError(
            f"expected exactly one source distribution, found {len(sdists)}"
        )
    unexpected = [path.name for path in files if path not in expected]
    if unexpected:
        raise ValueError(f"unexpected publication files: {', '.join(unexpected)}")
    directories = sorted(path.name for path in directory.iterdir() if path.is_dir())
    if directories:
        raise ValueError(
            f"unexpected publication directories: {', '.join(directories)}"
        )


def prepare_publication_directory(source: Path, destination: Path) -> None:
    """Copy only the single wheel and single sdist into a clean destination."""
    wheels = sorted(source.glob("*.whl"))
    sdists = sorted(source.glob("*.tar.gz"))
    if len(wheels) != 1:
        raise ValueError(f"expected exactly one source wheel, found {len(wheels)}")
    if len(sdists) != 1:
        raise ValueError(
            f"expected exactly one source distribution, found {len(sdists)}"
        )

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for artifact in (*wheels, *sdists):
        shutil.copy2(artifact, destination / artifact.name)
    validate_publication_directory(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        if args.destination is not None:
            parser.error("--check accepts one publication directory")
        validate_publication_directory(args.source)
    elif args.destination is None:
        parser.error("destination is required unless --check is used")
    else:
        prepare_publication_directory(args.source, args.destination)


if __name__ == "__main__":
    main()
