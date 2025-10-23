#!/usr/bin/env python3
"""
Test script for creating TeckoChecker polling jobs.

This script makes it easy to test job creation with various configurations
without needing to use curl or Postman.

Usage:
    # Single batch job
    python scripts/test_create_job.py

    # Multi-batch job
    python scripts/test_create_job.py --multi-batch

    # Custom configuration
    python scripts/test_create_job.py --batch-ids batch_123 batch_456 --interval 30

    # With specific secrets
    python scripts/test_create_job.py --openai-secret my_openai --keboola-secret my_keboola
"""

import argparse
import json
import sys
from typing import List, Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()

# Default configuration
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_BATCH_IDS = ["batch_test_001"]
DEFAULT_POLL_INTERVAL = 60
DEFAULT_KEBOOLA_CONFIG_ID = "12345"
DEFAULT_KEBOOLA_BRANCH_ID = "67890"


def create_polling_job(
    api_url: str,
    batch_ids: List[str],
    openai_secret_id: int,
    keboola_secret_id: int,
    poll_interval: int,
    keboola_config_id: str,
    keboola_branch_id: Optional[str] = None,
) -> dict:
    """
    Create a polling job via the TeckoChecker API.

    Args:
        api_url: Base URL of TeckoChecker API
        batch_ids: List of OpenAI batch IDs to monitor (1-10 batches)
        openai_secret_id: ID of OpenAI secret
        keboola_secret_id: ID of Keboola secret
        poll_interval: Polling interval in seconds
        keboola_config_id: Keboola configuration ID
        keboola_branch_id: Optional Keboola branch ID

    Returns:
        Response data from API
    """
    payload = {
        "batch_ids": batch_ids,
        "openai_secret_id": openai_secret_id,
        "keboola_secret_id": keboola_secret_id,
        "poll_interval": poll_interval,
        "keboola_config_id": keboola_config_id,
    }

    if keboola_branch_id:
        payload["keboola_branch_id"] = keboola_branch_id

    console.print("\n[bold cyan]Creating Polling Job...[/bold cyan]")
    console.print(f"API URL: {api_url}/api/jobs")
    console.print(f"Batch IDs: {', '.join(batch_ids)}")
    console.print(f"Batch count: {len(batch_ids)}")
    console.print(f"Poll interval: {poll_interval}s")

    # Show request payload
    console.print("\n[bold]Request Payload:[/bold]")
    syntax = Syntax(json.dumps(payload, indent=2), "json", theme="monokai")
    console.print(syntax)

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{api_url}/api/jobs", json=payload)
            response.raise_for_status()
            return response.json()

    except httpx.ConnectError:
        console.print(
            f"\n[bold red]Error:[/bold red] Cannot connect to API at {api_url}",
            style="red",
        )
        console.print("Make sure the TeckoChecker API is running:")
        console.print("  - Local: python teckochecker.py start")
        console.print("  - Docker: make docker-compose-up")
        sys.exit(1)

    except httpx.HTTPStatusError as e:
        console.print(f"\n[bold red]Error {e.response.status_code}:[/bold red]")
        try:
            error_data = e.response.json()
            console.print(json.dumps(error_data, indent=2))
        except Exception:
            console.print(e.response.text)
        sys.exit(1)


def display_result(job_data: dict) -> None:
    """Display the created job in a nice format."""
    console.print("\n[bold green]✓ Job Created Successfully![/bold green]\n")

    # Main job info table
    table = Table(title="Polling Job Details", show_header=True)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Job ID", str(job_data.get("id")))
    table.add_row("Status", job_data.get("status", "unknown"))
    table.add_row("Created At", job_data.get("created_at", ""))
    table.add_row("Poll Interval", f"{job_data.get('poll_interval')}s")

    # Batch information
    batches = job_data.get("batches", [])
    batch_ids = [b.get("batch_id") for b in batches]
    table.add_row("Batch Count", str(len(batches)))
    table.add_row("Batch IDs", "\n".join(batch_ids) if batch_ids else "N/A")

    # Completion counts
    table.add_row("Completed", str(job_data.get("completed_count", 0)))
    table.add_row("Failed", str(job_data.get("failed_count", 0)))

    # Keboola config
    table.add_row("Keboola Config ID", job_data.get("keboola_config_id", ""))
    if job_data.get("keboola_branch_id"):
        table.add_row("Keboola Branch ID", job_data.get("keboola_branch_id"))

    console.print(table)

    # Next steps
    console.print("\n[bold]Next Steps:[/bold]")
    console.print(f"  • View job status: GET {DEFAULT_API_URL}/api/jobs/{job_data.get('id')}")
    console.print(f"  • View all jobs: GET {DEFAULT_API_URL}/api/jobs")
    console.print(f"  • View logs: GET {DEFAULT_API_URL}/api/jobs/{job_data.get('id')}/logs")
    console.print(f"  • Web UI: {DEFAULT_API_URL}/web")
    console.print(f"  • API Docs: {DEFAULT_API_URL}/docs")


def main():
    parser = argparse.ArgumentParser(
        description="Test script for creating TeckoChecker polling jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create single-batch job with defaults
  python scripts/test_create_job.py

  # Create multi-batch job
  python scripts/test_create_job.py --multi-batch

  # Custom batch IDs
  python scripts/test_create_job.py --batch-ids batch_abc123 batch_def456

  # Custom polling interval
  python scripts/test_create_job.py --interval 30

  # Full custom configuration
  python scripts/test_create_job.py \\
    --batch-ids batch_001 batch_002 batch_003 \\
    --interval 45 \\
    --openai-secret 1 \\
    --keboola-secret 2 \\
    --keboola-config "my-config-123" \\
    --keboola-branch "my-branch-456"
        """,
    )

    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"TeckoChecker API URL (default: {DEFAULT_API_URL})",
    )

    parser.add_argument(
        "--batch-ids",
        nargs="+",
        help="OpenAI batch IDs to monitor (space-separated, max 10)",
    )

    parser.add_argument(
        "--multi-batch",
        action="store_true",
        help="Create a multi-batch job with 3 test batch IDs",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL})",
    )

    parser.add_argument(
        "--openai-secret",
        type=int,
        default=1,
        help="OpenAI secret ID (default: 1)",
    )

    parser.add_argument(
        "--keboola-secret",
        type=int,
        default=1,
        help="Keboola secret ID (default: 1)",
    )

    parser.add_argument(
        "--keboola-config",
        default=DEFAULT_KEBOOLA_CONFIG_ID,
        help=f"Keboola configuration ID (default: {DEFAULT_KEBOOLA_CONFIG_ID})",
    )

    parser.add_argument(
        "--keboola-branch",
        help="Keboola branch ID (optional)",
    )

    args = parser.parse_args()

    # Determine batch IDs
    if args.batch_ids:
        batch_ids = args.batch_ids
    elif args.multi_batch:
        batch_ids = [
            "batch_test_001",
            "batch_test_002",
            "batch_test_003",
        ]
    else:
        batch_ids = DEFAULT_BATCH_IDS

    # Validate batch count
    if len(batch_ids) > 10:
        console.print("[bold red]Error:[/bold red] Maximum 10 batch IDs allowed", style="red")
        sys.exit(1)

    # Show banner
    console.print(
        Panel.fit(
            "[bold cyan]TeckoChecker Job Creation Test[/bold cyan]\n"
            "Create polling jobs for testing",
            border_style="cyan",
        )
    )

    # Create the job
    result = create_polling_job(
        api_url=args.api_url,
        batch_ids=batch_ids,
        openai_secret_id=args.openai_secret,
        keboola_secret_id=args.keboola_secret,
        poll_interval=args.interval,
        keboola_config_id=args.keboola_config,
        keboola_branch_id=args.keboola_branch,
    )

    # Display result
    display_result(result)


if __name__ == "__main__":
    main()
