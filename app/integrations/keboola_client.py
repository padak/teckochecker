"""
Keboola Connection API client for TeckoChecker.

Provides integration with Keboola Connection API to trigger jobs
with proper error handling, retries, and exponential backoff.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)


class KeboolaClient:
    """
    Client for interacting with Keboola Connection API.

    Handles job triggering with automatic retries and exponential backoff.
    Uses Storage API token for authentication.
    """

    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds
    MAX_RETRY_DELAY = 60  # seconds
    RETRY_MULTIPLIER = 2

    # Request timeout
    REQUEST_TIMEOUT = 30  # seconds

    def __init__(self, storage_api_token: str, stack_url: str):
        """
        Initialize the Keboola Connection client.

        Args:
            storage_api_token: Keboola Storage API token for authentication
            stack_url: Base URL of the Keboola stack (e.g., https://connection.keboola.com)
        """
        self.storage_api_token = storage_api_token
        self.stack_url = stack_url.rstrip("/")  # Remove trailing slash if present
        self._token_preview = storage_api_token[:8] + "..." if len(storage_api_token) > 8 else "***"

    async def trigger_job(
        self,
        configuration_id: str,
        component_id: str,
        tag: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a Keboola Connection job with automatic retries.

        Implements exponential backoff for retries on transient failures.

        Args:
            configuration_id: The ID of the configuration to run
            component_id: Component ID (e.g., 'kds-team.app-custom-python')
            tag: Optional tag to identify the job run
            parameters: Optional dict of parameters to pass to the job (NEW)

        Returns:
            Dictionary containing:
                - job_id: ID of the triggered job
                - status: Initial status of the job
                - url: URL to view the job in Keboola UI
                - created_time: Timestamp when job was created

        Raises:
            ValueError: If configuration_id or component_id is invalid
            aiohttp.ClientError: If all retry attempts fail
        """
        if not configuration_id or not isinstance(configuration_id, str):
            raise ValueError(f"Invalid configuration_id: {configuration_id}")
        if not component_id or not isinstance(component_id, str):
            raise ValueError(f"Invalid component_id: {component_id}")

        logger.info(f"Triggering Keboola job for configuration: {configuration_id}")

        retry_delay = self.INITIAL_RETRY_DELAY
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self._execute_job_trigger(
                    configuration_id=configuration_id,
                    component_id=component_id,
                    tag=tag,
                    parameters=parameters,
                )

                logger.info(
                    f"Successfully triggered Keboola job {result.get('job_id')} "
                    f"for configuration {configuration_id} "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )

                return result

            except aiohttp.ClientResponseError as e:
                last_exception = e

                # For 4xx errors (except 429), don't retry
                if 400 <= e.status < 500 and e.status != 429:
                    logger.error(
                        f"Client error triggering Keboola job for {configuration_id}: "
                        f"Status {e.status}, {e.message}"
                    )
                    raise

                logger.warning(
                    f"HTTP error triggering Keboola job for {configuration_id}, "
                    f"attempt {attempt + 1}/{self.MAX_RETRIES}: "
                    f"Status {e.status}, {e.message}"
                )

            except aiohttp.ClientConnectionError as e:
                last_exception = e
                logger.warning(
                    f"Connection error triggering Keboola job for {configuration_id}, "
                    f"attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )

            except aiohttp.ClientError as e:
                last_exception = e
                logger.warning(
                    f"Client error triggering Keboola job for {configuration_id}, "
                    f"attempt {attempt + 1}/{self.MAX_RETRIES}: {e}"
                )

            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    f"Timeout triggering Keboola job for {configuration_id}, "
                    f"attempt {attempt + 1}/{self.MAX_RETRIES}"
                )

            # If this wasn't the last attempt, wait before retrying
            if attempt < self.MAX_RETRIES - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

                # Exponential backoff with cap
                retry_delay = min(retry_delay * self.RETRY_MULTIPLIER, self.MAX_RETRY_DELAY)

        # All retries exhausted
        logger.error(
            f"All {self.MAX_RETRIES} retry attempts failed for configuration {configuration_id}"
        )
        raise (
            last_exception
            if last_exception
            else Exception("Failed to trigger Keboola job after all retries")
        )

    async def _execute_job_trigger(
        self,
        configuration_id: str,
        component_id: str,
        tag: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the actual job trigger API call.

        Args:
            configuration_id: The ID of the configuration to run
            component_id: Component ID (required)
            tag: Optional tag to identify the job run
            parameters: Optional dict of parameters to pass to the job (NEW)

        Returns:
            Dictionary with job information

        Raises:
            aiohttp.ClientError: On HTTP errors
        """
        # Build the API endpoint - using queue API
        # Extract the region from the stack_url (e.g., eu-central-1)
        # From https://connection.eu-central-1.keboola.com to https://queue.eu-central-1.keboola.com
        queue_url = self.stack_url.replace("connection", "queue")
        endpoint = f"{queue_url}/jobs"

        # Prepare headers
        headers = {
            "X-StorageApi-Token": self.storage_api_token,
            "Content-Type": "application/json",
        }

        # Prepare payload with the correct format
        payload = {
            "mode": "run",
            "component": component_id,
            "config": configuration_id,
        }

        if tag:
            payload["tag"] = tag

        # NEW: Add parameters if provided
        if parameters:
            payload["configData"] = {
                "parameters": parameters
            }

        # Create timeout
        timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)

        # DEBUG: Log the exact payload being sent to Keboola
        logger.info("=" * 80)
        logger.info("KEBOOLA API REQUEST DEBUG")
        logger.info("=" * 80)
        logger.info(f"Endpoint: {endpoint}")
        logger.info(f"Payload: {payload}")
        logger.info(f"Headers: {{'X-StorageApi-Token': '***REDACTED***'}}")
        logger.info("=" * 80)

        # Execute the request
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                # Raise for HTTP errors
                response.raise_for_status()

                # Parse response
                data = await response.json()

                # DEBUG: Log the response
                logger.info("=" * 80)
                logger.info("KEBOOLA API RESPONSE DEBUG")
                logger.info("=" * 80)
                logger.info(f"Status: {response.status}")
                logger.info(f"Response: {data}")
                logger.info("=" * 80)

                # Parse and normalize the response
                return self._parse_job_response(data, configuration_id)

    def _parse_job_response(self, data: Dict[str, Any], configuration_id: str) -> Dict[str, Any]:
        """
        Parse the job trigger response from Keboola API.

        Args:
            data: JSON response from Keboola API
            configuration_id: Configuration ID that was triggered

        Returns:
            Normalized dictionary with job information

        Raises:
            ValueError: If response format is invalid
        """
        try:
            # Keboola API returns job information in the response
            job_id = data.get("id")
            if not job_id:
                raise ValueError("No job ID in response")

            result = {
                "job_id": str(job_id),
                "status": data.get("status", "created"),
                "configuration_id": configuration_id,
                "created_time": data.get("createdTime"),
                "url": data.get("url"),
            }

            # Add additional fields if available
            if "component" in data:
                result["component_id"] = data["component"]

            if "runId" in data:
                result["run_id"] = data["runId"]

            if "tag" in data:
                result["tag"] = data["tag"]

            return result

        except (KeyError, TypeError) as e:
            logger.error(f"Invalid job response format: {e}")
            raise ValueError(f"Invalid job response format: {e}")

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a Keboola job.

        Args:
            job_id: The ID of the job to check

        Returns:
            Dictionary containing job status information

        Raises:
            ValueError: If job_id is invalid
            aiohttp.ClientError: On HTTP errors
        """
        if not job_id or not isinstance(job_id, str):
            raise ValueError(f"Invalid job_id: {job_id}")

        logger.info(f"Checking Keboola job status for: {job_id}")

        endpoint = f"{self.stack_url}/v2/storage/jobs/{job_id}"

        headers = {
            "X-StorageApi-Token": self.storage_api_token,
        }

        timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()

                return {
                    "job_id": str(data.get("id")),
                    "status": data.get("status"),
                    "created_time": data.get("createdTime"),
                    "start_time": data.get("startTime"),
                    "end_time": data.get("endTime"),
                    "duration_seconds": data.get("durationSeconds"),
                    "is_finished": data.get("isFinished", False),
                    "url": data.get("url"),
                }

    def is_job_finished(self, status: str) -> bool:
        """
        Check if a job status indicates the job is finished.

        Args:
            status: Job status string

        Returns:
            True if job is finished, False otherwise
        """
        finished_statuses = {"success", "error", "cancelled", "terminated"}
        return status.lower() in finished_statuses

    def is_job_successful(self, status: str) -> bool:
        """
        Check if a job status indicates successful completion.

        Args:
            status: Job status string

        Returns:
            True if job completed successfully, False otherwise
        """
        return status.lower() == "success"

    def __repr__(self) -> str:
        """String representation with redacted API token."""
        return f"KeboolaClient(stack_url={self.stack_url}, token={self._token_preview})"
