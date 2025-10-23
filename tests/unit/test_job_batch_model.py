"""
Unit tests for JobBatch model and multi-batch PollingJob functionality.

This module tests:
- JobBatch model creation and properties
- JobBatch terminal state logic (completed, failed, cancelled, expired)
- PollingJob multi-batch helper properties
- Unique constraint enforcement on (job_id, batch_id)
- Cascade delete behavior when job is deleted
- Batch completion summary and statistics
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.models import JobBatch, PollingJob, Secret, Base


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_secret(db_session):
    """Create a sample secret for testing."""
    secret = Secret(
        name="test-openai-secret",
        type="openai",
        value="encrypted-sk-test-key",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(secret)
    db_session.commit()
    db_session.refresh(secret)
    return secret


@pytest.fixture
def sample_job(db_session, sample_secret):
    """Create a sample polling job for testing."""
    job = PollingJob(
        name="test-multi-batch-job",
        openai_secret_id=sample_secret.id,
        keboola_secret_id=sample_secret.id,
        keboola_stack_url="https://connection.keboola.com",
        keboola_component_id="kds-team.app-custom-python",
        keboola_configuration_id="12345",
        status="active",
        poll_interval_seconds=120,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ============================================================================
# JobBatch Model Tests
# ============================================================================


class TestJobBatchCreation:
    """Test cases for basic JobBatch model creation."""

    def test_job_batch_creation(self, db_session, sample_job):
        """Test basic JobBatch model creation with required fields."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_abc123",
            status="in_progress",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        # Verify basic attributes
        assert batch.id is not None
        assert batch.job_id == sample_job.id
        assert batch.batch_id == "batch_abc123"
        assert batch.status == "in_progress"
        assert batch.created_at is not None
        assert batch.completed_at is None

    def test_job_batch_default_status(self, db_session, sample_job):
        """Test that default status is 'in_progress'."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_xyz789",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.status == "in_progress"

    def test_job_batch_timestamps(self, db_session, sample_job):
        """Test that timestamps are set correctly."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_test123",
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        assert batch.created_at is not None
        assert isinstance(batch.created_at, datetime)
        assert batch.completed_at is not None
        assert isinstance(batch.completed_at, datetime)

    def test_job_batch_relationship(self, db_session, sample_job):
        """Test that JobBatch has proper relationship to PollingJob."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_relationship_test",
            status="in_progress",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        # Test relationship
        assert batch.job is not None
        assert batch.job.id == sample_job.id
        assert batch.job.name == sample_job.name

    def test_job_batch_repr(self, db_session, sample_job):
        """Test JobBatch string representation."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_repr_test",
            status="completed",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        repr_str = repr(batch)
        assert "JobBatch" in repr_str
        assert str(batch.id) in repr_str
        assert str(batch.job_id) in repr_str
        assert "batch_repr_test" in repr_str
        assert "completed" in repr_str


class TestJobBatchProperties:
    """Test cases for JobBatch property methods."""

    def test_batch_is_terminal_property_in_progress(self, db_session, sample_job):
        """Test is_terminal property returns False for in_progress status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_in_progress",
            status="in_progress",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_terminal is False

    def test_batch_is_terminal_property_completed(self, db_session, sample_job):
        """Test is_terminal property returns True for completed status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_completed",
            status="completed",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_terminal is True

    def test_batch_is_terminal_property_failed(self, db_session, sample_job):
        """Test is_terminal property returns True for failed status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_failed",
            status="failed",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_terminal is True

    def test_batch_is_terminal_property_cancelled(self, db_session, sample_job):
        """Test is_terminal property returns True for cancelled status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_cancelled",
            status="cancelled",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_terminal is True

    def test_batch_is_terminal_property_expired(self, db_session, sample_job):
        """Test is_terminal property returns True for expired status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_expired",
            status="expired",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_terminal is True

    def test_batch_is_completed_property(self, db_session, sample_job):
        """Test is_completed property for completed status."""
        batch_completed = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_completed_check",
            status="completed",
        )
        batch_failed = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_failed_check",
            status="failed",
        )
        db_session.add_all([batch_completed, batch_failed])
        db_session.commit()

        assert batch_completed.is_completed is True
        assert batch_failed.is_completed is False

    def test_batch_is_failed_property_failed(self, db_session, sample_job):
        """Test is_failed property returns True for failed status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_is_failed",
            status="failed",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_failed is True

    def test_batch_is_failed_property_cancelled(self, db_session, sample_job):
        """Test is_failed property returns True for cancelled status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_is_cancelled",
            status="cancelled",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_failed is True

    def test_batch_is_failed_property_expired(self, db_session, sample_job):
        """Test is_failed property returns True for expired status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_is_expired",
            status="expired",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_failed is True

    def test_batch_is_failed_property_completed(self, db_session, sample_job):
        """Test is_failed property returns False for completed status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_not_failed",
            status="completed",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_failed is False

    def test_batch_is_failed_property_in_progress(self, db_session, sample_job):
        """Test is_failed property returns False for in_progress status."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_still_running",
            status="in_progress",
        )
        db_session.add(batch)
        db_session.commit()

        assert batch.is_failed is False


class TestPollingJobMultiBatchProperties:
    """Test cases for PollingJob multi-batch helper properties."""

    def test_job_all_batches_terminal_empty(self, db_session, sample_job):
        """Test all_batches_terminal returns False when no batches exist."""
        assert sample_job.all_batches_terminal is False

    def test_job_all_batches_terminal_all_completed(self, db_session, sample_job):
        """Test all_batches_terminal returns True when all batches are completed."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id=f"batch_comp_{i}", status="completed")
            for i in range(3)
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        assert sample_job.all_batches_terminal is True

    def test_job_all_batches_terminal_mixed_terminal(self, db_session, sample_job):
        """Test all_batches_terminal returns True when all batches are terminal (mixed states)."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id="batch_comp", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_fail", status="failed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_cancel", status="cancelled"),
            JobBatch(job_id=sample_job.id, batch_id="batch_expire", status="expired"),
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        assert sample_job.all_batches_terminal is True

    def test_job_all_batches_terminal_one_in_progress(self, db_session, sample_job):
        """Test all_batches_terminal returns False when one batch is in_progress."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id="batch_comp", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_progress", status="in_progress"),
            JobBatch(job_id=sample_job.id, batch_id="batch_fail", status="failed"),
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        assert sample_job.all_batches_terminal is False

    def test_job_completed_batches_property(self, db_session, sample_job):
        """Test completed_batches property returns only completed batches."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id="batch_comp_1", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_comp_2", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_fail", status="failed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_progress", status="in_progress"),
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        completed = sample_job.completed_batches
        assert len(completed) == 2
        assert all(b.is_completed for b in completed)
        assert all(b.status == "completed" for b in completed)

    def test_job_failed_batches_property(self, db_session, sample_job):
        """Test failed_batches property returns only failed/cancelled/expired batches."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id="batch_fail", status="failed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_cancel", status="cancelled"),
            JobBatch(job_id=sample_job.id, batch_id="batch_expire", status="expired"),
            JobBatch(job_id=sample_job.id, batch_id="batch_comp", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_progress", status="in_progress"),
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        failed = sample_job.failed_batches
        assert len(failed) == 3
        assert all(b.is_failed for b in failed)
        assert {b.status for b in failed} == {"failed", "cancelled", "expired"}

    def test_job_batch_completion_summary(self, db_session, sample_job):
        """Test batch_completion_summary returns correct statistics."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id="batch_comp_1", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_comp_2", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_comp_3", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_fail_1", status="failed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_fail_2", status="cancelled"),
            JobBatch(job_id=sample_job.id, batch_id="batch_progress_1", status="in_progress"),
            JobBatch(job_id=sample_job.id, batch_id="batch_progress_2", status="in_progress"),
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        summary = sample_job.batch_completion_summary
        assert summary["total"] == 7
        assert summary["completed"] == 3
        assert summary["failed"] == 2
        assert summary["in_progress"] == 2

    def test_job_batch_completion_summary_empty(self, db_session, sample_job):
        """Test batch_completion_summary returns zeros when no batches exist."""
        summary = sample_job.batch_completion_summary
        assert summary["total"] == 0
        assert summary["completed"] == 0
        assert summary["failed"] == 0
        assert summary["in_progress"] == 0


class TestJobBatchConstraints:
    """Test cases for JobBatch database constraints."""

    def test_batch_unique_constraint(self, db_session, sample_job):
        """Test unique constraint on (job_id, batch_id) prevents duplicates."""
        batch1 = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_unique_test",
            status="in_progress",
        )
        db_session.add(batch1)
        db_session.commit()

        # Try to create duplicate batch_id for same job
        batch2 = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_unique_test",  # Same batch_id
            status="completed",
        )
        db_session.add(batch2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_batch_unique_constraint_different_jobs(self, db_session, sample_secret):
        """Test same batch_id can exist in different jobs."""
        # Create two different jobs
        job1 = PollingJob(
            name="job-1",
            openai_secret_id=sample_secret.id,
            keboola_secret_id=sample_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            status="active",
        )
        job2 = PollingJob(
            name="job-2",
            openai_secret_id=sample_secret.id,
            keboola_secret_id=sample_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="67890",
            status="active",
        )
        db_session.add_all([job1, job2])
        db_session.commit()

        # Same batch_id in different jobs should be allowed
        batch1 = JobBatch(job_id=job1.id, batch_id="batch_shared", status="in_progress")
        batch2 = JobBatch(job_id=job2.id, batch_id="batch_shared", status="completed")
        db_session.add_all([batch1, batch2])
        db_session.commit()  # Should not raise

        assert batch1.batch_id == batch2.batch_id
        assert batch1.job_id != batch2.job_id

    def test_batch_id_format_constraint(self, db_session, sample_job):
        """Test batch_id must start with 'batch_' prefix."""
        batch_invalid = JobBatch(
            job_id=sample_job.id,
            batch_id="invalid_format",  # Missing 'batch_' prefix
            status="in_progress",
        )
        db_session.add(batch_invalid)

        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "check_batch_id_format" in str(exc_info.value).lower() or "constraint" in str(exc_info.value).lower()

    def test_batch_id_length_constraint(self, db_session, sample_job):
        """Test batch_id must not exceed 255 characters."""
        # Create a batch_id longer than 255 characters
        long_batch_id = "batch_" + "x" * 260
        batch_long = JobBatch(
            job_id=sample_job.id,
            batch_id=long_batch_id,
            status="in_progress",
        )
        db_session.add(batch_long)

        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "check_batch_id_length" in str(exc_info.value).lower() or "constraint" in str(exc_info.value).lower()


class TestJobBatchCascadeDelete:
    """Test cases for cascade delete behavior."""

    def test_batch_cascade_delete_on_job_deletion(self, db_session, sample_job):
        """Test that batches are deleted when job is deleted (cascade delete)."""
        # Create multiple batches
        batches = [
            JobBatch(job_id=sample_job.id, batch_id=f"batch_cascade_{i}", status="in_progress")
            for i in range(5)
        ]
        db_session.add_all(batches)
        db_session.commit()

        # Verify batches exist
        batch_count = db_session.query(JobBatch).filter(JobBatch.job_id == sample_job.id).count()
        assert batch_count == 5

        # Delete the job
        db_session.delete(sample_job)
        db_session.commit()

        # Verify all batches are deleted
        batch_count_after = db_session.query(JobBatch).count()
        assert batch_count_after == 0

    def test_batch_cascade_delete_multiple_jobs(self, db_session, sample_secret):
        """Test cascade delete with multiple jobs having batches."""
        # Create multiple jobs
        jobs = [
            PollingJob(
                name=f"job-{i}",
                openai_secret_id=sample_secret.id,
                keboola_secret_id=sample_secret.id,
                keboola_stack_url="https://connection.keboola.com",
                keboola_component_id="kds-team.app-custom-python",
                keboola_configuration_id=f"config-{i}",
                status="active",
            )
            for i in range(3)
        ]
        db_session.add_all(jobs)
        db_session.commit()

        # Create batches for each job
        for job in jobs:
            batches = [
                JobBatch(job_id=job.id, batch_id=f"batch_{job.id}_{i}", status="in_progress")
                for i in range(3)
            ]
            db_session.add_all(batches)
        db_session.commit()

        # Verify total batches
        total_batches = db_session.query(JobBatch).count()
        assert total_batches == 9  # 3 jobs * 3 batches

        # Delete one job
        db_session.delete(jobs[0])
        db_session.commit()

        # Verify only that job's batches are deleted
        remaining_batches = db_session.query(JobBatch).count()
        assert remaining_batches == 6  # 2 jobs * 3 batches


class TestJobBatchEdgeCases:
    """Test cases for edge cases and special scenarios."""

    def test_batch_with_null_completed_at(self, db_session, sample_job):
        """Test that completed_at can be null for in_progress batches."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_no_completion",
            status="in_progress",
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)

        assert batch.completed_at is None

    def test_batch_status_update(self, db_session, sample_job):
        """Test updating batch status from in_progress to completed."""
        batch = JobBatch(
            job_id=sample_job.id,
            batch_id="batch_status_change",
            status="in_progress",
        )
        db_session.add(batch)
        db_session.commit()

        # Update status
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(batch)

        assert batch.status == "completed"
        assert batch.is_terminal is True
        assert batch.is_completed is True
        assert batch.completed_at is not None

    def test_job_repr_with_batches(self, db_session, sample_job):
        """Test PollingJob repr includes batch count."""
        # Add batches
        batches = [
            JobBatch(job_id=sample_job.id, batch_id=f"batch_repr_{i}", status="in_progress")
            for i in range(4)
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        repr_str = repr(sample_job)
        assert "PollingJob" in repr_str
        assert "batch_count=4" in repr_str

    def test_batch_ordering(self, db_session, sample_job):
        """Test that batches are ordered by created_at."""
        # Create batches with slight time differences
        batches = []
        for i in range(3):
            batch = JobBatch(
                job_id=sample_job.id,
                batch_id=f"batch_order_{i}",
                status="in_progress",
            )
            db_session.add(batch)
            db_session.commit()
            db_session.refresh(batch)
            batches.append(batch)

        db_session.refresh(sample_job)

        # Verify batches are ordered by created_at
        job_batches = sample_job.batches
        for i in range(len(job_batches) - 1):
            assert job_batches[i].created_at <= job_batches[i + 1].created_at

    def test_multiple_batches_all_terminal_states(self, db_session, sample_job):
        """Test job with batches in all possible terminal states."""
        batches = [
            JobBatch(job_id=sample_job.id, batch_id="batch_completed", status="completed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_failed", status="failed"),
            JobBatch(job_id=sample_job.id, batch_id="batch_cancelled", status="cancelled"),
            JobBatch(job_id=sample_job.id, batch_id="batch_expired", status="expired"),
        ]
        db_session.add_all(batches)
        db_session.commit()
        db_session.refresh(sample_job)

        assert sample_job.all_batches_terminal is True
        assert len(sample_job.completed_batches) == 1
        assert len(sample_job.failed_batches) == 3

        summary = sample_job.batch_completion_summary
        assert summary["total"] == 4
        assert summary["completed"] == 1
        assert summary["failed"] == 3
        assert summary["in_progress"] == 0

    def test_empty_batches_list(self, db_session, sample_job):
        """Test job with no batches has empty lists and correct summary."""
        assert len(sample_job.batches) == 0
        assert len(sample_job.completed_batches) == 0
        assert len(sample_job.failed_batches) == 0
        assert sample_job.all_batches_terminal is False

    def test_batch_foreign_key_constraint(self, db_session):
        """Test that batch requires valid job_id."""
        # Try to create batch with non-existent job_id
        batch = JobBatch(
            job_id=99999,  # Non-existent job
            batch_id="batch_invalid_fk",
            status="in_progress",
        )
        db_session.add(batch)

        with pytest.raises(IntegrityError):
            db_session.commit()
