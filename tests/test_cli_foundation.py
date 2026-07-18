"""Foundation tests for the SlideLineage CLI."""

from typer.testing import CliRunner

from slidelineage import __version__
from slidelineage.cli import app

runner = CliRunner()


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_help_succeeds_and_names_project() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "SlideLineage" in result.output


def test_version_succeeds_and_includes_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output
