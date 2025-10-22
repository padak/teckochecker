"""CLI commands for TeckoChecker.

This module implements all CLI commands for managing secrets, jobs, and the daemon.
"""

import sys
import logging
from typing import Optional
from pathlib import Path
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

# Import functions from init_db.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.init_db import initialize_database, create_env_file_if_needed


# Configure logging
logger = logging.getLogger(__name__)

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
        print_error("Cannot connect to TeckoChecker API. Is the daemon running?")
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


def init(
    generate_env: bool = typer.Option(
        False,
        "--generate-env",
        help="Automatically create .env file with generated SECRET_KEY",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Reset database (drop all tables and recreate)",
    ),
):
    """
    Initialize TeckoChecker database and configuration.

    Creates the necessary database tables and sets up the initial configuration.
    This command should be run once before using TeckoChecker.
    Does NOT require the API server to be running.
    """
    print_banner()
    print_info("Initializing TeckoChecker...")

    try:
        # Check if .env exists, warn if not (unless --generate-env is used)
        env_path = Path(__file__).parent.parent.parent / ".env"
        if not env_path.exists() and not generate_env:
            print_warning("No .env file found!")
            print_info(
                "Run with --generate-env flag to create one automatically, or create it manually from .env.example"
            )
            response = input("Continue anyway? (y/N): ")
            if response.lower() != "y":
                print_info("Aborted.")
                sys.exit(1)
            print()

        # Generate .env file if requested
        if generate_env:
            create_env_file_if_needed()

        # Initialize database
        initialize_database(reset=reset)

    except KeyboardInterrupt:
        print_info("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Initialization failed: {str(e)}")
        sys.exit(1)


# =============================================================================
# SETUP COMMAND
# =============================================================================


def setup():
    """
    Interactive setup wizard for TeckoChecker.

    Guides you through the initial configuration process including
    generating .env file and initializing the database.
    """
    print_banner()
    print_info("Welcome to TeckoChecker setup wizard!")
    print_info("This will help you get started with TeckoChecker.")
    print()

    try:
        # Check if .env exists
        env_path = Path(__file__).parent.parent.parent / ".env"

        if not env_path.exists():
            print_info("Step 1: Environment Configuration")
            print_info("No .env file found. A .env file is required for TeckoChecker to work.")
            response = input(
                "Would you like to generate a .env file with a secure SECRET_KEY? (Y/n): "
            )
            if response.lower() != "n":
                create_env_file_if_needed()
            else:
                print_warning(
                    "Skipping .env generation. Please create one manually from .env.example"
                )
            print()
        else:
            print_success("Step 1: Environment Configuration - .env file already exists")
            print()

        # Ask about database initialization
        print_info("Step 2: Database Initialization")
        print_info("TeckoChecker needs to initialize the database tables.")
        response = input("Would you like to initialize the database now? (Y/n): ")
        if response.lower() != "n":
            initialize_database(reset=False)
        else:
            print_warning(
                "Skipping database initialization. Run 'teckochecker init' later to set up the database."
            )
            print()

        # Show success and next steps
        print()
        print_success("Setup complete!")
        print()
        print_info("Next steps:")
        print_info("  1. Add secrets: teckochecker secret add --name <name> --type <type>")
        print_info("  2. Create jobs: teckochecker job create ...")
        print_info("  3. Start polling: teckochecker start")
        print()

    except KeyboardInterrupt:
        print_info("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Setup failed: {str(e)}")
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
        secrets_data = response.json()
        secrets = secrets_data.get("secrets", [])

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
    component_id: str = typer.Option(
        ...,
        "--component-id",
        help="Keboola component ID (e.g., kds-team.app-custom-python)",
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
        secrets_data = response.json()
        secrets = secrets_data.get("secrets", [])

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
                "keboola_component_id": component_id,
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

        # First, check if daemon is running by trying to connect
        daemon_running = False
        database_status = "Unknown"

        # Get health status
        try:
            health_response = client.get("/health")
            health_response.raise_for_status()
            health_data = health_response.json()
            daemon_running = True  # If we can connect, daemon is running
            database_status = health_data.get("database", "Unknown")
        except httpx.ConnectError:
            # Can't connect - daemon is not running
            daemon_running = False
        except Exception:
            # Other errors - daemon might be running but unhealthy
            daemon_running = True
            database_status = "Error"

        # Get statistics if daemon is running
        status_data = {
            "daemon_running": daemon_running,
            "database_status": database_status.capitalize() if database_status else "Unknown",
            "active_jobs": 0,
            "paused_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "total_jobs": 0,
            "uptime": "N/A",
            "last_poll_time": None,
        }

        if daemon_running:
            try:
                stats_response = client.get("/stats")
                stats_response.raise_for_status()
                stats_data = stats_response.json()

                # Update status data with stats
                status_data.update(
                    {
                        "active_jobs": stats_data.get("active_jobs", 0),
                        "paused_jobs": stats_data.get("paused_jobs", 0),
                        "completed_jobs": stats_data.get("completed_jobs", 0),
                        "failed_jobs": stats_data.get("failed_jobs", 0),
                        "total_jobs": stats_data.get("total_jobs", 0),
                    }
                )

                # Format uptime if available
                uptime_seconds = stats_data.get("uptime_seconds")
                if uptime_seconds is not None:
                    hours = int(uptime_seconds // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    seconds = int(uptime_seconds % 60)
                    status_data["uptime"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            except Exception as e:
                # If we can't get stats, just show the basic info
                logger.debug(f"Could not fetch stats: {e}")

        print_status(status_data)

    except httpx.ConnectError:
        # Special handling for when daemon is not running at all
        status_data = {
            "daemon_running": False,
            "database_status": "Unknown",
            "active_jobs": 0,
            "paused_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "total_jobs": 0,
            "uptime": "N/A",
            "last_poll_time": None,
        }
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
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help="Enable auto-reload on code changes (development mode)",
    ),
):
    """
    Start the TeckoChecker polling service.

    This starts the FastAPI server and begins polling jobs.
    The polling service starts automatically with the API server.
    """
    print_banner()
    print_info("Starting TeckoChecker...")

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
            print_info("Polling service is running in the background")
        else:
            # Run in foreground
            import uvicorn

            print_info(f"Starting TeckoChecker on port {port} (press Ctrl+C to stop)...")
            print_info("API Server: http://127.0.0.1:{}/docs".format(port))
            print_info("Polling service will start automatically...")
            uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info", reload=reload)

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
# DOCTOR COMMAND
# =============================================================================


def doctor():
    """
    Run diagnostic checks on TeckoChecker setup.

    Verifies environment configuration, database connection, dependencies,
    encryption setup, and API connectivity. Does NOT require API server running.
    """
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    print_banner()
    console.print("\n[bold cyan]Running TeckoChecker diagnostics...[/bold cyan]\n")

    results = {}
    all_passed = True

    # Check 1: Dependencies
    console.print("[bold]1. Checking Dependencies[/bold]")
    dependencies_passed = True
    required_packages = [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("cryptography", "Cryptography"),
        ("typer", "Typer"),
        ("rich", "Rich"),
        ("httpx", "HTTPX"),
        ("openai", "OpenAI"),
    ]

    for package, name in required_packages:
        try:
            __import__(package)
            console.print(f"   [green]:heavy_check_mark:[/green] {name}")
        except ImportError:
            console.print(f"   [red]:x:[/red] {name} (not installed)")
            dependencies_passed = False

    if not dependencies_passed:
        console.print(
            "   [yellow]Install missing packages with: pip install -r requirements.txt[/yellow]"
        )

    results["Dependencies"] = dependencies_passed
    all_passed = all_passed and dependencies_passed
    console.print()

    # Check 2: Environment Configuration
    console.print("[bold]2. Checking Environment Configuration[/bold]")
    env_passed = True

    env_path = Path(__file__).parent.parent.parent / ".env"
    env_example_path = Path(__file__).parent.parent.parent / ".env.example"

    if not env_example_path.exists():
        console.print("   [red]:x:[/red] .env.example file not found")
        env_passed = False
    else:
        console.print("   [green]:heavy_check_mark:[/green] .env.example exists")

    if not env_path.exists():
        console.print("   [red]:x:[/red] .env file not found")
        console.print("   [yellow]Run: cp .env.example .env[/yellow]")
        console.print("   [yellow]Or use: python teckochecker.py setup[/yellow]")
        env_passed = False
    else:
        console.print("   [green]:heavy_check_mark:[/green] .env file exists")

        # Try to load settings
        try:
            from app.config import get_settings

            settings = get_settings()
            console.print("   [green]:heavy_check_mark:[/green] Configuration loaded successfully")
            console.print(f"   [dim]Database URL: {settings.database_url}[/dim]")
            console.print(f"   [dim]Log Level: {settings.log_level}[/dim]")
            console.print(f"   [dim]API Port: {settings.api_port}[/dim]")

            # Check if SECRET_KEY is properly set
            if "change-this" in settings.secret_key.lower():
                console.print(
                    "   [yellow]:warning:[/yellow] SECRET_KEY is still set to default value"
                )
                console.print("   [yellow]Generate a new key and update .env file[/yellow]")
                env_passed = False
            else:
                console.print("   [green]:heavy_check_mark:[/green] SECRET_KEY is configured")

        except Exception as e:
            console.print(f"   [red]:x:[/red] Failed to load configuration: {e}")
            env_passed = False

    results["Environment"] = env_passed
    all_passed = all_passed and env_passed
    console.print()

    # Check 3: Encryption
    console.print("[bold]3. Testing Encryption[/bold]")
    encryption_passed = True
    try:
        from cryptography.fernet import Fernet

        # Generate a test key
        key = Fernet.generate_key()
        console.print("   [green]:heavy_check_mark:[/green] Generated test encryption key")

        # Test encryption
        f = Fernet(key)
        test_data = b"test secret value"
        encrypted = f.encrypt(test_data)
        console.print("   [green]:heavy_check_mark:[/green] Encryption successful")

        # Test decryption
        decrypted = f.decrypt(encrypted)
        console.print("   [green]:heavy_check_mark:[/green] Decryption successful")

        # Verify
        if decrypted == test_data:
            console.print("   [green]:heavy_check_mark:[/green] Data integrity verified")
        else:
            console.print("   [red]:x:[/red] Decrypted data does not match")
            encryption_passed = False

    except Exception as e:
        console.print(f"   [red]:x:[/red] Encryption test failed: {e}")
        encryption_passed = False

    results["Encryption"] = encryption_passed
    all_passed = all_passed and encryption_passed
    console.print()

    # Check 4: Models
    console.print("[bold]4. Checking Models[/bold]")
    models_passed = True
    try:
        from app.models import SECRET_TYPES, JOB_STATUSES, LOG_STATUSES

        console.print("   [green]:heavy_check_mark:[/green] Secret model imported")
        console.print("   [green]:heavy_check_mark:[/green] PollingJob model imported")
        console.print("   [green]:heavy_check_mark:[/green] PollingLog model imported")
        console.print(f"   [dim]Valid secret types: {', '.join(SECRET_TYPES)}[/dim]")
        console.print(f"   [dim]Valid job statuses: {', '.join(JOB_STATUSES)}[/dim]")
        console.print(f"   [dim]Valid log statuses: {', '.join(LOG_STATUSES)}[/dim]")

    except Exception as e:
        console.print(f"   [red]:x:[/red] Model import failed: {e}")
        models_passed = False

    results["Models"] = models_passed
    all_passed = all_passed and models_passed
    console.print()

    # Check 5: Database
    console.print("[bold]5. Checking Database[/bold]")
    database_passed = True
    try:
        from app.database import get_db_manager
        from app.config import get_settings

        settings = get_settings()
        db_manager = get_db_manager()

        # Check connection
        if not db_manager.check_connection():
            console.print("   [red]:x:[/red] Cannot connect to database")
            database_passed = False
        else:
            console.print("   [green]:heavy_check_mark:[/green] Database connection successful")

            # Check if tables exist
            tables = db_manager.get_table_names()
            console.print(
                f"   [green]:heavy_check_mark:[/green] Found {len(tables)} tables in database"
            )

            expected_tables = ["secrets", "polling_jobs", "polling_logs"]
            for table in expected_tables:
                if table in tables:
                    console.print(f"   [green]:heavy_check_mark:[/green] {table}")
                else:
                    console.print(f"   [red]:x:[/red] {table} (missing)")
                    database_passed = False

            if len(tables) == 0:
                console.print("   [yellow]:warning:[/yellow] No tables found")
                console.print("   [yellow]Run: python teckochecker.py init[/yellow]")
                database_passed = False

    except Exception as e:
        console.print(f"   [red]:x:[/red] Database check failed: {e}")
        database_passed = False

    results["Database"] = database_passed
    all_passed = all_passed and database_passed
    console.print()

    # Check 6: API Connectivity (optional - doesn't affect overall result)
    console.print("[bold]6. Checking API Connectivity[/bold]")
    api_running = False
    try:
        client = get_api_client()
        health_response = client.get("/health")
        health_response.raise_for_status()
        health_data = health_response.json()

        console.print("   [green]:heavy_check_mark:[/green] API server is running")
        console.print(f"   [dim]Status: {health_data.get('status', 'unknown')}[/dim]")
        console.print(f"   [dim]Database: {health_data.get('database', 'unknown')}[/dim]")
        api_running = True

    except httpx.ConnectError:
        console.print("   [yellow]:warning:[/yellow] API server is not running")
        console.print("   [dim]This is optional - start with: python teckochecker.py start[/dim]")
    except Exception as e:
        console.print(f"   [yellow]:warning:[/yellow] Could not connect to API: {e}")

    console.print()

    # Summary
    console.print("[bold cyan]Summary[/bold cyan]")

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")

    for check, passed in results.items():
        status = "[green]:heavy_check_mark: PASS[/green]" if passed else "[red]:x: FAIL[/red]"
        table.add_row(check, status)

    # API check is informational only
    api_status = (
        "[green]:heavy_check_mark: RUNNING[/green]"
        if api_running
        else "[yellow]:warning: STOPPED[/yellow]"
    )
    table.add_row("API Server", api_status)

    console.print(table)
    console.print()

    if all_passed:
        success_msg = """
[bold green]All checks passed! Setup is complete.[/bold green]

[bold]Next steps:[/bold]
  1. Start the API: [cyan]python teckochecker.py start --reload[/cyan]
     (Note: polling service starts automatically)
  2. Add secrets: [cyan]teckochecker secret add ...[/cyan]
  3. Create jobs: [cyan]teckochecker job create ...[/cyan]
"""
        console.print(Panel(success_msg.strip(), border_style="green", title="Success"))
        sys.exit(0)
    else:
        error_msg = """
[bold red]Some checks failed. Please fix the issues above.[/bold red]

Run [cyan]python teckochecker.py setup[/cyan] for interactive setup,
or [cyan]python teckochecker.py init --generate-env[/cyan] for automatic setup.
"""
        console.print(Panel(error_msg.strip(), border_style="red", title="Failed"))
        sys.exit(1)


# =============================================================================
# DB SCHEMA COMMAND
# =============================================================================

# Create sub-app for db commands
db_app = typer.Typer(help="Database management commands")


@db_app.command("schema")
def db_schema():
    """
    Show database schema in readable format.

    Displays table structures, columns, relationships, and indexes.
    Does NOT require API server running.
    """
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    from sqlalchemy import inspect

    try:
        from app.models import Secret, PollingJob, PollingLog
        from app.models import SECRET_TYPES, JOB_STATUSES, LOG_STATUSES

        print_banner()
        console.print("\n[bold cyan]TeckoChecker Database Schema[/bold cyan]\n")

        models = [
            (Secret, "Stores encrypted API keys and tokens"),
            (PollingJob, "Defines polling jobs for OpenAI batches"),
            (PollingLog, "Records polling activity and status changes"),
        ]

        for model, description in models:
            inspector = inspect(model)
            table_name = model.__tablename__

            # Create table header
            console.print(f"\n[bold yellow]Table: {table_name}[/bold yellow]")
            console.print(f"[dim]{description}[/dim]\n")

            # Create columns table
            columns_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
            columns_table.add_column("Column Name", style="cyan", no_wrap=True)
            columns_table.add_column("Type", style="green")
            columns_table.add_column("Nullable", justify="center")
            columns_table.add_column("Default", style="dim")

            for column in inspector.columns:
                col_name = column.name
                col_type = str(column.type)
                nullable = "[green]Yes[/green]" if column.nullable else "[red]No[/red]"
                default = str(column.default.arg) if column.default else "-"

                columns_table.add_row(col_name, col_type, nullable, default)

            console.print(columns_table)

            # Show relationships if any
            if inspector.relationships:
                console.print("\n[bold]Relationships:[/bold]")
                for rel in inspector.relationships:
                    console.print(
                        f"  [cyan]{rel.key}[/cyan] -> [green]{rel.mapper.class_.__name__}[/green]"
                    )

        # Show SQL schema
        console.print("\n[bold cyan]SQL Schema (SQLite)[/bold cyan]\n")

        sql_schema = """[dim]CREATE TABLE secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE polling_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    openai_secret_id INTEGER,
    keboola_secret_id INTEGER,
    keboola_stack_url TEXT NOT NULL,
    keboola_component_id TEXT NOT NULL,
    keboola_configuration_id TEXT NOT NULL,
    poll_interval_seconds INTEGER DEFAULT 120,
    status TEXT DEFAULT 'active',
    last_check_at TIMESTAMP,
    next_check_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (openai_secret_id) REFERENCES secrets(id) ON DELETE SET NULL,
    FOREIGN KEY (keboola_secret_id) REFERENCES secrets(id) ON DELETE SET NULL
);

CREATE TABLE polling_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES polling_jobs(id) ON DELETE CASCADE
);[/dim]"""

        console.print(Panel(sql_schema, border_style="cyan", title="Table Definitions"))

        # Show indexes
        console.print("\n[bold cyan]Indexes[/bold cyan]\n")

        indexes_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        indexes_table.add_column("Index Name", style="cyan")
        indexes_table.add_column("Table", style="yellow")
        indexes_table.add_column("Columns", style="green")

        indexes = [
            ("idx_secrets_name", "secrets", "name"),
            ("idx_polling_jobs_batch_id", "polling_jobs", "batch_id"),
            ("idx_polling_jobs_status", "polling_jobs", "status"),
            ("idx_polling_jobs_next_check", "polling_jobs", "next_check_at"),
            ("idx_polling_jobs_status_next_check", "polling_jobs", "status, next_check_at"),
            ("idx_polling_logs_job_id", "polling_logs", "job_id"),
            ("idx_polling_logs_created_at", "polling_logs", "created_at"),
            ("idx_polling_logs_job_created", "polling_logs", "job_id, created_at"),
            ("idx_polling_logs_status", "polling_logs", "status"),
        ]

        for idx_name, table, columns in indexes:
            indexes_table.add_row(idx_name, table, columns)

        console.print(indexes_table)

        # Show valid values
        console.print("\n[bold cyan]Valid Values[/bold cyan]\n")

        # Secret types
        console.print("[bold]Secret Types:[/bold]")
        for stype in SECRET_TYPES:
            console.print(f"  [green]{stype}[/green]")

        # Job statuses
        console.print("\n[bold]Job Statuses:[/bold]")
        status_descriptions = {
            "active": "Job is actively being polled",
            "paused": "Job is temporarily paused",
            "completed": "Job has completed successfully",
            "failed": "Job has failed",
        }
        for status in JOB_STATUSES:
            desc = status_descriptions.get(status, "")
            console.print(f"  [green]{status}[/green] - [dim]{desc}[/dim]")

        # Log statuses
        console.print("\n[bold]Log Statuses:[/bold]")
        log_descriptions = {
            "checking": "Currently checking status",
            "pending": "OpenAI batch is still pending",
            "completed": "OpenAI batch completed",
            "failed": "Check or batch failed",
            "error": "Error during polling",
            "triggered": "Keboola job was triggered",
        }
        for status in LOG_STATUSES:
            desc = log_descriptions.get(status, "")
            console.print(f"  [green]{status}[/green] - [dim]{desc}[/dim]")

        console.print()

    except Exception as e:
        print_error(f"Failed to display schema: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
