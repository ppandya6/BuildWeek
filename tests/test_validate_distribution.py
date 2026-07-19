from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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


def test_wheel_metadata_has_parseable_project_identity(tmp_path):
    wheel = tmp_path / "slide_of_life-0.1.0a1-py3-none-any.whl"
    metadata_text = """\
Metadata-Version: 2.4
Name: slide-of-life
Version: 0.1.0a1
Requires-Python: >=3.11
Project-URL: Repository, https://github.com/ppandya6/Slide-of-Life

Synthetic package metadata fixture.
"""
    with ZipFile(wheel, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("slide_of_life-0.1.0a1.dist-info/METADATA", metadata_text)

    metadata = validate_distribution.inspect_wheel_metadata(wheel)

    assert metadata.metadata_version == "2.4"
    assert metadata.name == "slide-of-life"
    assert str(metadata.version) == "0.1.0a1"
    assert str(metadata.requires_python) == ">=3.11"


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
