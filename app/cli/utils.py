"""CLI utility functions for TeckoChecker.

This module provides helper functions for pretty printing, confirmations, and progress indicators.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import box


console = Console()


def print_success(message: str) -> None:
    """Print a success message in green.

    Args:
        message: The success message to display
    """
    console.print(f"[green]:heavy_check_mark: {message}[/green]")


def print_error(message: str) -> None:
    """Print an error message in red.

    Args:
        message: The error message to display
    """
    console.print(f"[red]:x: {message}[/red]")


def print_warning(message: str) -> None:
    """Print a warning message in yellow.

    Args:
        message: The warning message to display
    """
    console.print(f"[yellow]:warning: {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message in blue.

    Args:
        message: The info message to display
    """
    console.print(f"[blue]:information: {message}[/blue]")


def confirm_action(message: str, default: bool = False) -> bool:
    """Display a confirmation prompt.

    Args:
        message: The confirmation message to display
        default: The default response if user presses Enter

    Returns:
        True if user confirms, False otherwise
    """
    return Confirm.ask(message, default=default)


def prompt_input(message: str, password: bool = False, default: Optional[str] = None) -> str:
    """Prompt user for input.

    Args:
        message: The prompt message to display
        password: If True, hide the input
        default: Default value if user presses Enter

    Returns:
        The user's input
    """
    return Prompt.ask(message, password=password, default=default)


def print_table(
    title: str,
    columns: List[Dict[str, str]],
    rows: List[List[Any]],
    show_header: bool = True,
) -> None:
    """Print a formatted table.

    Args:
        title: The table title
        columns: List of column definitions with 'name' and optional 'style'
        rows: List of row data
        show_header: Whether to show the header row
    """
    table = Table(
        title=title,
        show_header=show_header,
        header_style="bold magenta",
        box=box.ROUNDED,
        title_style="bold cyan",
    )

    # Add columns
    for col in columns:
        table.add_column(
            col["name"],
            style=col.get("style", ""),
            no_wrap=col.get("no_wrap", False),
        )

    # Add rows
    for row in rows:
        table.add_row(*[str(cell) if cell is not None else "-" for cell in row])

    console.print(table)


def print_secrets_table(secrets: List[Dict[str, Any]]) -> None:
    """Print a formatted table of secrets.

    Args:
        secrets: List of secret dictionaries
    """
    if not secrets:
        print_info("No secrets found.")
        return

    columns = [
        {"name": "ID", "style": "cyan"},
        {"name": "Name", "style": "green"},
        {"name": "Type", "style": "yellow"},
        {"name": "Created At", "style": "dim"},
    ]

    rows = [
        [
            secret["id"],
            secret["name"],
            secret["type"],
            format_datetime(secret.get("created_at")),
        ]
        for secret in secrets
    ]

    print_table("Secrets", columns, rows)


def print_jobs_table(jobs: List[Dict[str, Any]]) -> None:
    """Print a formatted table of polling jobs.

    Args:
        jobs: List of job dictionaries
    """
    if not jobs:
        print_info("No jobs found.")
        return

    columns = [
        {"name": "ID", "style": "cyan"},
        {"name": "Name", "style": "green"},
        {"name": "Batch ID", "style": "yellow", "no_wrap": True},
        {"name": "Status", "style": ""},
        {"name": "Poll Interval", "style": "dim"},
        {"name": "Last Check", "style": "dim"},
    ]

    rows = [
        [
            job["id"],
            job["name"],
            truncate_string(job.get("batch_id", ""), 20),
            format_status(job["status"]),
            f"{job.get('poll_interval_seconds', 0)}s",
            format_datetime(job.get("last_check_at")),
        ]
        for job in jobs
    ]

    print_table("Polling Jobs", columns, rows)


def print_job_details(job: Dict[str, Any]) -> None:
    """Print detailed information about a single job.

    Args:
        job: Job dictionary with detailed information
    """
    details = f"""
[bold cyan]Job Details[/bold cyan]

[bold]ID:[/bold] {job['id']}
[bold]Name:[/bold] {job['name']}
[bold]Batch ID:[/bold] {job.get('batch_id', 'N/A')}
[bold]Status:[/bold] {format_status(job['status'])}

[bold cyan]Configuration[/bold cyan]
[bold]OpenAI Secret:[/bold] {job.get('openai_secret_name', 'N/A')} (ID: {job.get('openai_secret_id', 'N/A')})
[bold]Keboola Secret:[/bold] {job.get('keboola_secret_name', 'N/A')} (ID: {job.get('keboola_secret_id', 'N/A')})
[bold]Keboola Stack:[/bold] {job.get('keboola_stack_url', 'N/A')}
[bold]Config ID:[/bold] {job.get('keboola_configuration_id', 'N/A')}
[bold]Poll Interval:[/bold] {job.get('poll_interval_seconds', 0)} seconds

[bold cyan]Timestamps[/bold cyan]
[bold]Created:[/bold] {format_datetime(job.get('created_at'))}
[bold]Last Check:[/bold] {format_datetime(job.get('last_check_at'))}
[bold]Next Check:[/bold] {format_datetime(job.get('next_check_at'))}
[bold]Completed:[/bold] {format_datetime(job.get('completed_at'))}
"""

    console.print(Panel(details.strip(), border_style="cyan"))


def print_status(status: Dict[str, Any]) -> None:
    """Print system status information.

    Args:
        status: Status dictionary with system information
    """
    status_text = f"""
[bold cyan]TeckoChecker System Status[/bold cyan]

[bold]Daemon Status:[/bold] {format_daemon_status(status.get('daemon_running', False))}
[bold]Active Jobs:[/bold] {status.get('active_jobs', 0)}
[bold]Paused Jobs:[/bold] {status.get('paused_jobs', 0)}
[bold]Completed Jobs:[/bold] {status.get('completed_jobs', 0)}
[bold]Failed Jobs:[/bold] {status.get('failed_jobs', 0)}
[bold]Total Jobs:[/bold] {status.get('total_jobs', 0)}

[bold]Database:[/bold] {status.get('database_status', 'Unknown')}
[bold]Uptime:[/bold] {status.get('uptime', 'N/A')}
[bold]Last Poll:[/bold] {format_datetime(status.get('last_poll_time'))}
"""

    console.print(Panel(status_text.strip(), border_style="cyan"))


def format_status(status: str) -> str:
    """Format job status with appropriate color.

    Args:
        status: The status string

    Returns:
        Formatted status string with color
    """
    status_colors = {
        "active": "green",
        "paused": "yellow",
        "completed": "blue",
        "failed": "red",
    }

    color = status_colors.get(status.lower(), "white")
    return f"[{color}]{status}[/{color}]"


def format_daemon_status(is_running: bool) -> str:
    """Format daemon status with appropriate color.

    Args:
        is_running: Whether the daemon is running

    Returns:
        Formatted status string
    """
    if is_running:
        return "[green]Running[/green]"
    return "[red]Stopped[/red]"


def format_datetime(dt: Optional[str]) -> str:
    """Format datetime for display.

    Args:
        dt: ISO format datetime string or None

    Returns:
        Formatted datetime string or "Never"
    """
    if not dt:
        return "Never"

    try:
        # Parse ISO format datetime
        if isinstance(dt, str):
            dt_obj = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        else:
            dt_obj = dt

        # Format for display
        return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return str(dt) if dt else "Never"


def truncate_string(s: str, length: int) -> str:
    """Truncate a string to specified length.

    Args:
        s: The string to truncate
        length: Maximum length

    Returns:
        Truncated string with ellipsis if needed
    """
    if len(s) <= length:
        return s
    return s[:length-3] + "..."


def show_progress(description: str):
    """Create a progress context manager for long operations.

    Args:
        description: Description of the operation

    Returns:
        Progress context manager
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )


def print_banner() -> None:
    """Print the TeckoChecker banner."""
    banner = """
[bold cyan]
╔╦╗┌─┐┌─┐┬┌─┌─┐╔═╗┬ ┬┌─┐┌─┐┬┌─┌─┐┬─┐
 ║ ├┤ │  ├┴┐│ │║  ├─┤├┤ │  ├┴┐├┤ ├┬┘
 ╩ └─┘└─┘┴ ┴└─┘╚═╝┴ ┴└─┘└─┘┴ ┴└─┘┴└─
[/bold cyan]
[dim]Polling orchestration for async workflows[/dim]
"""
    console.print(banner)


def print_help_hint(command: str) -> None:
    """Print a helpful hint about getting more help.

    Args:
        command: The command to get help for
    """
    console.print(f"\n[dim]Run [bold]{command} --help[/bold] for more information.[/dim]")
