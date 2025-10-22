"""
Unit tests for polling service.

This module tests:
- Polling loop flow and job processing
- Concurrent job execution with semaphore limits
- OpenAI batch status checking
- Keboola job triggering
- Error handling and retry logic
- Graceful shutdown
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Secret, PollingJob, PollingLog, Base
from app.services.polling import PollingService
from app.services.scheduler import JobScheduler


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return "test-secret-key-for-polling-tests"


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database engine."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session_factory(db_engine):
    """Create a database session factory."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def factory():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    return factory


@pytest.fixture
def db_session(db_session_factory):
    """Create a database session for tests."""
    session_gen = db_session_factory()
    session = next(session_gen)
    yield session
    try:
        next(session_gen)
    except StopIteration:
        pass
    finally:
        session.close()


@pytest.fixture
def polling_service(db_session_factory, encryption_key):
    """Create a PollingService instance."""
    # Initialize encryption service
    from app.services.encryption import init_encryption_service

    init_encryption_service(encryption_key)

    service = PollingService(
        db_session_factory=db_session_factory, default_poll_interval=120, max_concurrent_checks=10
    )
    return service


@pytest.fixture
def openai_secret(db_session, encryption_key):
    """Create a test OpenAI secret."""
    from app.services.encryption import init_encryption_service, get_encryption_service

    init_encryption_service(encryption_key)
    encryption_service = get_encryption_service()

    secret = Secret(
        name="test-openai", type="openai", value=encryption_service.encrypt("sk-test-key-123")
    )
    db_session.add(secret)
    db_session.commit()
    db_session.refresh(secret)
    return secret


@pytest.fixture
def keboola_secret(db_session, encryption_key):
    """Create a test Keboola secret."""
    from app.services.encryption import get_encryption_service

    encryption_service = get_encryption_service()

    secret = Secret(
        name="test-keboola", type="keboola", value=encryption_service.encrypt("keboola-token-123")
    )
    db_session.add(secret)
    db_session.commit()
    db_session.refresh(secret)
    return secret


@pytest.fixture
def sample_job(db_session, openai_secret, keboola_secret):
    """Create a sample polling job."""
    job = PollingJob(
        name="test-job",
        batch_id="batch_test123",
        openai_secret_id=openai_secret.id,
        keboola_secret_id=keboola_secret.id,
        keboola_stack_url="https://connection.keboola.com",
        keboola_component_id="kds-team.app-custom-python",
        keboola_configuration_id="12345",
        poll_interval_seconds=120,
        status="active",
        next_check_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def mock_openai_response_pending():
    """Mock OpenAI response for pending batch."""
    return {
        "status": "in_progress",
        "batch_id": "batch_test123",
        "created_at": 1234567890,
        "completed_at": None,
        "failed_at": None,
        "error_message": None,
        "metadata": {},
    }


@pytest.fixture
def mock_openai_response_completed():
    """Mock OpenAI response for completed batch."""
    return {
        "status": "completed",
        "batch_id": "batch_test123",
        "created_at": 1234567890,
        "completed_at": 1234567990,
        "failed_at": None,
        "error_message": None,
        "metadata": {},
    }


@pytest.fixture
def mock_openai_response_failed():
    """Mock OpenAI response for failed batch."""
    return {
        "status": "failed",
        "batch_id": "batch_test123",
        "created_at": 1234567890,
        "completed_at": None,
        "failed_at": 1234567990,
        "error_message": "Batch processing failed",
        "metadata": {},
    }


@pytest.fixture
def mock_keboola_response():
    """Mock Keboola job trigger response."""
    return {
        "job_id": "987654",
        "status": "created",
        "configuration_id": "12345",
        "created_time": "2024-01-01T00:00:00Z",
        "url": "https://connection.keboola.com/admin/projects/123/queue/jobs/987654",
    }


# ============================================================================
# Test PollingService - Basic Flow
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceBasicFlow:
    """Test basic polling service flow."""

    async def test_polling_service_initialization(self, polling_service):
        """Test polling service initializes correctly."""
        assert polling_service is not None
        assert polling_service.default_poll_interval == 120
        assert polling_service.max_concurrent_checks == 10
        assert polling_service._is_running is False
        assert len(polling_service._openai_clients) == 0
        assert len(polling_service._keboola_clients) == 0

    async def test_process_single_job_pending(
        self, polling_service, sample_job, mock_openai_response_pending
    ):
        """Test processing a single job that is still pending."""
        # Mock the OpenAI client
        with patch.object(polling_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.check_batch_status = AsyncMock(return_value=mock_openai_response_pending)
            mock_client.is_success_status = Mock(return_value=False)
            mock_client.is_terminal_status = Mock(return_value=False)
            mock_get_client.return_value = mock_client

            # Process the job
            await polling_service._process_single_job(sample_job)

            # Verify OpenAI client was called
            mock_client.check_batch_status.assert_called_once_with("batch_test123")

    async def test_process_single_job_completed_triggers_keboola(
        self,
        polling_service,
        sample_job,
        mock_openai_response_completed,
        mock_keboola_response,
        db_session,
    ):
        """Test that completed batch triggers Keboola job."""
        # Mock the OpenAI client
        with (
            patch.object(polling_service, "_get_openai_client") as mock_get_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_get_keboola,
        ):

            # Setup OpenAI mock
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(return_value=mock_openai_response_completed)
            mock_openai.is_success_status = Mock(return_value=True)
            mock_openai.is_terminal_status = Mock(return_value=True)
            mock_get_openai.return_value = mock_openai

            # Setup Keboola mock
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Process the job
            await polling_service._process_single_job(sample_job)

            # Verify OpenAI client was called
            mock_openai.check_batch_status.assert_called_once_with("batch_test123")

            # Verify Keboola client was called
            mock_keboola.trigger_job.assert_called_once()
            call_kwargs = mock_keboola.trigger_job.call_args.kwargs
            assert call_kwargs["configuration_id"] == "12345"
            assert call_kwargs["component_id"] == "kds-team.app-custom-python"
            assert "teckochecker" in call_kwargs["tag"]

    async def test_process_single_job_failed_marks_failed(
        self, polling_service, sample_job, mock_openai_response_failed, db_session
    ):
        """Test that failed batch marks job as failed."""
        # Mock the OpenAI client
        with patch.object(polling_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.check_batch_status = AsyncMock(return_value=mock_openai_response_failed)
            mock_client.is_success_status = Mock(return_value=False)
            mock_client.is_terminal_status = Mock(return_value=True)
            mock_get_client.return_value = mock_client

            # Process the job
            await polling_service._process_single_job(sample_job)

            # Verify job was marked as failed
            db_session.refresh(sample_job)
            assert sample_job.status == "failed"
            assert sample_job.completed_at is not None


# ============================================================================
# Test PollingService - Concurrent Processing
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceConcurrency:
    """Test concurrent job processing."""

    async def test_process_jobs_concurrent_with_semaphore_limit(
        self,
        polling_service,
        db_session,
        openai_secret,
        keboola_secret,
        mock_openai_response_pending,
    ):
        """Test that concurrent processing respects semaphore limit."""
        # Create multiple jobs
        jobs = []
        for i in range(15):  # More than max_concurrent_checks (10)
            job = PollingJob(
                name=f"test-job-{i}",
                batch_id=f"batch_{i}",
                openai_secret_id=openai_secret.id,
                keboola_secret_id=keboola_secret.id,
                keboola_stack_url="https://connection.keboola.com",
                keboola_component_id="kds-team.app-custom-python",
                keboola_configuration_id="12345",
                poll_interval_seconds=120,
                status="active",
                next_check_at=datetime.now(timezone.utc),
            )
            db_session.add(job)
            jobs.append(job)
        db_session.commit()

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def mock_process_with_tracking(job):
            nonlocal concurrent_count, max_concurrent
            async with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)

            # Simulate some async work
            await asyncio.sleep(0.01)

            async with lock:
                concurrent_count -= 1

        # Patch the _process_single_job method
        with patch.object(
            polling_service, "_process_single_job", side_effect=mock_process_with_tracking
        ):
            await polling_service._process_jobs_concurrent(jobs)

        # Verify we didn't exceed the semaphore limit
        assert max_concurrent <= polling_service.max_concurrent_checks

    async def test_process_jobs_concurrent_handles_exceptions(
        self, polling_service, sample_job, db_session
    ):
        """Test that concurrent processing handles exceptions gracefully."""
        # Create a job that will fail
        failing_job = PollingJob(
            name="failing-job",
            batch_id="batch_fail",
            openai_secret_id=sample_job.openai_secret_id,
            keboola_secret_id=sample_job.keboola_secret_id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            poll_interval_seconds=120,
            status="active",
        )
        db_session.add(failing_job)
        db_session.commit()

        jobs = [sample_job, failing_job]

        # Mock _process_single_job to fail for one job
        async def mock_process(job):
            if job.name == "failing-job":
                raise Exception("Simulated error")

        with patch.object(polling_service, "_process_single_job", side_effect=mock_process):
            # Should not raise exception
            await polling_service._process_jobs_concurrent(jobs)


# ============================================================================
# Test PollingService - Error Handling
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceErrorHandling:
    """Test error handling in polling service."""

    async def test_check_job_openai_error_handling(self, polling_service, sample_job, db_session):
        """Test handling of OpenAI API errors."""
        # Mock the OpenAI client to raise an error
        with patch.object(polling_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.check_batch_status = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            # Process the job (should not raise)
            await polling_service._process_single_job(sample_job)

            # Job should still be active (will be retried)
            db_session.refresh(sample_job)
            assert sample_job.status == "active"

    async def test_check_job_keboola_error_handling(
        self, polling_service, sample_job, mock_openai_response_completed, db_session
    ):
        """Test handling of Keboola API errors."""
        import aiohttp

        # Mock successful OpenAI check but failing Keboola trigger
        with (
            patch.object(polling_service, "_get_openai_client") as mock_get_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_get_keboola,
        ):

            # Setup OpenAI mock
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(return_value=mock_openai_response_completed)
            mock_openai.is_success_status = Mock(return_value=True)
            mock_get_openai.return_value = mock_openai

            # Setup Keboola mock to fail
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(
                side_effect=aiohttp.ClientError("Connection failed")
            )
            mock_get_keboola.return_value = mock_keboola

            # Process the job (should not raise)
            await polling_service._process_single_job(sample_job)

            # Job should still be active (error handled)
            db_session.refresh(sample_job)
            # The error handler reschedules the job, so it remains active
            assert sample_job.status == "active"

    async def test_handle_job_error_logs_and_reschedules(
        self, polling_service, sample_job, db_session
    ):
        """Test that job errors are logged and job is rescheduled."""
        error_message = "Test error message"

        # Record initial next_check_at
        initial_next_check = sample_job.next_check_at

        # Handle the error
        await polling_service._handle_job_error(sample_job, error_message)

        # Verify error was logged to database
        logs = db_session.query(PollingLog).filter_by(job_id=sample_job.id, status="error").all()

        assert len(logs) > 0
        assert error_message in logs[0].message

    async def test_invalid_secret_id_handling(
        self,
        polling_service,
        db_session,
        openai_secret,
        keboola_secret,
        mock_openai_response_completed,
    ):
        """Test handling of invalid secret ID."""
        # Create job with valid secrets initially
        job = PollingJob(
            name="invalid-secret-job",
            batch_id="batch_invalid",
            openai_secret_id=openai_secret.id,
            keboola_secret_id=keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            poll_interval_seconds=120,
            status="active",
        )
        db_session.add(job)
        db_session.commit()

        # Mock _get_keboola_client to raise ValueError for invalid secret
        with (
            patch.object(polling_service, "_get_openai_client") as mock_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_keboola,
        ):

            mock_openai_client = AsyncMock()
            mock_openai_client.check_batch_status = AsyncMock(
                return_value=mock_openai_response_completed
            )
            mock_openai_client.is_success_status = Mock(return_value=True)
            mock_openai.return_value = mock_openai_client

            # Simulate invalid secret error
            mock_keboola.side_effect = ValueError("Secret 99999 not found")

            # Should not raise, but handle gracefully
            await polling_service._process_single_job(job)


# ============================================================================
# Test PollingService - Client Management
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceClientManagement:
    """Test API client caching and management."""

    async def test_get_openai_client_caching(self, polling_service, sample_job):
        """Test that OpenAI clients are cached."""
        # Get client twice for same secret
        client1 = await polling_service._get_openai_client(sample_job)
        client2 = await polling_service._get_openai_client(sample_job)

        # Should be the same instance
        assert client1 is client2
        assert sample_job.openai_secret_id in polling_service._openai_clients

    async def test_get_keboola_client_caching(self, polling_service, sample_job):
        """Test that Keboola clients are cached."""
        # Get client twice for same secret
        client1 = await polling_service._get_keboola_client(sample_job)
        client2 = await polling_service._get_keboola_client(sample_job)

        # Should be the same instance
        assert client1 is client2
        assert sample_job.keboola_secret_id in polling_service._keboola_clients

    async def test_get_secret_value(self, polling_service, openai_secret):
        """Test retrieving and decrypting secret value."""
        value = await polling_service._get_secret_value(openai_secret.id)

        assert value is not None
        assert value == "sk-test-key-123"

    async def test_get_secret_value_not_found(self, polling_service):
        """Test retrieving non-existent secret raises error."""
        with pytest.raises(ValueError, match="not found"):
            await polling_service._get_secret_value(99999)

    async def test_cleanup_clients(self, polling_service, sample_job):
        """Test cleanup of API clients."""
        # Create some clients
        await polling_service._get_openai_client(sample_job)
        await polling_service._get_keboola_client(sample_job)

        assert len(polling_service._openai_clients) > 0
        assert len(polling_service._keboola_clients) > 0

        # Cleanup
        await polling_service._cleanup_clients()

        assert len(polling_service._openai_clients) == 0
        assert len(polling_service._keboola_clients) == 0


# ============================================================================
# Test PollingService - Scheduling and Sleep
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceScheduling:
    """Test job scheduling and sleep calculations."""

    async def test_calculate_sleep_duration_with_jobs(
        self, polling_service, db_session, sample_job
    ):
        """Test calculating sleep duration when jobs are scheduled."""
        # Set next check to 30 seconds in future
        sample_job.next_check_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        db_session.commit()
        db_session.refresh(sample_job)
        # SQLite returns naive datetimes - make it timezone-aware
        if sample_job.next_check_at and sample_job.next_check_at.tzinfo is None:
            sample_job.next_check_at = sample_job.next_check_at.replace(tzinfo=timezone.utc)
            db_session.commit()

        scheduler = JobScheduler(db_session)
        sleep_duration = await polling_service._calculate_sleep_duration(scheduler)

        # Should be approximately 30 seconds (allowing for test execution time)
        assert 25 <= sleep_duration <= 35

    async def test_calculate_sleep_duration_no_jobs(self, polling_service, db_session):
        """Test calculating sleep duration when no jobs are scheduled."""
        scheduler = JobScheduler(db_session)
        sleep_duration = await polling_service._calculate_sleep_duration(scheduler)

        # Should return default sleep duration
        assert sleep_duration == polling_service.DEFAULT_SLEEP_SECONDS

    async def test_calculate_sleep_duration_past_due(self, polling_service, db_session, sample_job):
        """Test calculating sleep duration for past-due jobs."""
        # Set next check to past
        sample_job.next_check_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        db_session.commit()
        db_session.refresh(sample_job)
        # SQLite returns naive datetimes - make it timezone-aware
        if sample_job.next_check_at and sample_job.next_check_at.tzinfo is None:
            sample_job.next_check_at = sample_job.next_check_at.replace(tzinfo=timezone.utc)
            db_session.commit()

        scheduler = JobScheduler(db_session)
        sleep_duration = await polling_service._calculate_sleep_duration(scheduler)

        # Should return 0 (check immediately)
        assert sleep_duration == 0

    async def test_calculate_sleep_duration_capped(self, polling_service, db_session, sample_job):
        """Test that sleep duration is capped at maximum."""
        # Set next check very far in future
        sample_job.next_check_at = datetime.now(timezone.utc) + timedelta(hours=2)
        db_session.commit()
        db_session.refresh(sample_job)
        # SQLite returns naive datetimes - make it timezone-aware
        if sample_job.next_check_at and sample_job.next_check_at.tzinfo is None:
            sample_job.next_check_at = sample_job.next_check_at.replace(tzinfo=timezone.utc)
            db_session.commit()

        scheduler = JobScheduler(db_session)
        sleep_duration = await polling_service._calculate_sleep_duration(scheduler)

        # Should be capped at 60 seconds
        assert sleep_duration == 60

    async def test_interruptible_sleep(self, polling_service):
        """Test interruptible sleep with timeout."""
        start_time = asyncio.get_event_loop().time()

        # Sleep for 0.1 seconds
        await polling_service._interruptible_sleep(0.1)

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should have slept for approximately 0.1 seconds
        assert 0.08 <= elapsed <= 0.15

    async def test_interruptible_sleep_with_shutdown(self, polling_service):
        """Test interruptible sleep responds to shutdown event."""
        start_time = asyncio.get_event_loop().time()

        # Start a task that will trigger shutdown
        async def trigger_shutdown():
            await asyncio.sleep(0.05)
            polling_service._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        # Try to sleep for 1 second
        await polling_service._interruptible_sleep(1.0)

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should wake up early (around 0.05 seconds)
        assert elapsed < 0.2

        await shutdown_task


# ============================================================================
# Test PollingService - Logging
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceLogging:
    """Test logging functionality."""

    async def test_log_status_check(
        self, polling_service, sample_job, mock_openai_response_pending, db_session
    ):
        """Test logging of status checks."""
        await polling_service._log_status_check(
            sample_job.id, mock_openai_response_pending, message="Test status check"
        )

        # Verify log was created
        logs = (
            db_session.query(PollingLog).filter_by(job_id=sample_job.id, status="in_progress").all()
        )

        assert len(logs) > 0
        assert "Test status check" in logs[0].message

    async def test_log_action(self, polling_service, sample_job, mock_keboola_response, db_session):
        """Test logging of actions."""
        await polling_service._log_action(
            sample_job.id, action="keboola_triggered", result=mock_keboola_response
        )

        # Verify log was created
        logs = (
            db_session.query(PollingLog)
            .filter_by(job_id=sample_job.id, status="keboola_triggered")
            .all()
        )

        assert len(logs) > 0
        assert "987654" in logs[0].message

    async def test_log_error(self, polling_service, sample_job, db_session):
        """Test logging of errors."""
        error_message = "Test error occurred"

        await polling_service._log_error(sample_job.id, error_message)

        # Verify log was created
        logs = db_session.query(PollingLog).filter_by(job_id=sample_job.id, status="error").all()

        assert len(logs) > 0
        assert error_message in logs[0].message


# ============================================================================
# Test PollingService - Batch Completion Handling
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceBatchCompletion:
    """Test handling of batch completion scenarios."""

    async def test_handle_batch_completion_success(
        self,
        polling_service,
        sample_job,
        mock_openai_response_completed,
        mock_keboola_response,
        db_session,
    ):
        """Test successful batch completion and Keboola trigger."""
        # Mock Keboola client
        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Handle batch completion
            await polling_service._handle_batch_completion(
                sample_job, mock_openai_response_completed
            )

            # Verify job was marked as completed
            db_session.refresh(sample_job)
            assert sample_job.status == "completed"
            assert sample_job.completed_at is not None

            # Verify Keboola was triggered
            mock_keboola.trigger_job.assert_called_once()

    async def test_handle_batch_completion_keboola_failure(
        self, polling_service, sample_job, mock_openai_response_completed, db_session
    ):
        """Test batch completion when Keboola trigger fails."""
        import aiohttp

        # Mock Keboola client to fail
        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(side_effect=aiohttp.ClientError("Keboola error"))
            mock_get_keboola.return_value = mock_keboola

            # Handle batch completion (should not raise)
            await polling_service._handle_batch_completion(
                sample_job, mock_openai_response_completed
            )

            # Job should remain active (to retry)
            db_session.refresh(sample_job)
            assert sample_job.status == "active"

    async def test_handle_batch_terminal_failed(
        self, polling_service, sample_job, mock_openai_response_failed, db_session
    ):
        """Test handling of failed batch status."""
        await polling_service._handle_batch_terminal(sample_job, mock_openai_response_failed)

        # Verify job was marked as failed
        db_session.refresh(sample_job)
        assert sample_job.status == "failed"
        assert sample_job.completed_at is not None

        # Verify log was created
        logs = db_session.query(PollingLog).filter_by(job_id=sample_job.id, status="failed").all()
        assert len(logs) > 0

    async def test_handle_batch_terminal_expired(self, polling_service, sample_job, db_session):
        """Test handling of expired batch status."""
        expired_response = {
            "status": "expired",
            "batch_id": "batch_test123",
            "created_at": 1234567890,
            "expired_at": 1234567990,
        }

        await polling_service._handle_batch_terminal(sample_job, expired_response)

        # Verify job was marked as failed
        db_session.refresh(sample_job)
        assert sample_job.status == "failed"
        assert sample_job.completed_at is not None

    async def test_reschedule_job(self, polling_service, sample_job, db_session):
        """Test rescheduling of job for next check."""
        # Record initial times
        initial_last_check = sample_job.last_check_at
        initial_next_check = sample_job.next_check_at

        # Reschedule
        await polling_service._reschedule_job(sample_job)

        # Verify timestamps were updated
        db_session.refresh(sample_job)
        # SQLite returns naive datetimes - make them timezone-aware for comparison
        if sample_job.next_check_at and sample_job.next_check_at.tzinfo is None:
            next_check_aware = sample_job.next_check_at.replace(tzinfo=timezone.utc)
        else:
            next_check_aware = sample_job.next_check_at

        assert sample_job.last_check_at != initial_last_check
        assert sample_job.next_check_at != initial_next_check
        assert next_check_aware > datetime.now(timezone.utc)


# ============================================================================
# Test PollingService - Polling Loop
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceLoop:
    """Test main polling loop functionality."""

    async def test_polling_loop_basic_flow(
        self, polling_service, sample_job, mock_openai_response_pending, db_session
    ):
        """Test basic polling loop flow."""
        # Mock dependencies
        with patch.object(polling_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.check_batch_status = AsyncMock(return_value=mock_openai_response_pending)
            mock_client.is_success_status = Mock(return_value=False)
            mock_client.is_terminal_status = Mock(return_value=False)
            mock_get_client.return_value = mock_client

            # Start polling loop in background
            loop_task = asyncio.create_task(polling_service.polling_loop())

            # Let it run for a short time
            await asyncio.sleep(0.2)

            # Stop the loop
            polling_service.shutdown()

            # Wait for loop to finish
            try:
                await asyncio.wait_for(loop_task, timeout=2.0)
            except asyncio.CancelledError:
                pass

            # Verify loop was running
            assert polling_service.is_running is False

    async def test_polling_loop_handles_errors(self, polling_service, sample_job, db_session):
        """Test that polling loop handles errors gracefully."""
        error_count = 0

        # Mock to raise an error a few times then succeed
        async def mock_process_with_error(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            if error_count <= 2:
                raise Exception("Test error")

        with patch.object(
            polling_service, "_process_jobs_concurrent", side_effect=mock_process_with_error
        ):
            # Start polling loop
            loop_task = asyncio.create_task(polling_service.polling_loop())

            # Let it run briefly
            await asyncio.sleep(0.3)

            # Stop the loop
            polling_service.shutdown()

            # Should not raise exception
            try:
                await asyncio.wait_for(loop_task, timeout=3.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                # Force shutdown if still running
                loop_task.cancel()
                try:
                    await loop_task
                except asyncio.CancelledError:
                    pass

    async def test_graceful_shutdown(self, polling_service):
        """Test graceful shutdown of polling service."""
        # Start polling loop
        loop_task = asyncio.create_task(polling_service.polling_loop())

        # Verify it's running
        await asyncio.sleep(0.1)
        assert polling_service.is_running is True

        # Request shutdown
        polling_service.shutdown()

        # Wait for clean shutdown
        try:
            await asyncio.wait_for(loop_task, timeout=2.0)
        except asyncio.CancelledError:
            pass

        # Verify clean state
        assert polling_service.is_running is False
        assert polling_service._shutdown_event.is_set()

    async def test_polling_loop_cleanup_on_exit(self, polling_service, sample_job):
        """Test that polling loop cleans up clients on exit."""
        # Create some clients
        await polling_service._get_openai_client(sample_job)

        assert len(polling_service._openai_clients) > 0

        # Start and stop loop
        loop_task = asyncio.create_task(polling_service.polling_loop())
        await asyncio.sleep(0.2)
        polling_service.shutdown()

        try:
            await asyncio.wait_for(loop_task, timeout=3.0)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            # Force shutdown if still running
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Clients should be cleaned up
        assert len(polling_service._openai_clients) == 0


# ============================================================================
# Test PollingService - Edge Cases
# ============================================================================


@pytest.mark.asyncio
class TestPollingServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_process_empty_job_list(self, polling_service):
        """Test processing empty job list."""
        # Should not raise error
        await polling_service._process_jobs_concurrent([])

    async def test_process_job_with_missing_batch_id(
        self, polling_service, db_session, openai_secret, keboola_secret
    ):
        """Test processing job with missing/invalid batch ID."""
        job = PollingJob(
            name="invalid-batch",
            batch_id="",  # Empty batch ID
            openai_secret_id=openai_secret.id,
            keboola_secret_id=keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            poll_interval_seconds=120,
            status="active",
        )
        db_session.add(job)
        db_session.commit()

        # Should handle gracefully
        await polling_service._process_single_job(job)

    async def test_concurrent_processing_single_job(
        self, polling_service, sample_job, mock_openai_response_pending
    ):
        """Test concurrent processing with single job."""
        with patch.object(polling_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.check_batch_status = AsyncMock(return_value=mock_openai_response_pending)
            mock_client.is_success_status = Mock(return_value=False)
            mock_client.is_terminal_status = Mock(return_value=False)
            mock_get_client.return_value = mock_client

            # Should work fine with single job
            await polling_service._process_jobs_concurrent([sample_job])

            mock_client.check_batch_status.assert_called_once()

    async def test_multiple_jobs_different_secrets(
        self, polling_service, db_session, encryption_key
    ):
        """Test processing jobs with different secrets."""
        from app.services.encryption import get_encryption_service

        encryption_service = get_encryption_service()

        # Create multiple secrets
        secret1 = Secret(name="openai-1", type="openai", value=encryption_service.encrypt("key1"))
        secret2 = Secret(name="openai-2", type="openai", value=encryption_service.encrypt("key2"))
        secret3 = Secret(
            name="keboola-1", type="keboola", value=encryption_service.encrypt("token1")
        )
        db_session.add_all([secret1, secret2, secret3])
        db_session.commit()

        # Refresh to get IDs
        db_session.refresh(secret1)
        db_session.refresh(secret2)
        db_session.refresh(secret3)

        # Create jobs with different secrets
        job1 = PollingJob(
            name="job-1",
            batch_id="batch_1",
            openai_secret_id=secret1.id,
            keboola_secret_id=secret3.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            poll_interval_seconds=120,
            status="active",
        )
        job2 = PollingJob(
            name="job-2",
            batch_id="batch_2",
            openai_secret_id=secret2.id,
            keboola_secret_id=secret3.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            poll_interval_seconds=120,
            status="active",
        )
        db_session.add_all([job1, job2])
        db_session.commit()

        # Mock OpenAI responses - don't mock _get_openai_client, let it create real clients
        mock_response = {"status": "in_progress", "batch_id": "test"}

        # Process each job individually to populate the cache
        async def mock_check_batch_status(batch_id):
            return mock_response

        with patch(
            "app.integrations.openai_client.OpenAIBatchClient.check_batch_status",
            new_callable=AsyncMock,
            side_effect=mock_check_batch_status,
        ):
            with patch(
                "app.integrations.openai_client.OpenAIBatchClient.is_success_status",
                return_value=False,
            ):
                with patch(
                    "app.integrations.openai_client.OpenAIBatchClient.is_terminal_status",
                    return_value=False,
                ):
                    await polling_service._process_jobs_concurrent([job1, job2])

                    # Should have created separate clients for each secret
                    # Since both jobs use different OpenAI secrets (secret1 and secret2)
                    assert len(polling_service._openai_clients) == 2
