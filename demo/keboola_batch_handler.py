#!/usr/bin/env python3
"""
TeckoChecker Demo - Keboola Custom Python Script

Receives batch completion metadata from TeckoChecker via Keboola variables.

TeckoChecker sends variableValuesData which Keboola maps to User Parameters.
Variables are then accessible directly via CommonInterface.configuration.parameters.
"""

import json
import logging
from typing import Any, Dict
from keboola.component import CommonInterface


def parse_variable(value: Any, var_type: str = "string") -> Any:
    """
    Parse variable value to correct type.

    Args:
        value: Raw variable value
        var_type: Expected type: "array", "int", or "string"

    Returns:
        Parsed value in the correct type
    """
    if value is None:
        return [] if var_type == "array" else (0 if var_type == "int" else "")

    if var_type == "array":
        if isinstance(value, list):
            return value
        # If it comes as JSON string, parse it
        if isinstance(value, str):
            try:
                return json.loads(value) if value else []
            except json.JSONDecodeError:
                logging.warning(f"Could not parse array variable: {value}")
                return []
        return []

    elif var_type == "int":
        if isinstance(value, int):
            return value
        # If it comes as string, convert it
        if isinstance(value, str):
            try:
                return int(value) if value else 0
            except (ValueError, TypeError):
                logging.warning(f"Could not parse int variable: {value}")
                return 0
        return 0

    return str(value) if value else ""


def log_batch_metadata(params: Dict[str, Any]) -> None:
    """
    Log batch completion metadata from TeckoChecker.

    Args:
        params: Dictionary containing batch metadata (directly in params, not nested)
    """
    # Keboola puts variables directly in params (not in user_properties sub-dict)
    # Parse variables directly from params
    batch_ids_completed = parse_variable(params.get("batch_ids_completed"), "array")
    batch_ids_failed = parse_variable(params.get("batch_ids_failed"), "array")
    batch_count_total = parse_variable(params.get("batch_count_total"), "int")
    batch_count_completed = parse_variable(params.get("batch_count_completed"), "int")
    batch_count_failed = parse_variable(params.get("batch_count_failed"), "int")

    logging.info("=" * 80)
    logging.info("TeckoChecker - Batch Completion")
    logging.info("=" * 80)

    # Log raw parameters (as received from Keboola)
    logging.info("\nRaw parameters:")
    for key, value in params.items():
        logging.info(f"  {key}: {value!r}")

    # Log parsed data
    logging.info("\nParsed data:")
    logging.info(f"  Total batches: {batch_count_total}")
    logging.info(f"  Completed: {batch_count_completed}")
    logging.info(f"  Failed: {batch_count_failed}")

    # Log batch IDs
    if batch_ids_completed:
        logging.info(f"\n  Completed batch IDs ({len(batch_ids_completed)}):")
        for batch_id in batch_ids_completed:
            logging.info(f"    - {batch_id}")

    if batch_ids_failed:
        logging.warning(f"\n  Failed batch IDs ({len(batch_ids_failed)}):")
        for batch_id in batch_ids_failed:
            logging.warning(f"    - {batch_id}")

    # Overall status
    logging.info("")
    if batch_count_failed == 0:
        logging.info("✓ All batches completed successfully!")
    elif batch_count_completed > 0:
        logging.warning(f"⚠ Partial success: {batch_count_completed}/{batch_count_total} completed")
    else:
        logging.error(f"✗ All batches failed ({batch_count_failed}/{batch_count_total})")

    logging.info("=" * 80)


def main():
    """Main entry point."""
    import os

    logging.info("=" * 80)
    logging.info("🚀 TeckoChecker - Batch Completion Handler")
    logging.info("=" * 80)

    # STEP 1: Read /data/config.json directly from disk
    logging.info("\n" + "=" * 80)
    logging.info("STEP 1: Reading /data/config.json from disk")
    logging.info("=" * 80)

    config_path = "/data/config.json"
    config_data = None

    if os.path.exists(config_path):
        logging.info(f"✓ File exists at: {config_path}")
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            logging.info("\n📄 RAW /data/config.json content:")
            logging.info("-" * 80)
            logging.info(json.dumps(config_data, indent=2))
            logging.info("-" * 80)

            # Show parameters specifically
            if "parameters" in config_data:
                logging.info("\n✓ Found 'parameters' in config.json:")
                logging.info(json.dumps(config_data["parameters"], indent=2))

                if "user_properties" in config_data.get("parameters", {}):
                    logging.info("\n✓ Found 'user_properties' in parameters:")
                    logging.info(json.dumps(config_data["parameters"]["user_properties"], indent=2))
                else:
                    logging.warning("\n⚠️ No 'user_properties' in parameters")
            else:
                logging.warning("\n⚠️ No 'parameters' key in config.json")

        except Exception as e:
            logging.error(f"❌ Failed to read config.json: {e}")
    else:
        logging.error(f"❌ Config file NOT found at: {config_path}")

    # STEP 2: Initialize CommonInterface and read parameters
    logging.info("\n" + "=" * 80)
    logging.info("STEP 2: Reading via CommonInterface")
    logging.info("=" * 80)

    ci = CommonInterface()
    params = ci.configuration.parameters

    logging.info("\n📦 CommonInterface.configuration.parameters:")
    logging.info(json.dumps(params, indent=2))

    if not params:
        logging.error("\n❌ No parameters from CommonInterface!")
        return

    # Keboola variables are mapped directly to params (not nested in user_properties)
    logging.info("\n✓ Parameters received from Keboola variables")

    # STEP 3: Parse and log batch metadata
    logging.info("\n" + "=" * 80)
    logging.info("STEP 3: Parsing batch metadata")
    logging.info("=" * 80)
    log_batch_metadata(params)

    # Add your custom processing logic here
    # Example: Download batch results, send notifications, etc.

    logging.info("\n✓ Script completed successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        raise
