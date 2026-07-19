"""Foundation tests for the Slide-of-Life CLI."""

import subprocess
import sys

from typer.testing import CliRunner

from slidelineage import __version__
from slidelineage.cli import app

runner = CliRunner()


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_help_succeeds_and_names_project() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Slide-of-Life" in result.output


def test_version_succeeds_and_includes_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_console_alias_warns_but_module_execution_does_not() -> None:
    alias = subprocess.run(
        ["slidelineage", "--help"], text=True, capture_output=True, check=False
    )
    assert alias.returncode == 0
    assert "retained for compatibility" in alias.stderr
    module = subprocess.run(
        [sys.executable, "-m", "slidelineage", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert module.returncode == 0
    assert "retained for compatibility" not in module.stderr + module.stdout
