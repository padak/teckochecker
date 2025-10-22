"""CLI commands for TeckoChecker.

This module implements all CLI commands for managing secrets, jobs, and the daemon.
"""

import sys
from typing import Optional
import typer
import httpx

from app.cli.utils import (
    print_success,
    print_error,
    print_warning,
    print_info,
    confirm_action,
    prompt_input,
    print_secrets_table,
    print_jobs_table,
    print_job_details,
    print_status,
    print_banner,
    console,
)


# Base API URL - should come from config in real implementation
API_BASE_URL = "http://localhost:8000/api"


# Create sub-apps for command groups
secret_app = typer.Typer(help="Manage secrets (API keys and tokens)")
job_app = typer.Typer(help="Manage polling jobs")


def get_api_client() -> httpx.Client:
    """Get an HTTP client for API requests.

    Returns:
        Configured HTTP client
    """
    return httpx.Client(base_url=API_BASE_URL, timeout=30.0)


def handle_api_error(e: Exception, operation: str) -> None:
    """Handle API errors and display appropriate messages.

    Args:
        e: The exception that occurred
        operation: Description of the operation that failed
    """
    if isinstance(e, httpx.ConnectError):
        print_error(f"Cannot connect to TeckoChecker API. Is the daemon running?")
        print_info("Try: teckochecker start")
    elif isinstance(e, httpx.HTTPStatusError):
        print_error(f"API error during {operation}: {e.response.status_code}")
        try:
            error_detail = e.response.json().get("detail", str(e))
            print_error(f"Details: {error_detail}")
        except Exception:
            print_error(f"Details: {e.response.text}")
    else:
        print_error(f"Error during {operation}: {str(e)}")


# =============================================================================
# INIT COMMAND
# =============================================================================

def init():
    """
    Initialize TeckoChecker database and configuration.

    Creates the necessary database tables and sets up the initial configuration.
    This command should be run once before using TeckoChecker.
    """
    print_banner()
    print_info("Initializing TeckoChecker...")

    try:
        client = get_api_client()
        response = client.post("/admin/init")
        response.raise_for_status()

        result = response.json()
        print_success("Database initialized successfully!")

        if result.get("tables_created"):
            print_info(f"Created tables: {', '.join(result['tables_created'])}")

    except Exception as e:
        handle_api_error(e, "initialization")
        sys.exit(1)


# =============================================================================
# SECRET COMMANDS
# =============================================================================

@secret_app.command("add")
def secret_add(
    name: str = typer.Option(..., "--name", "-n", help="Unique name for the secret"),
    secret_type: str = typer.Option(
        ...,
        "--type",
        "-t",
        help="Type of secret: 'openai' or 'keboola'",
    ),
    value: Optional[str] = typer.Option(
        None,
        "--value",
        "-v",
        help="Secret value (will prompt if not provided)",
    ),
):
    """
    Add a new secret (API key or token).

    Secrets are encrypted and stored securely in the database.
    """
    # Validate secret type
    if secret_type not in ["openai", "keboola"]:
        print_error("Secret type must be 'openai' or 'keboola'")
        sys.exit(1)

    # Prompt for value if not provided
    if not value:
        value = prompt_input(
            f"Enter {secret_type} secret value",
            password=True,
        )

    if not value:
        print_error("Secret value cannot be empty")
        sys.exit(1)

    try:
        client = get_api_client()
        response = client.post(
            "/admin/secrets",
            json={
                "name": name,
                "type": secret_type,
                "value": value,
            },
        )
        response.raise_for_status()

        secret = response.json()
        print_success(f"Secret '{name}' (ID: {secret['id']}) added successfully!")

    except Exception as e:
        handle_api_error(e, "adding secret")
        sys.exit(1)


@secret_app.command("list")
def secret_list():
    """
    List all secrets (without showing values).

    Displays secret names, types, and creation timestamps.
    """
    try:
        client = get_api_client()
        response = client.get("/admin/secrets")
        response.raise_for_status()

        data = response.json()
        secrets = data.get("secrets", [])
        print_secrets_table(secrets)

    except Exception as e:
        handle_api_error(e, "listing secrets")
        sys.exit(1)


@secret_app.command("delete")
def secret_delete(
    name: str = typer.Argument(..., help="Name of the secret to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """
    Delete a secret.

    Warning: Cannot delete secrets that are referenced by active jobs.
    """
    if not force:
        if not confirm_action(f"Delete secret '{name}'?", default=False):
            print_info("Cancelled.")
            return

    try:
        client = get_api_client()
        # First get the secret ID by name
        response = client.get("/admin/secrets")
        response.raise_for_status()
        secrets = response.json()

        secret = next((s for s in secrets if s["name"] == name), None)
        if not secret:
            print_error(f"Secret '{name}' not found")
            sys.exit(1)

        # Delete the secret
        response = client.delete(f"/admin/secrets/{secret['id']}")
        response.raise_for_status()

        print_success(f"Secret '{name}' deleted successfully!")

    except Exception as e:
        handle_api_error(e, "deleting secret")
        sys.exit(1)


# =============================================================================
# JOB COMMANDS
# =============================================================================

@job_app.command("create")
def job_create(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    batch_id: str = typer.Option(..., "--batch-id", "-b", help="OpenAI batch ID to monitor"),
    openai_secret: str = typer.Option(
        ...,
        "--openai-secret",
        help="Name of OpenAI secret to use",
    ),
    keboola_secret: str = typer.Option(
        ...,
        "--keboola-secret",
        help="Name of Keboola secret to use",
    ),
    keboola_stack: str = typer.Option(
        ...,
        "--keboola-stack",
        help="Keboola stack URL (e.g., https://connection.keboola.com)",
    ),
    config_id: str = typer.Option(
        ...,
        "--config-id",
        help="Keboola configuration ID to trigger",
    ),
    poll_interval: int = typer.Option(
        120,
        "--poll-interval",
        "-i",
        help="Polling interval in seconds (default: 120)",
        min=30,
        max=3600,
    ),
):
    """
    Create a new polling job.

    This will start monitoring the specified OpenAI batch job and trigger
    the Keboola configuration when it completes.
    """
    try:
        client = get_api_client()

        # First, resolve secret names to IDs
        response = client.get("/admin/secrets")
        response.raise_for_status()
        secrets = response.json()

        openai_secret_obj = next((s for s in secrets if s["name"] == openai_secret), None)
        keboola_secret_obj = next((s for s in secrets if s["name"] == keboola_secret), None)

        if not openai_secret_obj:
            print_error(f"OpenAI secret '{openai_secret}' not found")
            sys.exit(1)

        if not keboola_secret_obj:
            print_error(f"Keboola secret '{keboola_secret}' not found")
            sys.exit(1)

        # Create the job
        response = client.post(
            "/jobs",
            json={
                "name": name,
                "batch_id": batch_id,
                "openai_secret_id": openai_secret_obj["id"],
                "keboola_secret_id": keboola_secret_obj["id"],
                "keboola_stack_url": keboola_stack,
                "keboola_configuration_id": config_id,
                "poll_interval_seconds": poll_interval,
            },
        )
        response.raise_for_status()

        job = response.json()
        print_success(f"Job '{name}' (ID: {job['id']}) created successfully!")
        print_info(f"Polling every {poll_interval} seconds")

    except Exception as e:
        handle_api_error(e, "creating job")
        sys.exit(1)


@job_app.command("list")
def job_list(
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: active, paused, completed, failed",
    ),
):
    """
    List all polling jobs.

    Optionally filter by status.
    """
    try:
        client = get_api_client()
        url = "/jobs"
        if status:
            url += f"?status={status}"

        response = client.get(url)
        response.raise_for_status()

        data = response.json()
        jobs = data.get("jobs", [])
        print_jobs_table(jobs)

    except Exception as e:
        handle_api_error(e, "listing jobs")
        sys.exit(1)


@job_app.command("show")
def job_show(
    job_id: int = typer.Argument(..., help="Job ID to display"),
):
    """
    Show detailed information about a specific job.
    """
    try:
        client = get_api_client()
        response = client.get(f"/jobs/{job_id}")
        response.raise_for_status()

        job = response.json()
        print_job_details(job)

    except Exception as e:
        handle_api_error(e, "fetching job details")
        sys.exit(1)


@job_app.command("pause")
def job_pause(
    job_id: int = typer.Argument(..., help="Job ID to pause"),
):
    """
    Pause a polling job.

    The job will stop polling until resumed.
    """
    try:
        client = get_api_client()
        response = client.post(f"/jobs/{job_id}/pause")
        response.raise_for_status()

        print_success(f"Job {job_id} paused successfully!")

    except Exception as e:
        handle_api_error(e, "pausing job")
        sys.exit(1)


@job_app.command("resume")
def job_resume(
    job_id: int = typer.Argument(..., help="Job ID to resume"),
):
    """
    Resume a paused polling job.

    The job will start polling again at the configured interval.
    """
    try:
        client = get_api_client()
        response = client.post(f"/jobs/{job_id}/resume")
        response.raise_for_status()

        print_success(f"Job {job_id} resumed successfully!")

    except Exception as e:
        handle_api_error(e, "resuming job")
        sys.exit(1)


@job_app.command("delete")
def job_delete(
    job_id: int = typer.Argument(..., help="Job ID to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """
    Delete a polling job.

    This will remove the job and all its associated logs.
    """
    if not force:
        if not confirm_action(f"Delete job {job_id}?", default=False):
            print_info("Cancelled.")
            return

    try:
        client = get_api_client()
        response = client.delete(f"/jobs/{job_id}")
        response.raise_for_status()

        print_success(f"Job {job_id} deleted successfully!")

    except Exception as e:
        handle_api_error(e, "deleting job")
        sys.exit(1)


# =============================================================================
# STATUS COMMAND
# =============================================================================

def status():
    """
    Show TeckoChecker system status.

    Displays daemon status, job counts, and system health.
    """
    try:
        client = get_api_client()
        response = client.get("/health")
        response.raise_for_status()

        status_data = response.json()
        print_status(status_data)

    except Exception as e:
        handle_api_error(e, "fetching status")
        sys.exit(1)


# =============================================================================
# DAEMON MANAGEMENT COMMANDS
# =============================================================================

def start(
    daemon: bool = typer.Option(
        False,
        "--daemon",
        "-d",
        help="Run in background as daemon",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to run the API server on",
    ),
):
    """
    Start the TeckoChecker polling service.

    This starts the FastAPI server and begins polling jobs.
    """
    print_info("Starting TeckoChecker daemon...")

    try:
        if daemon:
            # In production, this would use a proper daemon implementation
            import subprocess

            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(port),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print_success(f"TeckoChecker daemon started on port {port}")
        else:
            # Run in foreground
            import uvicorn

            print_info(f"Starting TeckoChecker on port {port} (press Ctrl+C to stop)...")
            uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")

    except KeyboardInterrupt:
        print_info("\nShutting down gracefully...")
    except Exception as e:
        print_error(f"Failed to start daemon: {str(e)}")
        sys.exit(1)


def stop():
    """
    Stop the TeckoChecker polling service.

    This gracefully shuts down the daemon.
    """
    print_info("Stopping TeckoChecker daemon...")

    try:
        # In production, this would interact with a proper process manager
        import signal
        import subprocess

        # Find the uvicorn process
        result = subprocess.run(
            ["pgrep", "-f", "uvicorn.*app.main:app"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    try:
                        import os
                        os.kill(int(pid), signal.SIGTERM)
                        print_success(f"Stopped process {pid}")
                    except ProcessLookupError:
                        pass

            print_success("TeckoChecker daemon stopped")
        else:
            print_warning("No TeckoChecker daemon process found")

    except Exception as e:
        print_error(f"Failed to stop daemon: {str(e)}")
        sys.exit(1)


# =============================================================================
# SHELL COMPLETION COMMANDS
# =============================================================================

def install_completion(
    shell: Optional[str] = typer.Argument(
        None,
        help="Shell to install completion for (bash, zsh, fish, powershell)",
    ),
):
    """
    Install shell completion for TeckoChecker.

    Automatically detects your shell if not specified.
    """
    print_info("Installing shell completion...")

    try:
        from typer.completion import install as install_typer_completion

        result = install_typer_completion(prog_name="teckochecker", shell=shell)

        if result:
            print_success("Shell completion installed successfully!")
            print_info("Restart your shell or source your profile for changes to take effect.")
        else:
            print_warning("Shell completion installation may have failed.")

    except Exception as e:
        print_error(f"Failed to install completion: {str(e)}")
        sys.exit(1)


def show_completion(
    shell: Optional[str] = typer.Argument(
        None,
        help="Shell to show completion for (bash, zsh, fish, powershell)",
    ),
):
    """
    Show shell completion script.

    Use this to manually add completion to your shell configuration.
    """
    try:
        from typer.completion import show_completion as show_typer_completion

        result = show_typer_completion(prog_name="teckochecker", shell=shell)
        console.print(result)

    except Exception as e:
        print_error(f"Failed to show completion: {str(e)}")
        sys.exit(1)
