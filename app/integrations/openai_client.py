"""
OpenAI Batch API client for TeckoChecker.

Provides integration with OpenAI's Batch API to check job statuses
with proper error handling, retries, and exponential backoff.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI, OpenAIError, APIError, RateLimitError, APIConnectionError

logger = logging.getLogger(__name__)


class OpenAIBatchClient:
    """
    Client for interacting with OpenAI Batch API.

    Handles status checking with automatic retries and exponential backoff.
    """

    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds
    MAX_RETRY_DELAY = 60  # seconds
    RETRY_MULTIPLIER = 2

    # Valid batch statuses from OpenAI API
    VALID_STATUSES = {
        'validating',
        'failed',
        'in_progress',
        'finalizing',
        'completed',
        'expired',
        'cancelling',
        'cancelled'
    }

    def __init__(self, api_key: str):
        """
        Initialize the OpenAI Batch client.

        Args:
            api_key: OpenAI API key for authentication
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self._api_key = api_key  # Store for logging purposes (redacted)

    async def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Check the status of an OpenAI batch job with automatic retries.

        Implements exponential backoff for retries on transient failures.

        Args:
            batch_id: The ID of the batch job to check

        Returns:
            Dictionary containing:
                - status: Current status of the batch
                - created_at: Timestamp when batch was created
                - completed_at: Timestamp when batch completed (if applicable)
                - failed_at: Timestamp when batch failed (if applicable)
                - error_message: Error message if batch failed
                - metadata: Additional metadata from the batch

        Raises:
            ValueError: If batch_id is invalid
            OpenAIError: If all retry attempts fail
        """
        if not batch_id or not isinstance(batch_id, str):
            raise ValueError(f"Invalid batch_id: {batch_id}")

        logger.info(f"Checking batch status for: {batch_id}")

        retry_delay = self.INITIAL_RETRY_DELAY
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Retrieve batch information from OpenAI
                batch = await self.client.batches.retrieve(batch_id)

                # Parse and validate the response
                result = self._parse_batch_response(batch)

                logger.info(
                    f"Batch {batch_id} status: {result['status']} "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )

                return result

            except RateLimitError as e:
                last_exception = e
                logger.warning(
                    f"Rate limit hit for batch {batch_id}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )

            except APIConnectionError as e:
                last_exception = e
                logger.warning(
                    f"Connection error for batch {batch_id}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )

            except APIError as e:
                # For 4xx errors (except 429), don't retry
                if hasattr(e, 'status_code') and 400 <= e.status_code < 500 and e.status_code != 429:
                    logger.error(f"Client error for batch {batch_id}: {e}")
                    raise

                last_exception = e
                logger.warning(
                    f"API error for batch {batch_id}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )

            except OpenAIError as e:
                last_exception = e
                logger.warning(
                    f"OpenAI error for batch {batch_id}, attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )

            # If this wasn't the last attempt, wait before retrying
            if attempt < self.MAX_RETRIES - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

                # Exponential backoff with cap
                retry_delay = min(retry_delay * self.RETRY_MULTIPLIER, self.MAX_RETRY_DELAY)

        # All retries exhausted
        logger.error(
            f"All {self.MAX_RETRIES} retry attempts failed for batch {batch_id}"
        )
        raise last_exception if last_exception else OpenAIError(
            "Failed to check batch status after all retries"
        )

    def _parse_batch_response(self, batch: Any) -> Dict[str, Any]:
        """
        Parse the batch response from OpenAI API.

        Args:
            batch: Batch object from OpenAI API

        Returns:
            Normalized dictionary with batch information

        Raises:
            ValueError: If response format is invalid
        """
        try:
            status = batch.status.lower() if hasattr(batch, 'status') else 'unknown'

            # Validate status
            if status not in self.VALID_STATUSES:
                logger.warning(f"Unknown batch status: {status}")

            result = {
                'status': status,
                'batch_id': batch.id if hasattr(batch, 'id') else None,
                'created_at': batch.created_at if hasattr(batch, 'created_at') else None,
                'completed_at': getattr(batch, 'completed_at', None),
                'failed_at': getattr(batch, 'failed_at', None),
                'expired_at': getattr(batch, 'expired_at', None),
                'cancelled_at': getattr(batch, 'cancelled_at', None),
                'error_message': None,
                'metadata': {},
            }

            # Extract error information if available
            if hasattr(batch, 'errors') and batch.errors:
                try:
                    # Errors could be a list or an object
                    if isinstance(batch.errors, list) and len(batch.errors) > 0:
                        result['error_message'] = str(batch.errors[0])
                    else:
                        result['error_message'] = str(batch.errors)
                except Exception as e:
                    logger.warning(f"Could not parse batch errors: {e}")

            # Extract metadata if available
            if hasattr(batch, 'metadata') and batch.metadata:
                try:
                    result['metadata'] = dict(batch.metadata)
                except Exception as e:
                    logger.warning(f"Could not parse batch metadata: {e}")

            # Add request counts if available
            if hasattr(batch, 'request_counts'):
                try:
                    result['request_counts'] = {
                        'total': getattr(batch.request_counts, 'total', 0),
                        'completed': getattr(batch.request_counts, 'completed', 0),
                        'failed': getattr(batch.request_counts, 'failed', 0),
                    }
                except Exception as e:
                    logger.warning(f"Could not parse request counts: {e}")

            return result

        except AttributeError as e:
            logger.error(f"Invalid batch response format: {e}")
            raise ValueError(f"Invalid batch response format: {e}")

    def is_terminal_status(self, status: str) -> bool:
        """
        Check if a batch status is terminal (no further polling needed).

        Args:
            status: Batch status string

        Returns:
            True if status is terminal, False otherwise
        """
        terminal_statuses = {'completed', 'failed', 'expired', 'cancelled'}
        return status.lower() in terminal_statuses

    def is_success_status(self, status: str) -> bool:
        """
        Check if a batch status represents successful completion.

        Args:
            status: Batch status string

        Returns:
            True if batch completed successfully, False otherwise
        """
        return status.lower() == 'completed'

    async def close(self):
        """
        Close the OpenAI client and cleanup resources.
        """
        try:
            await self.client.close()
            logger.info("OpenAI client closed successfully")
        except Exception as e:
            logger.warning(f"Error closing OpenAI client: {e}")

    def __repr__(self) -> str:
        """String representation with redacted API key."""
        key_preview = self._api_key[:8] + "..." if len(self._api_key) > 8 else "***"
        return f"OpenAIBatchClient(api_key={key_preview})"
