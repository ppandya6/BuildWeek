import re
import tomllib
from datetime import date
from importlib.metadata import distribution
from pathlib import Path

from slidelineage import __version__

ROOT = Path(__file__).parents[1]


def metadata():
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_runtime_and_distribution_versions_match():
    assert __version__ == "0.1.0a1"
    assert distribution("slide-of-life").version == __version__


def test_metadata_and_entry_points():
    project = metadata()["project"]
    assert project["name"] == "slide-of-life"
    assert project["scripts"] == {
        "slidelineage": "slidelineage.cli:compatibility_app",
        "slide-of-life": "slidelineage.cli:app",
    }
    assert "openai>=1.0" in project["optional-dependencies"]["ai"]
    assert all(not dep.lower().startswith("openai") for dep in project["dependencies"])


def test_release_documents_are_synchronized_and_safe():
    readme = (ROOT / "README.md").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert 'python -m pip install "slide-of-life==0.1.0a1"' in readme
    assert "Python 3.11 or newer is required" in readme
    assert "future PyPI release" not in readme
    assert "https://github.com/ppandya6/Slide-of-Life" in readme
    assert "Codex" in readme and "GPT-5.6" in readme
    assert "alpha prerelease" in readme
    assert "not a clinical device" in readme
    assert "uses: ppandya6/Slide-of-Life@v0.1.0a1" in readme
    for option in (
        "--train examples/demo/generated/train_manifest.csv",
        "--test examples/demo/generated/test_manifest.csv",
        "--images examples/demo/generated/images",
        "--schema-map examples/demo/schema-map.yaml",
        "--output artifacts/demo-audit",
        "--repair",
        "--force",
    ):
        assert option in readme
    version_headings = re.findall(
        rf"^##\s+{re.escape(__version__)}\s+-\s+(.+)$", changelog, re.MULTILINE
    )
    assert len(version_headings) == 1
    release_label = version_headings[0]
    assert re.fullmatch(r"Unreleased|\d{4}-\d{2}-\d{2}", release_label)
    if release_label != "Unreleased":
        date.fromisoformat(release_label)
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    assert (
        "pypi" not in workflow.lower()
        and "id-token: write" not in workflow
        and "permissions:\n  contents: read" in workflow
    )
