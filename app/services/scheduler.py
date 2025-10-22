"""
Job scheduler for TeckoChecker polling system.

Manages scheduling of polling jobs, determining which jobs need to be checked
and when the next check should occur based on individual polling intervals.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Manages the scheduling of polling jobs.

    Handles:
    - Determining which jobs need to be checked now
    - Calculating next check times based on polling intervals
    - Respecting individual job configurations
    """

    def __init__(self, db_session: Session):
        """
        Initialize the job scheduler.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    def get_jobs_to_check(self, limit: Optional[int] = None) -> List[Any]:
        """
        Get all jobs that are ready to be checked.

        A job is ready to be checked if:
        1. It has status 'active'
        2. Its next_check_at time is in the past or null (first check)

        Args:
            limit: Optional maximum number of jobs to return

        Returns:
            List of polling job records ready to be checked
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            now = datetime.utcnow()

            # Query for active jobs that need checking
            query = self.db.query(PollingJob).filter(
                and_(
                    PollingJob.status == 'active',
                    or_(
                        PollingJob.next_check_at.is_(None),
                        PollingJob.next_check_at <= now
                    )
                )
            ).order_by(PollingJob.next_check_at.asc().nullsfirst())

            if limit:
                query = query.limit(limit)

            jobs = query.all()

            logger.info(f"Found {len(jobs)} jobs ready to be checked")

            return jobs

        except Exception as e:
            logger.error(f"Error getting jobs to check: {e}")
            raise

    def schedule_next_check(
        self,
        job_id: int,
        poll_interval_seconds: Optional[int] = None,
    ) -> datetime:
        """
        Schedule the next check for a job.

        Updates the job's next_check_at timestamp based on the polling interval.

        Args:
            job_id: ID of the job to schedule
            poll_interval_seconds: Optional override for poll interval.
                                   If not provided, uses job's configured interval.

        Returns:
            The calculated next check time

        Raises:
            ValueError: If job not found or invalid interval
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            job = self.db.query(PollingJob).filter(PollingJob.id == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Use provided interval or job's configured interval
            interval = poll_interval_seconds if poll_interval_seconds else job.poll_interval_seconds

            if not interval or interval <= 0:
                raise ValueError(f"Invalid poll interval: {interval}")

            # Calculate next check time
            now = datetime.utcnow()
            next_check = now + timedelta(seconds=interval)

            # Update job record
            job.last_check_at = now
            job.next_check_at = next_check
            self.db.commit()

            logger.info(
                f"Scheduled job {job_id} for next check at {next_check} "
                f"(interval: {interval}s)"
            )

            return next_check

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error scheduling next check for job {job_id}: {e}")
            raise

    def update_job_status(
        self,
        job_id: int,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """
        Update the status of a polling job.

        Args:
            job_id: ID of the job to update
            status: New status ('active', 'paused', 'completed', 'failed')
            completed_at: Optional completion timestamp

        Raises:
            ValueError: If job not found or invalid status
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        valid_statuses = {'active', 'paused', 'completed', 'failed'}

        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        try:
            job = self.db.query(PollingJob).filter(PollingJob.id == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            old_status = job.status
            job.status = status

            if completed_at:
                job.completed_at = completed_at

            # If marking as completed or failed, set completed_at if not already set
            if status in {'completed', 'failed'} and not job.completed_at:
                job.completed_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Updated job {job_id} status from {old_status} to {status}")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating job {job_id} status: {e}")
            raise

    def get_next_schedule_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the next scheduled check across all jobs.

        Useful for determining how long to sleep in the polling loop.

        Returns:
            Datetime of the next scheduled check, or None if no jobs scheduled
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            result = self.db.query(PollingJob.next_check_at).filter(
                and_(
                    PollingJob.status == 'active',
                    PollingJob.next_check_at.isnot(None)
                )
            ).order_by(PollingJob.next_check_at.asc()).first()

            if result and result[0]:
                logger.debug(f"Next scheduled check at: {result[0]}")
                return result[0]

            logger.debug("No scheduled checks found")
            return None

        except Exception as e:
            logger.error(f"Error getting next schedule time: {e}")
            return None

    def get_active_jobs_count(self) -> int:
        """
        Get the count of active polling jobs.

        Returns:
            Number of active jobs
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            count = self.db.query(PollingJob).filter(
                PollingJob.status == 'active'
            ).count()

            logger.debug(f"Active jobs count: {count}")
            return count

        except Exception as e:
            logger.error(f"Error getting active jobs count: {e}")
            return 0

    def get_job_details(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific job.

        Args:
            job_id: ID of the job

        Returns:
            Dictionary with job details, or None if not found
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            job = self.db.query(PollingJob).filter(PollingJob.id == job_id).first()

            if not job:
                return None

            return {
                'id': job.id,
                'name': job.name,
                'batch_id': job.batch_id,
                'status': job.status,
                'poll_interval_seconds': job.poll_interval_seconds,
                'last_check_at': job.last_check_at,
                'next_check_at': job.next_check_at,
                'created_at': job.created_at,
                'completed_at': job.completed_at,
                'keboola_stack_url': job.keboola_stack_url,
                'keboola_configuration_id': job.keboola_configuration_id,
            }

        except Exception as e:
            logger.error(f"Error getting job details for {job_id}: {e}")
            return None

    def pause_job(self, job_id: int) -> None:
        """
        Pause a polling job.

        Args:
            job_id: ID of the job to pause

        Raises:
            ValueError: If job not found
        """
        self.update_job_status(job_id, 'paused')
        logger.info(f"Paused job {job_id}")

    def resume_job(self, job_id: int, reset_schedule: bool = True) -> None:
        """
        Resume a paused polling job.

        Args:
            job_id: ID of the job to resume
            reset_schedule: If True, reset next_check_at to trigger immediate check

        Raises:
            ValueError: If job not found
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            job = self.db.query(PollingJob).filter(PollingJob.id == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            job.status = 'active'

            if reset_schedule:
                # Set next check to now for immediate execution
                job.next_check_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Resumed job {job_id}")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error resuming job {job_id}: {e}")
            raise

    def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """
        Clean up old completed/failed jobs.

        Args:
            days_old: Remove jobs completed more than this many days ago

        Returns:
            Number of jobs deleted
        """
        from app.models import PollingJob  # Import here to avoid circular dependency

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            result = self.db.query(PollingJob).filter(
                and_(
                    PollingJob.status.in_(['completed', 'failed']),
                    PollingJob.completed_at < cutoff_date
                )
            ).delete()

            self.db.commit()

            logger.info(f"Cleaned up {result} old jobs (older than {days_old} days)")

            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning up old jobs: {e}")
            raise
