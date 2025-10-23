#!/usr/bin/env python3
"""
Test script for triggering Keboola jobs directly.

This script simulates what TeckoChecker does when it triggers a Keboola job
after batch completion. Useful for testing the Keboola Custom Python handler
without waiting for actual batch completion.

Usage:
    # Using Keboola token from environment
    export KEBOOLA_TOKEN="your-token-here"
    python scripts/test_trigger_keboola.py

    # Using token from TeckoChecker secret
    python scripts/test_trigger_keboola.py --from-teckochecker --secret-id 1

    # Custom configuration
    python scripts/test_trigger_keboola.py --token YOUR_TOKEN --config my-config-id

    # Multi-batch test
    python scripts/test_trigger_keboola.py --multi-batch

    # Simulate partial failure
    python scripts/test_trigger_keboola.py --with-failures
"""

import argparse
import json
import os
import sys
from typing import List, Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()

# Default configuration
DEFAULT_KEBOOLA_API_URL = "https://queue.eu-central-1.keboola.com/jobs"
DEFAULT_CONFIG_ID = "01k88kpabsjpv5qqxcn0dg69pm"
DEFAULT_COMPONENT = "kds-team.app-custom-python"
DEFAULT_TECKOCHECKER_API_URL = "http://localhost:8000"


def get_keboola_token_from_teckochecker(
    api_url: str, secret_id: int
) -> tuple[str, str, Optional[str]]:
    """
    Retrieve Keboola token and config from TeckoChecker secret.

    Args:
        api_url: TeckoChecker API URL
        secret_id: Secret ID to retrieve

    Returns:
        Tuple of (token, config_id, branch_id)
    """
    console.print(f"\n[cyan]Fetching secret {secret_id} from TeckoChecker...[/cyan]")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/api/admin/secrets/{secret_id}")
            response.raise_for_status()
            secret = response.json()

            if secret.get("type") != "keboola":
                console.print(
                    f"[bold red]Error:[/bold red] Secret {secret_id} is not a Keboola secret (type: {secret.get('type')})",
                    style="red",
                )
                sys.exit(1)

            # Get decrypted values
            token = secret.get("value")
            metadata = secret.get("metadata", {})
            config_id = metadata.get("config_id")
            branch_id = metadata.get("branch_id")

            if not token:
                console.print(
                    "[bold red]Error:[/bold red] Secret has no token value", style="red"
                )
                sys.exit(1)

            console.print(f"[green]✓ Retrieved Keboola secret[/green]")
            console.print(f"  Config ID: {config_id or 'not set'}")
            console.print(f"  Branch ID: {branch_id or 'not set'}")

            return token, config_id, branch_id

    except httpx.ConnectError:
        console.print(
            f"\n[bold red]Error:[/bold red] Cannot connect to TeckoChecker at {api_url}",
            style="red",
        )
        console.print("Make sure TeckoChecker is running:")
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


def trigger_keboola_job(
    api_url: str,
    token: str,
    component: str,
    config_id: str,
    batch_ids_completed: List[str],
    batch_ids_failed: List[str],
    branch_id: Optional[str] = None,
) -> dict:
    """
    Trigger a Keboola job with batch completion parameters.

    Args:
        api_url: Keboola Queue API URL
        token: Keboola Storage API token
        component: Keboola component ID
        config_id: Configuration ID
        batch_ids_completed: List of completed batch IDs
        batch_ids_failed: List of failed batch IDs
        branch_id: Optional branch ID

    Returns:
        Response data from Keboola API
    """
    # Calculate counts
    batch_count_total = len(batch_ids_completed) + len(batch_ids_failed)
    batch_count_completed = len(batch_ids_completed)
    batch_count_failed = len(batch_ids_failed)

    # Build payload with jobParams structure
    payload = {
        "mode": "run",
        "component": component,
        "config": config_id,
        "configData": {
            "parameters": {
                "jobParams": {
                    "batch_ids_completed": batch_ids_completed,
                    "batch_ids_failed": batch_ids_failed,
                    "batch_count_total": batch_count_total,
                    "batch_count_completed": batch_count_completed,
                    "batch_count_failed": batch_count_failed,
                }
            }
        },
    }

    if branch_id:
        payload["branchId"] = branch_id

    headers = {"X-StorageApi-Token": token}

    console.print("\n[bold cyan]Triggering Keboola Job...[/bold cyan]")
    console.print(f"API URL: {api_url}")
    console.print(f"Component: {component}")
    console.print(f"Config ID: {config_id}")
    if branch_id:
        console.print(f"Branch ID: {branch_id}")

    # Show payload (with masked token)
    console.print("\n[bold]Request Payload:[/bold]")
    syntax = Syntax(json.dumps(payload, indent=2), "json", theme="monokai")
    console.print(syntax)

    console.print("\n[bold]Headers:[/bold]")
    console.print(f"X-StorageApi-Token: {'*' * 20}...{token[-4:]}")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        console.print(f"\n[bold red]Error {e.response.status_code}:[/bold red]")
        try:
            error_data = e.response.json()
            console.print(json.dumps(error_data, indent=2))
        except Exception:
            console.print(e.response.text)
        sys.exit(1)


def display_result(result: dict) -> None:
    """Display the Keboola job trigger result."""
    console.print("\n[bold green]✓ Keboola Job Triggered Successfully![/bold green]\n")

    table = Table(title="Keboola Job Details", show_header=True)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Job ID", str(result.get("id", "N/A")))
    table.add_row("Status", result.get("status", "N/A"))
    table.add_row("URL", result.get("url", "N/A"))
    table.add_row("Run ID", str(result.get("runId", "N/A")))

    console.print(table)

    # Full response
    console.print("\n[bold]Full Response:[/bold]")
    syntax = Syntax(json.dumps(result, indent=2), "json", theme="monokai")
    console.print(syntax)

    # Next steps
    if result.get("url"):
        console.print("\n[bold]Monitor Job:[/bold]")
        console.print(f"  • Job URL: {result['url']}")


def main():
    parser = argparse.ArgumentParser(
        description="Test script for triggering Keboola jobs directly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use token from environment variable
  export KEBOOLA_TOKEN="your-token"
  python scripts/test_trigger_keboola.py

  # Get token from TeckoChecker secret
  python scripts/test_trigger_keboola.py --from-teckochecker --secret-id 1

  # Multi-batch test
  python scripts/test_trigger_keboola.py --multi-batch

  # Simulate partial failure (2 completed, 1 failed)
  python scripts/test_trigger_keboola.py --with-failures

  # Custom batch IDs
  python scripts/test_trigger_keboola.py --completed batch_001 batch_002 --failed batch_003

  # Custom config
  python scripts/test_trigger_keboola.py --config my-config-id --branch my-branch-id
        """,
    )

    parser.add_argument(
        "--keboola-api-url",
        default=DEFAULT_KEBOOLA_API_URL,
        help=f"Keboola Queue API URL (default: {DEFAULT_KEBOOLA_API_URL})",
    )

    parser.add_argument(
        "--token",
        help="Keboola Storage API token (or use KEBOOLA_TOKEN env var)",
    )

    parser.add_argument(
        "--from-teckochecker",
        action="store_true",
        help="Get token and config from TeckoChecker secret",
    )

    parser.add_argument(
        "--teckochecker-api-url",
        default=DEFAULT_TECKOCHECKER_API_URL,
        help=f"TeckoChecker API URL (default: {DEFAULT_TECKOCHECKER_API_URL})",
    )

    parser.add_argument(
        "--secret-id",
        type=int,
        default=1,
        help="TeckoChecker secret ID to use (with --from-teckochecker, default: 1)",
    )

    parser.add_argument(
        "--component",
        default=DEFAULT_COMPONENT,
        help=f"Keboola component ID (default: {DEFAULT_COMPONENT})",
    )

    parser.add_argument(
        "--config",
        help="Keboola configuration ID",
    )

    parser.add_argument(
        "--branch",
        help="Keboola branch ID (optional)",
    )

    parser.add_argument(
        "--completed",
        nargs="+",
        help="Completed batch IDs (space-separated)",
    )

    parser.add_argument(
        "--failed",
        nargs="+",
        default=[],
        help="Failed batch IDs (space-separated)",
    )

    parser.add_argument(
        "--multi-batch",
        action="store_true",
        help="Test with 3 completed batches",
    )

    parser.add_argument(
        "--with-failures",
        action="store_true",
        help="Test with 2 completed and 1 failed batch",
    )

    args = parser.parse_args()

    # Show banner
    console.print(
        Panel.fit(
            "[bold cyan]Keboola Job Trigger Test[/bold cyan]\n"
            "Simulate TeckoChecker triggering Keboola jobs",
            border_style="cyan",
        )
    )

    # Get token and config
    if args.from_teckochecker:
        token, config_from_secret, branch_from_secret = get_keboola_token_from_teckochecker(
            args.teckochecker_api_url, args.secret_id
        )
        config_id = args.config or config_from_secret or DEFAULT_CONFIG_ID
        branch_id = args.branch or branch_from_secret
    else:
        token = args.token or os.getenv("KEBOOLA_TOKEN")
        if not token:
            console.print(
                "[bold red]Error:[/bold red] No Keboola token provided", style="red"
            )
            console.print("Either set KEBOOLA_TOKEN env var, use --token, or --from-teckochecker")
            sys.exit(1)

        config_id = args.config or DEFAULT_CONFIG_ID
        branch_id = args.branch

    # Determine batch IDs
    if args.completed:
        batch_ids_completed = args.completed
        batch_ids_failed = args.failed or []
    elif args.multi_batch:
        batch_ids_completed = [
            "batch_test_001",
            "batch_test_002",
            "batch_test_003",
        ]
        batch_ids_failed = []
    elif args.with_failures:
        batch_ids_completed = [
            "batch_test_001",
            "batch_test_002",
        ]
        batch_ids_failed = ["batch_test_003"]
    else:
        # Default: single completed batch
        batch_ids_completed = ["batch_68fa3dc29b6c8190961deca91c6a7f0e"]
        batch_ids_failed = []

    # Show summary
    console.print(f"\n[bold]Test Configuration:[/bold]")
    console.print(f"  Completed batches: {len(batch_ids_completed)}")
    console.print(f"  Failed batches: {len(batch_ids_failed)}")
    console.print(f"  Total batches: {len(batch_ids_completed) + len(batch_ids_failed)}")

    # Trigger the job
    result = trigger_keboola_job(
        api_url=args.keboola_api_url,
        token=token,
        component=args.component,
        config_id=config_id,
        batch_ids_completed=batch_ids_completed,
        batch_ids_failed=batch_ids_failed,
        branch_id=branch_id,
    )

    # Display result
    display_result(result)


if __name__ == "__main__":
    main()
