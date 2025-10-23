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

import json
import logging
import os
import sys
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

    # Use logging.info for visibility (CommonInterface sets up rich logging)
    logging.info("")
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
        logging.warning(f"⚠ Partial success: {batch_count_completed}/{batch_count_total} batches completed")
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
    # Initialize Keboola Common Interface FIRST (required for logging to work properly)
    ci = CommonInterface()

    logging.warning("=" * 80)
    logging.warning("🚀 TeckoChecker Demo Script Started")
    logging.warning("=" * 80)
    logging.warning("")

    # 1. Try to read config.json directly from disk
    config_path = "/data/config.json"
    logging.warning(f"📁 Reading config from: {config_path}")

    if os.path.exists(config_path):
        logging.warning("✓ Config file exists")
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            logging.warning("")
            logging.warning("📄 RAW CONFIG.JSON CONTENT:")
            logging.warning(json.dumps(config_data, indent=2))
            logging.warning("")

            # Extract parameters from config
            config_parameters = config_data.get("parameters", {})
            logging.warning(f"✓ Found {len(config_parameters)} parameters in config.json")

        except Exception as e:
            logging.error(f"❌ Error reading config.json: {e}")
    else:
        logging.error(f"❌ Config file not found at: {config_path}")

    # 2. Get parameters from CommonInterface
    logging.warning("")
    logging.warning("📦 PARAMETERS FROM COMMONINTERFACE:")
    parameters = ci.configuration.parameters

    if not parameters:
        logging.error("❌ ERROR: No parameters from CommonInterface!")
    else:
        logging.warning(f"✓ Received {len(parameters)} parameters")
        logging.warning("")

        for key, value in parameters.items():
            if isinstance(value, list):
                logging.warning(f"  • {key}: [{len(value)} items]")
                for i, item in enumerate(value, 1):
                    logging.warning(f"      {i}. {item}")
            else:
                logging.warning(f"  • {key}: {value}")

    logging.warning("")
    logging.warning("=" * 80)

    # Log batch metadata
    log_batch_metadata(parameters)

    # Process batch results (placeholder for custom logic)
    batch_ids_completed = parameters.get("batch_ids_completed", [])
    batch_ids_failed = parameters.get("batch_ids_failed", [])
    process_batch_results(batch_ids_completed, batch_ids_failed)

    logging.info("")
    logging.info("=" * 80)
    logging.info("✓ TeckoChecker Demo Script Completed Successfully")
    logging.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"❌ ERROR in TeckoChecker demo script: {type(e).__name__}: {str(e)}")
        logging.exception(e, extra={"context": "main_execution"})
        raise
