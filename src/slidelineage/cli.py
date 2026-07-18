"""Command-line interface for the SlideLineage foundation."""

from typing import Annotated

import typer

from slidelineage import __version__

APP_NAME = "SlideLineage"
APP_PURPOSE = (
    "Local deterministic-first tooling for auditing computational-pathology "
    "train/test partition lineage."
)
DOCS_HINT = (
    "See docs/product-spec.md and docs/scientific-method.md for milestone scope."
)

app = typer.Typer(
    name="slidelineage",
    help=f"{APP_NAME}: {APP_PURPOSE} Task 1 provides repository foundation only.",
    no_args_is_help=False,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{APP_NAME} {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the SlideLineage version and exit.",
        ),
    ] = False,
) -> None:
    """Show foundation guidance until the audit pipeline is implemented."""
    _ = version
    typer.echo(f"{APP_NAME} {__version__}")
    typer.echo(APP_PURPOSE)
    typer.echo(
        "The audit pipeline is planned for a later milestone; "
        "it is not implemented in Task 1."
    )
    typer.echo(DOCS_HINT)
