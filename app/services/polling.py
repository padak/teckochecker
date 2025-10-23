"""
Polling service for TeckoChecker.

Orchestrates the continuous polling of OpenAI batch jobs and triggers
Keboola jobs upon completion. Handles concurrent polling with asyncio.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from contextlib import contextmanager


from app.integrations.openai_client import OpenAIBatchClient
from app.integrations.keboola_client import KeboolaClient
from app.services.scheduler import JobScheduler

logger = logging.getLogger(__name__)


class PollingService:
    """
    Main polling service that orchestrates job status checking and action triggering.

    Handles:
    - Concurrent polling of multiple OpenAI batch jobs
    - Triggering Keboola jobs on completion
    - Job lifecycle management
    - Error handling and recovery
    """

    # Polling loop configuration
    DEFAULT_SLEEP_SECONDS = 5  # Default sleep if no jobs scheduled
    MAX_CONCURRENT_CHECKS = 10  # Maximum concurrent status checks
    POLL_BATCH_SIZE = 50  # Number of jobs to process in each iteration

    def __init__(
        self,
        db_session_factory,
        default_poll_interval: int = 120,
        max_concurrent_checks: Optional[int] = None,
    ):
        """
        Initialize the polling service.

        Args:
            db_session_factory: Factory function to create database sessions
            default_poll_interval: Default polling interval in seconds
            max_concurrent_checks: Maximum number of concurrent status checks
        """
        self.db_session_factory = db_session_factory
        self.default_poll_interval = default_poll_interval
        self.max_concurrent_checks = max_concurrent_checks or self.MAX_CONCURRENT_CHECKS

        self._is_running = False
        self._shutdown_event = asyncio.Event()

        # Cache for API clients (reused across checks)
        self._openai_clients: Dict[int, OpenAIBatchClient] = {}
        self._keboola_clients: Dict[int, KeboolaClient] = {}

        logger.info(
            f"PollingService initialized with max_concurrent_checks={self.max_concurrent_checks}, "
            f"default_poll_interval={self.default_poll_interval}s"
        )

    async def polling_loop(self) -> None:
        """
        Main polling loop that continuously checks job statuses.

        This is the core engine that:
        1. Gets jobs ready to be checked
        2. Checks their statuses concurrently
        3. Triggers actions when appropriate
        4. Reschedules jobs for next check
        5. Sleeps until next scheduled check

        Runs until shutdown is requested.
        """
        logger.info("Starting polling loop")
        self._is_running = True

        try:
            while self._is_running:
                try:
                    # Create a new database session for this iteration
                    with self._create_db_session() as db:
                        scheduler = JobScheduler(db)

                        # Get jobs that need checking
                        jobs_to_check = scheduler.get_jobs_to_check(limit=self.POLL_BATCH_SIZE)

                        if jobs_to_check:
                            logger.info(f"Processing {len(jobs_to_check)} jobs")

                            # Process jobs concurrently (with limit)
                            await self._process_jobs_concurrent(jobs_to_check)

                        # Determine how long to sleep
                        sleep_duration = await self._calculate_sleep_duration(scheduler)

                        logger.debug(f"Sleeping for {sleep_duration} seconds")

                        # Sleep with periodic checks for shutdown
                        await self._interruptible_sleep(sleep_duration)

                except Exception as e:
                    logger.error(f"Error in polling loop iteration: {e}", exc_info=True)
                    # Sleep briefly before retrying to avoid tight error loop
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
            raise

        finally:
            logger.info("Polling loop stopped")
            self._is_running = False
            await self._cleanup_clients()

    async def _process_jobs_concurrent(self, jobs: List[Any]) -> None:
        """
        Process multiple jobs concurrently with a concurrency limit.

        Args:
            jobs: List of job records to process
        """
        # Create a semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(self.max_concurrent_checks)

        async def process_with_semaphore(job):
            async with semaphore:
                await self._process_single_job(job)

        # Process all jobs concurrently (limited by semaphore)
        tasks = [process_with_semaphore(job) for job in jobs]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_job(self, job: Any) -> None:
        """
        Process multi-batch polling check.

        Logic:
        1. Loop through all job.batches
        2. For each non-terminal batch, check OpenAI status
        3. Update batch status in database
        4. If ALL batches terminal → trigger Keboola with metadata
        5. Otherwise → reschedule next check

        Args:
            job: Job record to process
        """
        job_id = job.id

        try:
            logger.info(f"Processing job {job_id} with {len(job.batches)} batches")

            # Get OpenAI client for this job
            openai_client = await self._get_openai_client(job)

            # Check each batch that's not yet terminal
            batches_to_check = [b for b in job.batches if not b.is_terminal]

            if not batches_to_check:
                # All already terminal - shouldn't happen, but handle gracefully
                if job.all_batches_terminal and job.status == "active":
                    await self._trigger_keboola_with_results(job)
                return

            logger.info(f"Job {job_id}: Checking {len(batches_to_check)} non-terminal batches")

            # Process batches concurrently (respects semaphore limit)
            check_tasks = [
                self._check_single_batch(openai_client, job_batch)
                for job_batch in batches_to_check
            ]

            await asyncio.gather(*check_tasks, return_exceptions=True)

            # Refresh job from DB to get updated batch statuses
            with self._create_db_session() as db:
                from app.models import PollingJob
                job = db.query(PollingJob).filter(PollingJob.id == job_id).first()
                if not job:
                    logger.error(f"Job {job_id} not found after batch checks")
                    return

                # Log current state
                summary = job.batch_completion_summary
                await self._log_status_check(
                    job_id,
                    {"status": "checking"},
                    message=f"Batch status: {summary['completed']} completed, "
                            f"{summary['failed']} failed, {summary['in_progress']} in progress"
                )

                # Check if all batches are terminal
                if job.all_batches_terminal:
                    await self._trigger_keboola_with_results(job)
                    job.status = "completed_with_failures" if job.failed_batches else "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
                else:
                    # Reschedule next check
                    await self._reschedule_job(job)

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            await self._handle_job_error(job, str(e))

    async def _check_single_batch(
        self,
        openai_client: Any,
        job_batch: Any
    ) -> None:
        """
        Check status of single batch and update database.

        Args:
            openai_client: OpenAI client instance
            job_batch: JobBatch instance to check
        """
        try:
            status_result = await openai_client.check_batch_status(job_batch.batch_id)
            new_status = status_result["status"]

            logger.debug(f"Batch {job_batch.batch_id}: status '{new_status}'")

            if new_status != job_batch.status:
                with self._create_db_session() as db:
                    from app.models import JobBatch

                    # Get fresh batch instance from this session
                    batch = db.query(JobBatch).filter(JobBatch.id == job_batch.id).first()
                    if batch:
                        batch.status = new_status

                        if batch.is_terminal:
                            batch.completed_at = datetime.now(timezone.utc)

                        db.commit()
                        logger.info(f"Batch {job_batch.batch_id}: status updated to '{new_status}'")

        except Exception as e:
            logger.error(f"Failed to check batch {job_batch.batch_id}: {str(e)}", exc_info=True)
            await self._log_error(job_batch.job_id, f"Failed to check batch {job_batch.batch_id}: {str(e)}")

    async def _trigger_keboola_with_results(self, job: Any) -> None:
        """
        Trigger Keboola job with batch completion metadata.

        Passes parameters:
        - batch_ids_completed: List of successfully completed batch IDs
        - batch_ids_failed: List of failed/cancelled/expired batch IDs
        - batch_count_total: Total number of batches
        - batch_count_completed: Number of completed batches
        - batch_count_failed: Number of failed batches

        Args:
            job: PollingJob instance with batches loaded
        """
        job_id = job.id

        try:
            logger.info(f"Job {job_id}: All batches terminal, triggering Keboola job")

            # Get or create Keboola client for this job
            keboola_client = await self._get_keboola_client(job)

            # Prepare metadata
            completed_ids = [b.batch_id for b in job.completed_batches]
            failed_ids = [b.batch_id for b in job.failed_batches]

            parameters = {
                "batch_ids_completed": completed_ids,
                "batch_ids_failed": failed_ids,
                "batch_count_total": len(job.batches),
                "batch_count_completed": len(completed_ids),
                "batch_count_failed": len(failed_ids),
            }

            logger.info(f"Job {job_id}: Triggering Keboola with metadata: {parameters}")

            # Trigger the Keboola job with parameters
            trigger_result = await keboola_client.trigger_job(
                configuration_id=job.keboola_configuration_id,
                component_id=job.keboola_component_id,
                parameters=parameters  # Pass batch metadata
            )

            logger.info(
                f"Job {job_id}: Successfully triggered Keboola job {trigger_result.get('job_id')} "
                f"with {len(completed_ids)} completed, {len(failed_ids)} failed batches"
            )

            # Log the action
            await self._log_action(
                job_id,
                action="keboola_triggered",
                result=trigger_result
            )

        except Exception as e:
            logger.error(f"Job {job_id}: Error triggering Keboola job: {e}", exc_info=True)
            await self._handle_job_error(job, f"Keboola trigger failed: {e}")

            # Mark job as failed
            with self._create_db_session() as db:
                from app.models import PollingJob
                job_to_fail = db.query(PollingJob).filter(PollingJob.id == job_id).first()
                if job_to_fail:
                    job_to_fail.status = "failed"
                    job_to_fail.completed_at = datetime.now(timezone.utc)
                    db.commit()

    # OLD METHODS REMOVED - no longer needed for multi-batch architecture
    # _handle_batch_completion() replaced by _trigger_keboola_with_results()
    # _handle_batch_terminal() logic now handled in _process_single_job()

    async def _reschedule_job(self, job: Any) -> None:
        """
        Reschedule a job for the next check.

        Args:
            job: Job record
        """
        job_id = job.id

        try:
            with self._create_db_session() as db:
                scheduler = JobScheduler(db)
                next_check = scheduler.schedule_next_check(job_id)
                logger.debug(f"Job {job_id}: Rescheduled for {next_check}")

        except Exception as e:
            logger.error(f"Error rescheduling job {job_id}: {e}")

    async def _handle_job_error(self, job: Any, error_message: str) -> None:
        """
        Handle errors that occur while processing a job.

        Args:
            job: Job record
            error_message: Error message
        """
        job_id = job.id

        logger.error(f"Job {job_id}: Error - {error_message}")

        try:
            # Log the error
            await self._log_error(job_id, error_message)

            # Reschedule with potentially longer interval
            # (could implement exponential backoff here)
            await self._reschedule_job(job)

        except Exception as e:
            logger.error(f"Error handling job error for {job_id}: {e}")

    async def _get_openai_client(self, job: Any) -> OpenAIBatchClient:
        """
        Get or create an OpenAI client for a job.

        Args:
            job: Job record

        Returns:
            OpenAI client instance
        """
        secret_id = job.openai_secret_id

        # Return cached client if available
        if secret_id in self._openai_clients:
            return self._openai_clients[secret_id]

        # Create new client
        api_key = await self._get_secret_value(secret_id)
        client = OpenAIBatchClient(api_key=api_key)

        # Cache for reuse
        self._openai_clients[secret_id] = client

        return client

    async def _get_keboola_client(self, job: Any) -> KeboolaClient:
        """
        Get or create a Keboola client for a job.

        Args:
            job: Job record

        Returns:
            Keboola client instance
        """
        secret_id = job.keboola_secret_id

        # Return cached client if available
        if secret_id in self._keboola_clients:
            return self._keboola_clients[secret_id]

        # Create new client
        api_token = await self._get_secret_value(secret_id)
        client = KeboolaClient(storage_api_token=api_token, stack_url=job.keboola_stack_url)

        # Cache for reuse
        self._keboola_clients[secret_id] = client

        return client

    async def _get_secret_value(self, secret_id: int) -> str:
        """
        Retrieve and decrypt a secret value.

        Args:
            secret_id: ID of the secret

        Returns:
            Decrypted secret value

        Raises:
            ValueError: If secret not found
        """
        from app.models import Secret  # Import here to avoid circular dependency
        from app.services.encryption import get_encryption_service

        with self._create_db_session() as db:
            secret = db.query(Secret).filter(Secret.id == secret_id).first()

            if not secret:
                raise ValueError(f"Secret {secret_id} not found")

            # Decrypt the secret value
            encryption_service = get_encryption_service()
            decrypted_value = encryption_service.decrypt(secret.value)

            return decrypted_value

    async def _log_status_check(
        self, job_id: int, status_result: Dict[str, Any], message: Optional[str] = None
    ) -> None:
        """
        Log a status check to the database.

        Args:
            job_id: ID of the job
            status_result: Result from status check
            message: Optional additional message
        """
        from app.models import PollingLog  # Import here to avoid circular dependency

        try:
            with self._create_db_session() as db:
                log_message = message or f"Status: {status_result.get('status')}"

                log_entry = PollingLog(
                    job_id=job_id,
                    status=status_result.get("status"),
                    message=log_message,
                    created_at=datetime.now(timezone.utc),
                )

                db.add(log_entry)
                db.commit()

        except Exception as e:
            logger.error(f"Error logging status check for job {job_id}: {e}")

    async def _log_action(self, job_id: int, action: str, result: Dict[str, Any]) -> None:
        """
        Log an action (like Keboola trigger) to the database.

        Args:
            job_id: ID of the job
            action: Action name
            result: Result from the action
        """
        from app.models import PollingLog  # Import here to avoid circular dependency

        try:
            with self._create_db_session() as db:
                message = f"Action: {action}, Result: {result.get('job_id', 'N/A')}"

                log_entry = PollingLog(
                    job_id=job_id,
                    status=action,
                    message=message,
                    created_at=datetime.now(timezone.utc),
                )

                db.add(log_entry)
                db.commit()

        except Exception as e:
            logger.error(f"Error logging action for job {job_id}: {e}")

    async def _log_error(self, job_id: int, error_message: str) -> None:
        """
        Log an error to the database.

        Args:
            job_id: ID of the job
            error_message: Error message
        """
        from app.models import PollingLog  # Import here to avoid circular dependency

        try:
            with self._create_db_session() as db:
                log_entry = PollingLog(
                    job_id=job_id,
                    status="error",
                    message=error_message,
                    created_at=datetime.now(timezone.utc),
                )

                db.add(log_entry)
                db.commit()

        except Exception as e:
            logger.error(f"Error logging error for job {job_id}: {e}")

    async def _calculate_sleep_duration(self, scheduler: JobScheduler) -> float:
        """
        Calculate how long to sleep before the next polling iteration.

        Args:
            scheduler: Job scheduler instance

        Returns:
            Sleep duration in seconds
        """
        next_check_time = scheduler.get_next_schedule_time()

        if not next_check_time:
            # No jobs scheduled, use default sleep
            return self.DEFAULT_SLEEP_SECONDS

        # Calculate time until next check
        now = datetime.now(timezone.utc)
        time_until_next = (next_check_time - now).total_seconds()

        # Don't sleep for negative time or too long
        if time_until_next <= 0:
            return 0

        # Cap at reasonable maximum
        return min(time_until_next, 60)

    async def _interruptible_sleep(self, duration: float) -> None:
        """
        Sleep for a duration while allowing interruption for shutdown.

        Args:
            duration: Sleep duration in seconds
        """
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=duration)
        except asyncio.TimeoutError:
            # Normal timeout - continue polling
            pass

    async def _cleanup_clients(self) -> None:
        """Clean up API clients on shutdown."""
        logger.info("Cleaning up API clients")

        # Close OpenAI clients
        for client in self._openai_clients.values():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Error closing OpenAI client: {e}")

        self._openai_clients.clear()
        self._keboola_clients.clear()

    @contextmanager
    def _create_db_session(self):
        """
        Context manager for database sessions.

        Yields:
            Database session
        """
        session_generator = self.db_session_factory()
        session = next(session_generator)
        try:
            yield session
        finally:
            try:
                next(session_generator)
            except StopIteration:
                pass
            finally:
                session.close()

    def shutdown(self) -> None:
        """
        Request graceful shutdown of the polling service.
        """
        logger.info("Shutdown requested")
        self._is_running = False
        self._shutdown_event.set()

    @property
    def is_running(self) -> bool:
        """Check if the polling service is currently running."""
        return self._is_running
