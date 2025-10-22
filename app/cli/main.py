"""Main CLI entry point for TeckoChecker.

This module sets up the Typer application and registers all commands.
"""

import typer
from typing import Optional

from app.cli.utils import print_banner, console
from app.cli import commands


# Create the main Typer app
app = typer.Typer(
    name="teckochecker",
    help="TeckoChecker - Polling orchestration for async workflows",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def version_callback(value: bool):
    """Show version information."""
    if value:
        console.print("[cyan]TeckoChecker[/cyan] version [bold]0.1.0[/bold]")
        console.print("Polling orchestration for async workflows")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version information",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output",
    ),
):
    """
    TeckoChecker - Polling orchestration for async workflows.

    Monitor OpenAI batch jobs and trigger Keboola workflows automatically.
    """
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")


# Register command groups
app.add_typer(commands.secret_app, name="secret")
app.add_typer(commands.job_app, name="job")

# Register standalone commands
app.command(name="init")(commands.init)
app.command(name="status")(commands.status)
app.command(name="start")(commands.start)
app.command(name="stop")(commands.stop)
app.command(name="install-completion")(commands.install_completion)
app.command(name="show-completion")(commands.show_completion)


def run():
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    run()
