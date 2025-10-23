#!/usr/bin/env python3
"""
TeckoChecker Demo - Keboola Custom Python Script

This script demonstrates how to receive and process batch completion metadata
from TeckoChecker polling service.

When TeckoChecker completes monitoring OpenAI batch jobs, it triggers this
Keboola configuration with batch completion details.

Parameters received from TeckoChecker:
- batch_ids_completed: List of successfully completed batch IDs
- batch_ids_failed: List of failed/cancelled/expired batch IDs
- batch_count_total: Total number of batches monitored
- batch_count_completed: Count of successfully completed batches
- batch_count_failed: Count of failed batches
"""

import logging
from typing import List, Dict, Any
from keboola.component import CommonInterface


def log_batch_metadata(parameters: Dict[str, Any]) -> None:
    """
    Log batch completion metadata received from TeckoChecker.

    Args:
        parameters: Dictionary containing batch metadata
    """
    # Extract parameters with defaults
    batch_ids_completed = parameters.get("batch_ids_completed", [])
    batch_ids_failed = parameters.get("batch_ids_failed", [])
    batch_count_total = parameters.get("batch_count_total", 0)
    batch_count_completed = parameters.get("batch_count_completed", 0)
    batch_count_failed = parameters.get("batch_count_failed", 0)

    # Log summary
    logging.info("=" * 80)
    logging.info("TeckoChecker Batch Completion Summary")
    logging.info("=" * 80)

    logging.info(f"Total Batches: {batch_count_total}")
    logging.info(f"Completed: {batch_count_completed}")
    logging.info(f"Failed: {batch_count_failed}")

    # Log completed batch IDs
    if batch_ids_completed:
        logging.info("")
        logging.info("Completed Batch IDs:")
        for i, batch_id in enumerate(batch_ids_completed, 1):
            logging.info(f"  {i}. {batch_id}")
    else:
        logging.info("")
        logging.info("No completed batches")

    # Log failed batch IDs
    if batch_ids_failed:
        logging.warning("")
        logging.warning("Failed Batch IDs:")
        for i, batch_id in enumerate(batch_ids_failed, 1):
            logging.warning(f"  {i}. {batch_id}")
    else:
        logging.info("")
        logging.info("No failed batches")

    logging.info("=" * 80)

    # Determine overall status
    if batch_count_failed == 0:
        logging.info("✓ All batches completed successfully!")
    elif batch_count_completed > 0:
        logging.warning(
            f"⚠ Partial success: {batch_count_completed}/{batch_count_total} batches completed"
        )
    else:
        logging.error(f"✗ All batches failed ({batch_count_failed}/{batch_count_total})")


def process_batch_results(batch_ids_completed: List[str], batch_ids_failed: List[str]) -> None:
    """
    Process batch results (placeholder for custom logic).

    This is where you would add your custom processing logic, such as:
    - Downloading results from completed batches
    - Sending notifications
    - Updating downstream systems
    - Triggering additional workflows

    Args:
        batch_ids_completed: List of successfully completed batch IDs
        batch_ids_failed: List of failed batch IDs
    """
    logging.info("")
    logging.info("Processing batch results...")

    # Example: Process completed batches
    if batch_ids_completed:
        logging.info(f"Processing {len(batch_ids_completed)} completed batches...")
        for batch_id in batch_ids_completed:
            logging.info(f"  - Would download/process results from: {batch_id}")
            # Add your custom logic here
            # Example: download_batch_results(batch_id)
            # Example: process_batch_output(batch_id)

    # Example: Handle failed batches
    if batch_ids_failed:
        logging.warning(f"Handling {len(batch_ids_failed)} failed batches...")
        for batch_id in batch_ids_failed:
            logging.warning(f"  - Would handle failure for: {batch_id}")
            # Add your error handling logic here
            # Example: send_failure_notification(batch_id)
            # Example: retry_batch(batch_id)

    logging.info("Processing complete!")


def main():
    """
    Main entry point for Keboola Custom Python component.
    """
    # Initialize Keboola Common Interface
    ci = CommonInterface()

    # Get parameters from configuration
    parameters = ci.configuration.parameters

    logging.info("TeckoChecker Demo Script Started")
    logging.info(f"Received parameters: {list(parameters.keys())}")

    # Log batch metadata
    log_batch_metadata(parameters)

    # Process batch results (placeholder for custom logic)
    batch_ids_completed = parameters.get("batch_ids_completed", [])
    batch_ids_failed = parameters.get("batch_ids_failed", [])
    process_batch_results(batch_ids_completed, batch_ids_failed)

    logging.info("")
    logging.info("TeckoChecker Demo Script Completed Successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(f"Error in TeckoChecker demo script: {e}")
        raise
