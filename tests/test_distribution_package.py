import tomllib
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
    assert (
        "future PyPI release" in readme
        and "slide_of_life-0.1.0a1-py3-none-any.whl" in readme
    )
    assert f"## {__version__} - Unreleased" in changelog
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    assert (
        "pypi" not in workflow.lower()
        and "id-token: write" not in workflow
        and "permissions:\n  contents: read" in workflow
    )
