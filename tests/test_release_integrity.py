from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_release_notes import extract  # noqa: E402
from generate_checksums import generate  # noqa: E402


def test_generate_checksums_is_sorted_relative_and_repeatable(tmp_path: Path):
    wheel = tmp_path / "z.whl"
    sdist = tmp_path / "a.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    output = generate(tmp_path)
    expected = (
        f"{hashlib.sha256(b'sdist').hexdigest()}  a.tar.gz\n"
        f"{hashlib.sha256(b'wheel').hexdigest()}  z.whl\n"
    )
    assert output.read_text(encoding="ascii") == expected
    assert generate(tmp_path).read_text(encoding="ascii") == expected
    assert str(tmp_path) not in expected


@pytest.mark.parametrize("name", ["extra.zip", "README", "nested"])
def test_generate_checksums_rejects_unexpected_entries(tmp_path: Path, name: str):
    (tmp_path / "a.whl").write_bytes(b"wheel")
    (tmp_path / "a.tar.gz").write_bytes(b"sdist")
    unexpected = tmp_path / name
    unexpected.mkdir() if name == "nested" else unexpected.write_text("bad")
    with pytest.raises(ValueError, match="unexpected distribution entries"):
        generate(tmp_path)


def test_extract_release_notes_preserves_requested_markdown(tmp_path: Path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Log\n\n## 2.0 - Unreleased\n\n- **safe** note\n\n## 1.0\n\nold\n",
        encoding="utf-8",
    )
    assert extract(changelog, "2.0") == "## 2.0 - Unreleased\n\n- **safe** note\n"


@pytest.mark.parametrize(
    "text, message",
    [("# Log\n", "found 0"), ("## 1.0\na\n## 1.0\nb\n", "found 2")],
)
def test_extract_release_notes_requires_one_section(
    tmp_path: Path, text: str, message: str
):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        extract(changelog, "1.0")
