"""
Unit tests for multi-batch polling service refactored code.

Tests the new multi-batch architecture:
- _process_single_job: Handles multiple batches per job
- _check_single_batch: Updates individual batch status
- _trigger_keboola_with_results: Passes batch metadata as parameters

Test coverage targets 85%+ for polling.py lines 140-316.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, call

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Secret, PollingJob, JobBatch, PollingLog, Base
from app.services.polling import PollingService


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return "test-secret-key-for-multi-batch-tests"


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
    from app.services.encryption import init_encryption_service

    init_encryption_service(encryption_key)

    service = PollingService(
        db_session_factory=db_session_factory,
        default_poll_interval=120,
        max_concurrent_checks=10
    )
    return service


@pytest.fixture
def openai_secret(db_session, encryption_key):
    """Create a test OpenAI secret."""
    from app.services.encryption import init_encryption_service, get_encryption_service

    init_encryption_service(encryption_key)
    encryption_service = get_encryption_service()

    secret = Secret(
        name="test-openai",
        type="openai",
        value=encryption_service.encrypt("sk-test-key-123")
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
        name="test-keboola",
        type="keboola",
        value=encryption_service.encrypt("keboola-token-123")
    )
    db_session.add(secret)
    db_session.commit()
    db_session.refresh(secret)
    return secret


@pytest.fixture
def multi_batch_job(db_session, openai_secret, keboola_secret):
    """Create a polling job with multiple batches."""
    job = PollingJob(
        name="test-multi-batch-job",
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

    # Add three batches
    batch1 = JobBatch(
        job_id=job.id,
        batch_id="batch_abc123",
        status="in_progress"
    )
    batch2 = JobBatch(
        job_id=job.id,
        batch_id="batch_def456",
        status="in_progress"
    )
    batch3 = JobBatch(
        job_id=job.id,
        batch_id="batch_ghi789",
        status="in_progress"
    )
    db_session.add_all([batch1, batch2, batch3])
    db_session.commit()

    # Refresh to load relationships
    db_session.refresh(job)
    return job


@pytest.fixture
def single_batch_job(db_session, openai_secret, keboola_secret):
    """Create a polling job with a single batch."""
    job = PollingJob(
        name="test-single-batch-job",
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

    # Add single batch
    batch = JobBatch(
        job_id=job.id,
        batch_id="batch_single123",
        status="in_progress"
    )
    db_session.add(batch)
    db_session.commit()

    db_session.refresh(job)
    return job


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
# Test Class 1: TestProcessSingleJob
# ============================================================================


@pytest.mark.asyncio
class TestProcessSingleJob:
    """Test _process_single_job with multi-batch architecture."""

    async def test_process_job_all_batches_completed(
        self,
        polling_service,
        multi_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test processing when all batches are completed - should trigger Keboola."""
        job_id = multi_batch_job.id

        # Mock all batches as completed
        async def mock_check_status(batch_id):
            return {"status": "completed", "batch_id": batch_id}

        # Mock OpenAI and Keboola clients
        with (
            patch.object(polling_service, "_get_openai_client") as mock_get_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_get_keboola,
        ):
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Process the job
            await polling_service._process_single_job(multi_batch_job)

            # Verify OpenAI was called for each batch
            assert mock_openai.check_batch_status.call_count == 3

            # Verify Keboola was triggered
            mock_keboola.trigger_job.assert_called_once()

            # Verify job status was updated
            db_session.refresh(multi_batch_job)
            assert multi_batch_job.status == "completed"
            assert multi_batch_job.completed_at is not None

            # Verify all batches marked as completed
            for batch in multi_batch_job.batches:
                db_session.refresh(batch)
                assert batch.status == "completed"
                assert batch.completed_at is not None

    async def test_process_job_partial_completion(
        self,
        polling_service,
        multi_batch_job,
        db_session
    ):
        """Test processing when some batches still in_progress - should reschedule."""
        # Mock mixed statuses
        async def mock_check_status(batch_id):
            if batch_id == "batch_abc123":
                return {"status": "completed", "batch_id": batch_id}
            elif batch_id == "batch_def456":
                return {"status": "in_progress", "batch_id": batch_id}
            else:
                return {"status": "finalizing", "batch_id": batch_id}

        with patch.object(polling_service, "_get_openai_client") as mock_get_openai:
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            # Mock reschedule
            with patch.object(polling_service, "_reschedule_job") as mock_reschedule:
                # Process the job
                await polling_service._process_single_job(multi_batch_job)

                # Verify OpenAI was called for each batch
                assert mock_openai.check_batch_status.call_count == 3

                # Verify job was rescheduled (not completed)
                mock_reschedule.assert_called_once()

                # Verify job status is still active
                db_session.refresh(multi_batch_job)
                assert multi_batch_job.status == "active"
                assert multi_batch_job.completed_at is None

    async def test_process_job_with_failures(
        self,
        polling_service,
        multi_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test processing with mixed completed/failed batches - should trigger anyway."""
        # Mock mixed statuses including failures
        async def mock_check_status(batch_id):
            if batch_id == "batch_abc123":
                return {"status": "completed", "batch_id": batch_id}
            elif batch_id == "batch_def456":
                return {"status": "failed", "batch_id": batch_id}
            else:
                return {"status": "cancelled", "batch_id": batch_id}

        with (
            patch.object(polling_service, "_get_openai_client") as mock_get_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_get_keboola,
        ):
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Process the job
            await polling_service._process_single_job(multi_batch_job)

            # Verify Keboola was triggered even with failures
            mock_keboola.trigger_job.assert_called_once()

            # Check the parameters passed to Keboola
            call_kwargs = mock_keboola.trigger_job.call_args.kwargs
            assert "parameters" in call_kwargs

            params = call_kwargs["parameters"]
            assert params["batch_count_completed"] == 1
            assert params["batch_count_failed"] == 2
            assert "batch_abc123" in params["batch_ids_completed"]
            assert "batch_def456" in params["batch_ids_failed"]
            assert "batch_ghi789" in params["batch_ids_failed"]

            # Verify job marked as completed_with_failures
            db_session.refresh(multi_batch_job)
            assert multi_batch_job.status == "completed_with_failures"
            assert multi_batch_job.completed_at is not None

    async def test_process_job_empty_batches(
        self,
        polling_service,
        db_session,
        openai_secret,
        keboola_secret
    ):
        """Test edge case: job with no batches - should handle gracefully."""
        # Create job without batches
        job = PollingJob(
            name="empty-batch-job",
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
        db_session.refresh(job)

        # Should not raise error
        await polling_service._process_single_job(job)

        # Job should remain active
        db_session.refresh(job)
        assert job.status == "active"

    async def test_process_job_all_already_terminal(
        self,
        polling_service,
        multi_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test processing when all batches already terminal - should trigger Keboola."""
        # Update all batches to terminal status
        for batch in multi_batch_job.batches:
            batch.status = "completed"
            batch.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(multi_batch_job)

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Process the job
            await polling_service._process_single_job(multi_batch_job)

            # Should trigger Keboola even though no checks were needed
            mock_keboola.trigger_job.assert_called_once()


# ============================================================================
# Test Class 2: TestCheckSingleBatch
# ============================================================================


@pytest.mark.asyncio
class TestCheckSingleBatch:
    """Test _check_single_batch for individual batch status updates."""

    async def test_check_single_batch_status_update(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test status changed - should update database."""
        batch = single_batch_job.batches[0]
        assert batch.status == "in_progress"

        # Mock OpenAI response with new status
        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            return_value={"status": "finalizing", "batch_id": batch.batch_id}
        )

        # Check the batch
        await polling_service._check_single_batch(mock_openai, batch)

        # Verify status was updated
        db_session.refresh(batch)
        assert batch.status == "finalizing"

    async def test_check_single_batch_no_change(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test status unchanged - should skip update."""
        batch = single_batch_job.batches[0]
        original_status = batch.status

        # Mock OpenAI response with same status
        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            return_value={"status": "in_progress", "batch_id": batch.batch_id}
        )

        # Check the batch
        await polling_service._check_single_batch(mock_openai, batch)

        # Status should remain unchanged
        db_session.refresh(batch)
        assert batch.status == original_status
        assert batch.completed_at is None

    async def test_check_single_batch_terminal(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test terminal status - should set completed_at timestamp."""
        batch = single_batch_job.batches[0]

        # Mock OpenAI response with terminal status
        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            return_value={"status": "completed", "batch_id": batch.batch_id}
        )

        # Check the batch
        await polling_service._check_single_batch(mock_openai, batch)

        # Verify status and timestamp
        db_session.refresh(batch)
        assert batch.status == "completed"
        assert batch.completed_at is not None
        assert batch.is_terminal is True

    async def test_check_single_batch_failed_terminal(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test failed terminal status - should set completed_at."""
        batch = single_batch_job.batches[0]

        # Mock OpenAI response with failed status
        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            return_value={"status": "failed", "batch_id": batch.batch_id}
        )

        # Check the batch
        await polling_service._check_single_batch(mock_openai, batch)

        # Verify terminal status
        db_session.refresh(batch)
        assert batch.status == "failed"
        assert batch.completed_at is not None
        assert batch.is_terminal is True
        assert batch.is_failed is True

    async def test_check_single_batch_error(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test OpenAI error handling - should not crash."""
        batch = single_batch_job.batches[0]
        original_status = batch.status

        # Mock OpenAI to raise error
        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            side_effect=Exception("API Error")
        )

        # Should not raise error
        await polling_service._check_single_batch(mock_openai, batch)

        # Batch status should remain unchanged
        db_session.refresh(batch)
        assert batch.status == original_status

    async def test_check_single_batch_cancelled(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test cancelled status - should be treated as terminal."""
        batch = single_batch_job.batches[0]

        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            return_value={"status": "cancelled", "batch_id": batch.batch_id}
        )

        await polling_service._check_single_batch(mock_openai, batch)

        db_session.refresh(batch)
        assert batch.status == "cancelled"
        assert batch.is_terminal is True
        assert batch.is_failed is True
        assert batch.completed_at is not None

    async def test_check_single_batch_expired(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test expired status - should be treated as terminal."""
        batch = single_batch_job.batches[0]

        mock_openai = AsyncMock()
        mock_openai.check_batch_status = AsyncMock(
            return_value={"status": "expired", "batch_id": batch.batch_id}
        )

        await polling_service._check_single_batch(mock_openai, batch)

        db_session.refresh(batch)
        assert batch.status == "expired"
        assert batch.is_terminal is True
        assert batch.is_failed is True
        assert batch.completed_at is not None


# ============================================================================
# Test Class 3: TestTriggerKeboolaWithResults
# ============================================================================


@pytest.mark.asyncio
class TestTriggerKeboolaWithResults:
    """Test _trigger_keboola_with_results with batch metadata."""

    async def test_trigger_keboola_all_completed(
        self,
        polling_service,
        multi_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test triggering Keboola with all successful batches."""
        # Mark all batches as completed
        for batch in multi_batch_job.batches:
            batch.status = "completed"
            batch.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(multi_batch_job)

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Trigger Keboola
            await polling_service._trigger_keboola_with_results(multi_batch_job)

            # Verify trigger was called
            mock_keboola.trigger_job.assert_called_once()

            # Verify parameters
            call_kwargs = mock_keboola.trigger_job.call_args.kwargs
            params = call_kwargs["parameters"]

            assert params["batch_count_total"] == 3
            assert params["batch_count_completed"] == 3
            assert params["batch_count_failed"] == 0
            assert len(params["batch_ids_completed"]) == 3
            assert len(params["batch_ids_failed"]) == 0
            assert "batch_abc123" in params["batch_ids_completed"]
            assert "batch_def456" in params["batch_ids_completed"]
            assert "batch_ghi789" in params["batch_ids_completed"]

    async def test_trigger_keboola_with_failures(
        self,
        polling_service,
        multi_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test triggering Keboola with mixed success/failure batches."""
        # Mark batches with mixed statuses
        multi_batch_job.batches[0].status = "completed"
        multi_batch_job.batches[0].completed_at = datetime.now(timezone.utc)
        multi_batch_job.batches[1].status = "failed"
        multi_batch_job.batches[1].completed_at = datetime.now(timezone.utc)
        multi_batch_job.batches[2].status = "expired"
        multi_batch_job.batches[2].completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(multi_batch_job)

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Trigger Keboola
            await polling_service._trigger_keboola_with_results(multi_batch_job)

            # Verify parameters
            call_kwargs = mock_keboola.trigger_job.call_args.kwargs
            params = call_kwargs["parameters"]

            assert params["batch_count_total"] == 3
            assert params["batch_count_completed"] == 1
            assert params["batch_count_failed"] == 2
            assert len(params["batch_ids_completed"]) == 1
            assert len(params["batch_ids_failed"]) == 2
            assert "batch_abc123" in params["batch_ids_completed"]
            assert "batch_def456" in params["batch_ids_failed"]
            assert "batch_ghi789" in params["batch_ids_failed"]

    async def test_trigger_keboola_parameters_format(
        self,
        polling_service,
        single_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test that parameters are passed in correct format to Keboola."""
        # Mark batch as completed
        batch = single_batch_job.batches[0]
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(single_batch_job)

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Trigger Keboola
            await polling_service._trigger_keboola_with_results(single_batch_job)

            # Verify call structure
            call_kwargs = mock_keboola.trigger_job.call_args.kwargs

            assert "configuration_id" in call_kwargs
            assert "component_id" in call_kwargs
            assert "tag" in call_kwargs
            assert "parameters" in call_kwargs

            assert call_kwargs["configuration_id"] == "12345"
            assert call_kwargs["component_id"] == "kds-team.app-custom-python"
            assert "teckochecker" in call_kwargs["tag"]

            params = call_kwargs["parameters"]
            assert isinstance(params, dict)
            assert "batch_ids_completed" in params
            assert "batch_ids_failed" in params
            assert "batch_count_total" in params
            assert "batch_count_completed" in params
            assert "batch_count_failed" in params

    async def test_trigger_keboola_error(
        self,
        polling_service,
        single_batch_job,
        db_session
    ):
        """Test Keboola trigger failure handling."""
        # Mark batch as completed
        batch = single_batch_job.batches[0]
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(single_batch_job)

        import aiohttp

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(
                side_effect=aiohttp.ClientError("Keboola API Error")
            )
            mock_get_keboola.return_value = mock_keboola

            # Should not raise - error handled internally
            await polling_service._trigger_keboola_with_results(single_batch_job)

            # Job should be marked as failed
            db_session.refresh(single_batch_job)
            assert single_batch_job.status == "failed"
            assert single_batch_job.completed_at is not None

            # Error should be logged
            logs = db_session.query(PollingLog).filter_by(
                job_id=single_batch_job.id,
                status="error"
            ).all()
            assert len(logs) > 0

    async def test_trigger_keboola_logs_action(
        self,
        polling_service,
        single_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test that successful trigger logs action to database."""
        # Mark batch as completed
        batch = single_batch_job.batches[0]
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(single_batch_job)

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Trigger Keboola
            await polling_service._trigger_keboola_with_results(single_batch_job)

            # Verify action was logged
            logs = db_session.query(PollingLog).filter_by(
                job_id=single_batch_job.id,
                status="keboola_triggered"
            ).all()
            assert len(logs) > 0
            assert "987654" in logs[0].message

    async def test_trigger_keboola_zero_batches(
        self,
        polling_service,
        db_session,
        openai_secret,
        keboola_secret,
        mock_keboola_response
    ):
        """Test triggering with job that has zero batches (edge case)."""
        # Create job without batches
        job = PollingJob(
            name="zero-batch-job",
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
        db_session.refresh(job)

        with patch.object(polling_service, "_get_keboola_client") as mock_get_keboola:
            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Should handle gracefully
            await polling_service._trigger_keboola_with_results(job)

            # Parameters should reflect zero batches
            call_kwargs = mock_keboola.trigger_job.call_args.kwargs
            params = call_kwargs["parameters"]

            assert params["batch_count_total"] == 0
            assert params["batch_count_completed"] == 0
            assert params["batch_count_failed"] == 0
            assert params["batch_ids_completed"] == []
            assert params["batch_ids_failed"] == []


# ============================================================================
# Test Class 4: Integration and Edge Cases
# ============================================================================


@pytest.mark.asyncio
class TestMultiBatchIntegration:
    """Integration tests for multi-batch workflow."""

    async def test_full_workflow_all_complete(
        self,
        polling_service,
        multi_batch_job,
        mock_keboola_response,
        db_session
    ):
        """Test complete workflow: check batches -> all complete -> trigger."""
        # Mock OpenAI to return completed for all
        async def mock_check_status(batch_id):
            return {"status": "completed", "batch_id": batch_id}

        with (
            patch.object(polling_service, "_get_openai_client") as mock_get_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_get_keboola,
        ):
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value=mock_keboola_response)
            mock_get_keboola.return_value = mock_keboola

            # Process job
            await polling_service._process_single_job(multi_batch_job)

            # Verify complete workflow
            assert mock_openai.check_batch_status.call_count == 3
            mock_keboola.trigger_job.assert_called_once()

            db_session.refresh(multi_batch_job)
            assert multi_batch_job.status == "completed"

            # All batches should be completed
            for batch in multi_batch_job.batches:
                db_session.refresh(batch)
                assert batch.status == "completed"
                assert batch.is_terminal

    async def test_full_workflow_partial_progress(
        self,
        polling_service,
        multi_batch_job,
        db_session
    ):
        """Test workflow with partial progress - should reschedule."""
        call_count = [0]

        async def mock_check_status(batch_id):
            # First batch completes, others still in progress
            if batch_id == "batch_abc123":
                return {"status": "completed", "batch_id": batch_id}
            return {"status": "in_progress", "batch_id": batch_id}

        with patch.object(polling_service, "_get_openai_client") as mock_get_openai:
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            with patch.object(polling_service, "_reschedule_job") as mock_reschedule:
                # Process job
                await polling_service._process_single_job(multi_batch_job)

                # Should check all batches
                assert mock_openai.check_batch_status.call_count == 3

                # Should reschedule, not complete
                mock_reschedule.assert_called_once()

                db_session.refresh(multi_batch_job)
                assert multi_batch_job.status == "active"
                assert multi_batch_job.completed_at is None

    async def test_batch_completion_summary(
        self,
        multi_batch_job,
        db_session
    ):
        """Test batch_completion_summary property with various statuses."""
        # Set various statuses
        multi_batch_job.batches[0].status = "completed"
        multi_batch_job.batches[1].status = "failed"
        multi_batch_job.batches[2].status = "in_progress"
        db_session.commit()
        db_session.refresh(multi_batch_job)

        summary = multi_batch_job.batch_completion_summary

        assert summary["total"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["in_progress"] == 1

    async def test_concurrent_batch_checks(
        self,
        polling_service,
        multi_batch_job,
        db_session
    ):
        """Test that batch checks happen concurrently."""
        check_times = []

        async def mock_check_status(batch_id):
            check_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Simulate API call
            return {"status": "in_progress", "batch_id": batch_id}

        with patch.object(polling_service, "_get_openai_client") as mock_get_openai:
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            with patch.object(polling_service, "_reschedule_job"):
                start_time = asyncio.get_event_loop().time()

                # Process job
                await polling_service._process_single_job(multi_batch_job)

                elapsed = asyncio.get_event_loop().time() - start_time

                # Should complete in ~0.1s (concurrent) not ~0.3s (sequential)
                assert elapsed < 0.25, "Batch checks should be concurrent"
                assert len(check_times) == 3

    async def test_error_in_one_batch_does_not_affect_others(
        self,
        polling_service,
        multi_batch_job,
        db_session
    ):
        """Test that error in one batch check doesn't stop others."""
        async def mock_check_status(batch_id):
            if batch_id == "batch_def456":
                raise Exception("API Error for this batch")
            return {"status": "completed", "batch_id": batch_id}

        with patch.object(polling_service, "_get_openai_client") as mock_get_openai:
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            with patch.object(polling_service, "_reschedule_job"):
                # Should not raise
                await polling_service._process_single_job(multi_batch_job)

                # Two batches should have been updated
                db_session.refresh(multi_batch_job)
                completed_count = sum(
                    1 for b in multi_batch_job.batches if b.status == "completed"
                )
                assert completed_count == 2

    async def test_all_batches_terminal_property(self, multi_batch_job, db_session):
        """Test all_batches_terminal property logic."""
        # Initially all in_progress
        assert not multi_batch_job.all_batches_terminal

        # Mark all as terminal
        for batch in multi_batch_job.batches:
            batch.status = "completed"
        db_session.commit()
        db_session.refresh(multi_batch_job)

        assert multi_batch_job.all_batches_terminal

        # Mark one as non-terminal
        multi_batch_job.batches[0].status = "in_progress"
        db_session.commit()
        db_session.refresh(multi_batch_job)

        assert not multi_batch_job.all_batches_terminal

    async def test_logging_during_batch_processing(
        self,
        polling_service,
        multi_batch_job,
        db_session
    ):
        """Test that status checks are logged correctly."""
        async def mock_check_status(batch_id):
            return {"status": "completed", "batch_id": batch_id}

        with (
            patch.object(polling_service, "_get_openai_client") as mock_get_openai,
            patch.object(polling_service, "_get_keboola_client") as mock_get_keboola,
        ):
            mock_openai = AsyncMock()
            mock_openai.check_batch_status = AsyncMock(side_effect=mock_check_status)
            mock_get_openai.return_value = mock_openai

            mock_keboola = AsyncMock()
            mock_keboola.trigger_job = AsyncMock(return_value={"job_id": "123"})
            mock_get_keboola.return_value = mock_keboola

            # Process job
            await polling_service._process_single_job(multi_batch_job)

            # Check that logs were created
            logs = db_session.query(PollingLog).filter_by(
                job_id=multi_batch_job.id
            ).all()

            assert len(logs) > 0

            # Should have checking status log
            checking_logs = [log for log in logs if "completed" in log.message.lower()]
            assert len(checking_logs) > 0
