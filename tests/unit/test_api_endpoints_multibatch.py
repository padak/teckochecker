"""
Unit tests for API endpoints with multi-batch support.

This module tests:
- Health and stats endpoints
- Secret CRUD operations via API
- Job CRUD operations with multi-batch support (NEW)
- Job pause/resume functionality
- Error handling (404, 409, 422, 500)
- Response schema validation for batches array and computed counts
- Cascade delete for JobBatch records
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models import Secret, PollingJob, PollingLog, JobBatch
from app.services.encryption import init_encryption_service


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return "test-secret-key-for-testing-purposes"


@pytest.fixture(scope="function")
def db_session(encryption_key):
    """Create an in-memory SQLite database session for testing."""
    # Initialize encryption service first
    init_encryption_service(encryption_key)

    # Create in-memory SQLite database with static pool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Use static pool for in-memory DB
        echo=False,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(db_session):
    """Create a FastAPI test client with dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_openai_secret(db_session, encryption_key):
    """Create a sample OpenAI secret in the database."""
    from app.services.encryption import get_encryption_service

    encryption_service = get_encryption_service()

    secret = Secret(
        name="test-openai-key", type="openai", value=encryption_service.encrypt("sk-test-key-12345")
    )
    db_session.add(secret)
    db_session.commit()
    db_session.refresh(secret)
    return secret


@pytest.fixture
def sample_keboola_secret(db_session, encryption_key):
    """Create a sample Keboola secret in the database."""
    from app.services.encryption import get_encryption_service

    encryption_service = get_encryption_service()

    secret = Secret(
        name="test-keboola-token",
        type="keboola",
        value=encryption_service.encrypt("kbc-token-12345"),
    )
    db_session.add(secret)
    db_session.commit()
    db_session.refresh(secret)
    return secret


@pytest.fixture
def sample_job(db_session, sample_openai_secret, sample_keboola_secret):
    """Create a sample polling job with multiple batches in the database."""
    job = PollingJob(
        name="Test Job",
        openai_secret_id=sample_openai_secret.id,
        keboola_secret_id=sample_keboola_secret.id,
        keboola_stack_url="https://connection.keboola.com",
        keboola_component_id="kds-team.app-custom-python",
        keboola_configuration_id="12345",
        poll_interval_seconds=120,
        status="active",
        next_check_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Add batches to the job
    batch1 = JobBatch(job_id=job.id, batch_id="batch_abc123", status="in_progress")
    batch2 = JobBatch(job_id=job.id, batch_id="batch_def456", status="completed")
    db_session.add_all([batch1, batch2])
    db_session.commit()
    db_session.refresh(job)

    return job


# ============================================================================
# Job Management Endpoints Tests - Multi-Batch Support
# ============================================================================


class TestJobsCreateEndpoint:
    """Test cases for creating jobs with multi-batch support."""

    def test_create_job_single_batch(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating a new polling job with single batch_id."""
        job_data = {
            "name": "My Test Job",
            "batch_ids": ["batch_xyz789"],  # Single batch
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "kds-team.app-custom-python",
            "keboola_configuration_id": "54321",
            "poll_interval_seconds": 180,
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == job_data["name"]
        assert data["status"] == "active"
        assert data["poll_interval_seconds"] == 180
        assert "id" in data
        assert "created_at" in data
        assert "next_check_at" in data

        # Verify new multi-batch fields
        assert "batches" in data
        assert isinstance(data["batches"], list)
        assert len(data["batches"]) == 1
        assert data["batches"][0]["batch_id"] == "batch_xyz789"
        assert data["batch_count"] == 1
        assert data["completed_count"] == 0
        assert data["failed_count"] == 0

    def test_create_job_multiple_batches(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating a job with 3 batch_ids."""
        job_data = {
            "name": "Multi-Batch Job",
            "batch_ids": ["batch_001", "batch_002", "batch_003"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "kds-team.app-custom-python",
            "keboola_configuration_id": "54321",
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 201
        data = response.json()
        assert len(data["batches"]) == 3
        assert data["batch_count"] == 3

        # Verify all batches are created
        batch_ids = [b["batch_id"] for b in data["batches"]]
        assert "batch_001" in batch_ids
        assert "batch_002" in batch_ids
        assert "batch_003" in batch_ids

        # All should be in_progress initially
        for batch in data["batches"]:
            assert batch["status"] == "in_progress"

    def test_create_job_max_batches(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with 10 batch_ids (maximum allowed)."""
        batch_ids = [f"batch_{i:03d}" for i in range(10)]
        job_data = {
            "name": "Max Batches Job",
            "batch_ids": batch_ids,
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 201
        data = response.json()
        assert data["batch_count"] == 10
        assert len(data["batches"]) == 10

    def test_create_job_duplicate_batches(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with duplicate batch_ids returns 422 error."""
        job_data = {
            "name": "Duplicate Batches Job",
            "batch_ids": ["batch_001", "batch_002", "batch_001"],  # Duplicate
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"
        assert any("duplicate" in str(detail).lower() for detail in data["details"])

    def test_create_job_invalid_format(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with invalid batch_id format returns 422 error."""
        job_data = {
            "name": "Invalid Format Job",
            "batch_ids": ["invalid_id_no_prefix"],  # Missing 'batch_' prefix
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"
        assert any("batch_" in str(detail).lower() for detail in data["details"])

    def test_create_job_missing_secret(self, client, sample_keboola_secret):
        """Test creating job with non-existent OpenAI secret returns 404."""
        job_data = {
            "name": "Missing Secret Job",
            "batch_ids": ["batch_test"],
            "openai_secret_id": 99999,  # Non-existent
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 404
        data = response.json()
        assert "OpenAI secret" in data["detail"]
        assert response.headers.get("X-Error-Code") == "1001"


class TestJobsListEndpoint:
    """Test cases for listing jobs with multi-batch support."""

    def test_list_jobs_returns_batches_array(self, client, sample_job):
        """Test listing jobs includes batches array in response."""
        response = client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["jobs"]) == 1

        job = data["jobs"][0]
        assert "batches" in job
        assert isinstance(job["batches"], list)
        assert len(job["batches"]) == 2  # sample_job has 2 batches

    def test_list_jobs_computed_counts(self, client, sample_job):
        """Test listing jobs returns correct computed counts."""
        response = client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()

        job = data["jobs"][0]
        assert job["batch_count"] == 2
        assert job["completed_count"] == 1  # batch_def456 is completed
        assert job["failed_count"] == 0

    def test_list_jobs_status_filter(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test filtering jobs by status still works with multi-batch."""
        # Create paused job
        paused_job = PollingJob(
            name="Paused Job",
            openai_secret_id=sample_openai_secret.id,
            keboola_secret_id=sample_keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="test-component",
            keboola_configuration_id="12345",
            status="paused",
        )
        db_session.add(paused_job)
        db_session.commit()

        # Add batch to paused job
        batch = JobBatch(job_id=paused_job.id, batch_id="batch_paused", status="in_progress")
        db_session.add(batch)
        db_session.commit()

        # Filter for paused jobs only
        response = client.get("/api/jobs?status=paused")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["jobs"][0]["status"] == "paused"
        assert len(data["jobs"][0]["batches"]) == 1


class TestJobsGetEndpoint:
    """Test cases for retrieving single job details with multi-batch support."""

    def test_get_job_by_id(self, client, sample_job):
        """Test retrieving a specific job by ID returns batches array."""
        response = client.get(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_job.id
        assert data["name"] == sample_job.name
        assert "batches" in data
        assert len(data["batches"]) == 2
        assert "logs" in data

    def test_get_job_computed_counts(self, client, sample_job):
        """Test get job returns correct computed counts."""
        response = client.get(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_count"] == 2
        assert data["completed_count"] == 1
        assert data["failed_count"] == 0

    def test_get_job_not_found(self, client):
        """Test retrieving non-existent job returns 404."""
        response = client.get("/api/jobs/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert response.headers.get("X-Error-Code") == "1002"

    def test_get_job_with_logs(self, client, db_session, sample_job):
        """Test retrieving job with logs parameter includes logs."""
        # Create some log entries
        log1 = PollingLog(job_id=sample_job.id, status="checking", message="Checking batch status")
        log2 = PollingLog(job_id=sample_job.id, status="pending", message="Batch still in progress")
        db_session.add_all([log1, log2])
        db_session.commit()

        response = client.get(f"/api/jobs/{sample_job.id}?include_logs=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 2


class TestJobsUpdateEndpoint:
    """Test cases for updating jobs with multi-batch support."""

    def test_update_job_fields(self, client, sample_job):
        """Test updating job name and intervals (no batch changes allowed)."""
        update_data = {"name": "Updated Job Name", "poll_interval_seconds": 300}

        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["poll_interval_seconds"] == update_data["poll_interval_seconds"]

        # Verify batches remain unchanged
        assert len(data["batches"]) == 2

    def test_update_job_returns_new_format(self, client, sample_job):
        """Test update response includes batches array and computed counts."""
        update_data = {"name": "New Name"}

        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert "batches" in data
        assert "batch_count" in data
        assert "completed_count" in data
        assert "failed_count" in data


class TestJobsPauseResumeEndpoints:
    """Test cases for job pause and resume with multi-batch support."""

    def test_pause_job(self, client, sample_job):
        """Test pausing an active job."""
        assert sample_job.status == "active"

        response = client.post(f"/api/jobs/{sample_job.id}/pause")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    def test_resume_job(self, client, db_session, sample_job):
        """Test resuming a paused job."""
        # Pause the job first
        sample_job.status = "paused"
        db_session.commit()

        response = client.post(f"/api/jobs/{sample_job.id}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["next_check_at"] is not None

    def test_pause_resume_return_new_format(self, client, db_session, sample_job):
        """Test both pause and resume return batches array."""
        # Pause
        pause_response = client.post(f"/api/jobs/{sample_job.id}/pause")
        assert pause_response.status_code == 200
        pause_data = pause_response.json()
        assert "batches" in pause_data
        assert len(pause_data["batches"]) == 2

        # Resume
        resume_response = client.post(f"/api/jobs/{sample_job.id}/resume")
        assert resume_response.status_code == 200
        resume_data = resume_response.json()
        assert "batches" in resume_data
        assert len(resume_data["batches"]) == 2

    def test_pause_non_active_job(self, client, db_session, sample_job):
        """Test pausing non-active job returns 409 error."""
        sample_job.status = "completed"
        db_session.commit()

        response = client.post(f"/api/jobs/{sample_job.id}/pause")

        assert response.status_code == 409
        data = response.json()
        assert "Cannot pause" in data["detail"]


class TestJobsDeleteEndpoint:
    """Test cases for deleting jobs with cascade delete of batches."""

    def test_delete_job(self, client, sample_job):
        """Test deleting a job successfully."""
        response = client.delete(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        # Verify job is deleted
        get_response = client.get(f"/api/jobs/{sample_job.id}")
        assert get_response.status_code == 404

    def test_delete_cascades_batches(self, client, db_session, sample_job):
        """Test deleting job also deletes associated JobBatch records."""
        job_id = sample_job.id

        # Verify batches exist
        batches_before = db_session.query(JobBatch).filter(JobBatch.job_id == job_id).count()
        assert batches_before == 2

        # Delete job
        response = client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 200

        # Verify batches are deleted (CASCADE)
        batches_after = db_session.query(JobBatch).filter(JobBatch.job_id == job_id).count()
        assert batches_after == 0


class TestBatchValidationScenarios:
    """Test validation scenarios for batch_ids."""

    def test_batch_id_too_long(self, client, sample_openai_secret, sample_keboola_secret):
        """Test batch_id exceeding 255 character limit."""
        job_data = {
            "name": "Long Batch ID Job",
            "batch_ids": ["batch_" + "x" * 300],  # Over 255 chars
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 422

    def test_batch_id_with_special_characters(
        self, client, sample_openai_secret, sample_keboola_secret
    ):
        """Test batch_id with special characters fails validation."""
        special_chars = ["batch_test$", "batch_test#", "batch_test@", "batch_test%"]

        for batch_id in special_chars:
            job_data = {
                "name": f"Special Char Job {batch_id}",
                "batch_ids": [batch_id],
                "openai_secret_id": sample_openai_secret.id,
                "keboola_secret_id": sample_keboola_secret.id,
                "keboola_stack_url": "https://connection.keboola.com",
                "keboola_component_id": "test-component",
                "keboola_configuration_id": "12345",
            }

            response = client.post("/api/jobs", json=job_data)
            assert response.status_code == 422

    def test_batch_id_with_valid_characters(
        self, client, sample_openai_secret, sample_keboola_secret
    ):
        """Test batch_id with valid characters (alphanumeric, hyphen, underscore)."""
        job_data = {
            "name": "Valid Characters Job",
            "batch_ids": ["batch_test-123_ABC"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 201

    def test_empty_batch_ids_array(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with empty batch_ids array fails."""
        job_data = {
            "name": "Empty Batch IDs Job",
            "batch_ids": [],  # Empty array
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 422

    def test_batch_ids_not_array(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with batch_ids as string instead of array fails."""
        job_data = {
            "name": "String Batch IDs Job",
            "batch_ids": "batch_test",  # String instead of array
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 422


class TestComputedCountsEdgeCases:
    """Test computed counts with various batch status combinations."""

    def test_all_batches_completed(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test job with all batches completed."""
        job = PollingJob(
            name="All Completed Job",
            openai_secret_id=sample_openai_secret.id,
            keboola_secret_id=sample_keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="test-component",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job)
        db_session.commit()

        # All batches completed
        for i in range(3):
            batch = JobBatch(job_id=job.id, batch_id=f"batch_{i:03d}", status="completed")
            db_session.add(batch)
        db_session.commit()

        response = client.get(f"/api/jobs/{job.id}")
        data = response.json()

        assert data["batch_count"] == 3
        assert data["completed_count"] == 3
        assert data["failed_count"] == 0

    def test_mixed_failed_statuses(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test job with different failed status types (failed, cancelled, expired)."""
        job = PollingJob(
            name="Mixed Failed Job",
            openai_secret_id=sample_openai_secret.id,
            keboola_secret_id=sample_keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="test-component",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job)
        db_session.commit()

        # Create batches with different terminal states
        batch1 = JobBatch(job_id=job.id, batch_id="batch_001", status="failed")
        batch2 = JobBatch(job_id=job.id, batch_id="batch_002", status="cancelled")
        batch3 = JobBatch(job_id=job.id, batch_id="batch_003", status="expired")
        batch4 = JobBatch(job_id=job.id, batch_id="batch_004", status="completed")
        db_session.add_all([batch1, batch2, batch3, batch4])
        db_session.commit()

        response = client.get(f"/api/jobs/{job.id}")
        data = response.json()

        assert data["batch_count"] == 4
        assert data["completed_count"] == 1
        assert data["failed_count"] == 3  # failed + cancelled + expired

    def test_job_with_zero_batches(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test job without any batches (edge case - shouldn't normally happen)."""
        job = PollingJob(
            name="No Batches Job",
            openai_secret_id=sample_openai_secret.id,
            keboola_secret_id=sample_keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="test-component",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/jobs/{job.id}")
        data = response.json()

        assert data["batch_count"] == 0
        assert data["completed_count"] == 0
        assert data["failed_count"] == 0
        assert data["batches"] == []
