from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = spec_from_file_location(
    "validate_distribution", ROOT / "scripts/validate_distribution.py"
)
assert SPEC and SPEC.loader
validate_distribution = module_from_spec(SPEC)
SPEC.loader.exec_module(validate_distribution)


def artifact_names(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).touch()
    return tmp_path


def test_checksum_is_allowed_but_not_passed_to_twine(tmp_path, monkeypatch):
    directory = artifact_names(
        tmp_path,
        "slide_of_life-0.1.0a1-py3-none-any.whl",
        "slide_of_life-0.1.0a1.tar.gz",
        "SHA256SUMS",
    )
    wheel, sdist, checksums = validate_distribution.classify_artifacts(directory)
    commands = []
    monkeypatch.setattr(
        validate_distribution,
        "run",
        lambda command: commands.append(command),
    )

    validate_distribution.check_distribution_metadata(wheel, sdist)

    assert checksums == directory / "SHA256SUMS"
    assert commands == [
        [
            validate_distribution.sys.executable,
            "-m",
            "twine",
            "check",
            str(wheel),
            str(sdist),
        ]
    ]
    assert str(checksums) not in commands[0]


@pytest.mark.parametrize(
    "names",
    [
        ("package.whl", "package.tar.gz", "unrelated.txt"),
        ("package.tar.gz",),
        ("package.whl",),
        ("package.whl", "duplicate.whl", "package.tar.gz"),
        ("package.whl", "package.tar.gz", "duplicate.tar.gz"),
    ],
    ids=["unexpected", "missing-wheel", "missing-sdist", "wheels", "sdists"],
)
def test_invalid_artifact_sets_fail_closed(tmp_path, names):
    directory = artifact_names(tmp_path, *names)

    with pytest.raises(RuntimeError):
        validate_distribution.classify_artifacts(directory)
