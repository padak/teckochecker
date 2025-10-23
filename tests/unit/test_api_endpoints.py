"""
Unit tests for API endpoints.

This module tests:
- Health and stats endpoints
- Secret CRUD operations via API
- Job CRUD operations via API
- Job pause/resume functionality
- Error handling (404, 409, 422, 500)
- Response schema validation
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models import Secret, PollingJob, PollingLog
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
    # Keep session open, don't expunge
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
    # Keep session open, don't expunge
    return secret


@pytest.fixture
def sample_job(db_session, sample_openai_secret, sample_keboola_secret):
    """Create a sample polling job in the database."""
    from app.models import JobBatch

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

    # Add a batch to the job (multi-batch schema)
    batch = JobBatch(
        job_id=job.id,
        batch_id="batch_abc123",
        status="in_progress",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(job)

    # Keep session open, don't expunge
    return job


# ============================================================================
# System Endpoints Tests
# ============================================================================


class TestSystemEndpoints:
    """Test cases for system endpoints (/api/health, /api/stats)."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/api/health"

    def test_health_check_success(self, client):
        """Test health check endpoint returns healthy status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data

    def test_health_check_response_schema(self, client):
        """Test health check response matches schema."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        required_fields = ["status", "timestamp", "database", "version"]
        for field in required_fields:
            assert field in data

    def test_stats_empty_database(self, client):
        """Test stats endpoint with empty database."""
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 0
        assert data["active_jobs"] == 0
        assert data["paused_jobs"] == 0
        assert data["completed_jobs"] == 0
        assert data["failed_jobs"] == 0
        assert data["total_secrets"] == 0
        assert data["total_logs"] == 0

    def test_stats_with_data(self, client, sample_job):
        """Test stats endpoint with existing data."""
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 1
        assert data["active_jobs"] == 1
        assert data["total_secrets"] == 2  # OpenAI + Keboola from fixtures
        assert data["total_logs"] == 0

    def test_stats_job_counts(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test stats correctly counts jobs by status."""
        from app.models import JobBatch

        # Create jobs with different statuses
        statuses = ["active", "paused", "completed", "failed"]
        for status in statuses:
            job = PollingJob(
                name=f"Job {status}",
                openai_secret_id=sample_openai_secret.id,
                keboola_secret_id=sample_keboola_secret.id,
                keboola_stack_url="https://connection.keboola.com",
                keboola_component_id="test-component",
                keboola_configuration_id="12345",
                status=status,
            )
            db_session.add(job)
            db_session.flush()

            # Add batch for each job
            batch = JobBatch(
                job_id=job.id,
                batch_id=f"batch_{status}",
                status="in_progress",
            )
            db_session.add(batch)

        db_session.commit()

        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs"] == 4
        assert data["active_jobs"] == 1
        assert data["paused_jobs"] == 1
        assert data["completed_jobs"] == 1
        assert data["failed_jobs"] == 1


# ============================================================================
# Secret Management Endpoints Tests
# ============================================================================


class TestSecretEndpoints:
    """Test cases for secret management endpoints (/api/admin/secrets)."""

    def test_create_secret_openai(self, client):
        """Test creating a new OpenAI secret."""
        secret_data = {"name": "production-openai", "type": "openai", "value": "sk-prod-key-12345"}

        response = client.post("/api/admin/secrets", json=secret_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == secret_data["name"]
        assert data["type"] == secret_data["type"]
        assert "id" in data
        assert "created_at" in data
        assert "value" not in data  # Value should not be returned

    def test_create_secret_keboola(self, client):
        """Test creating a new Keboola secret."""
        secret_data = {"name": "production-keboola", "type": "keboola", "value": "kbc-token-67890"}

        response = client.post("/api/admin/secrets", json=secret_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == secret_data["name"]
        assert data["type"] == secret_data["type"]

    def test_create_secret_invalid_type(self, client):
        """Test creating secret with invalid type."""
        secret_data = {"name": "invalid-secret", "type": "invalid_type", "value": "some-value"}

        response = client.post("/api/admin/secrets", json=secret_data)

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"

    def test_create_secret_duplicate_name(self, client, sample_openai_secret):
        """Test creating secret with duplicate name."""
        secret_data = {"name": sample_openai_secret.name, "type": "openai", "value": "another-key"}

        response = client.post("/api/admin/secrets", json=secret_data)

        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["detail"]

    def test_create_secret_missing_fields(self, client):
        """Test creating secret with missing required fields."""
        secret_data = {
            "name": "incomplete-secret"
            # Missing type and value
        }

        response = client.post("/api/admin/secrets", json=secret_data)

        assert response.status_code == 422

    def test_create_secret_empty_value(self, client):
        """Test creating secret with empty value."""
        secret_data = {"name": "empty-secret", "type": "openai", "value": ""}

        response = client.post("/api/admin/secrets", json=secret_data)

        assert response.status_code == 422

    def test_list_secrets_empty(self, client):
        """Test listing secrets when database is empty."""
        response = client.get("/api/admin/secrets")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["secrets"] == []

    def test_list_secrets(self, client, sample_openai_secret, sample_keboola_secret):
        """Test listing all secrets."""
        response = client.get("/api/admin/secrets")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["secrets"]) == 2

        # Verify response structure
        for secret in data["secrets"]:
            assert "id" in secret
            assert "name" in secret
            assert "type" in secret
            assert "created_at" in secret
            assert "value" not in secret

    def test_list_secrets_response_schema(self, client, sample_openai_secret):
        """Test list secrets response matches schema."""
        response = client.get("/api/admin/secrets")

        assert response.status_code == 200
        data = response.json()
        assert "secrets" in data
        assert "total" in data
        assert isinstance(data["secrets"], list)

    def test_get_secret_by_id(self, client, sample_openai_secret):
        """Test retrieving a specific secret by ID."""
        response = client.get(f"/api/admin/secrets/{sample_openai_secret.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_openai_secret.id
        assert data["name"] == sample_openai_secret.name
        assert data["type"] == sample_openai_secret.type
        assert "value" not in data

    def test_get_secret_not_found(self, client):
        """Test retrieving non-existent secret."""
        response = client.get("/api/admin/secrets/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert response.headers.get("X-Error-Code") == "1001"

    def test_delete_secret(self, client, sample_openai_secret):
        """Test deleting a secret."""
        response = client.delete(f"/api/admin/secrets/{sample_openai_secret.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        # Verify secret is deleted
        get_response = client.get(f"/api/admin/secrets/{sample_openai_secret.id}")
        assert get_response.status_code == 404

    def test_delete_secret_not_found(self, client):
        """Test deleting non-existent secret."""
        response = client.delete("/api/admin/secrets/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert response.headers.get("X-Error-Code") == "1001"

    def test_delete_secret_in_use(self, client, sample_job):
        """Test deleting secret that is referenced by active job."""
        # Try to delete the OpenAI secret used by the job
        response = client.delete(f"/api/admin/secrets/{sample_job.openai_secret_id}")

        assert response.status_code == 409
        data = response.json()
        assert "referenced by active jobs" in data["detail"]

    def test_delete_secret_completed_job_ok(self, client, db_session, sample_job):
        """Test deleting secret referenced by completed job is allowed."""
        # Mark job as completed
        sample_job.status = "completed"
        db_session.commit()

        # Should be able to delete the secret now
        response = client.delete(f"/api/admin/secrets/{sample_job.openai_secret_id}")

        # This should succeed since the job is not active/paused
        assert response.status_code == 200


# ============================================================================
# Job Management Endpoints Tests
# ============================================================================


class TestJobEndpoints:
    """Test cases for job management endpoints (/api/jobs)."""

    def test_create_job_success(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating a new polling job."""
        job_data = {
            "name": "My Test Job",
            "batch_ids": ["batch_xyz789"],
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
        assert len(data["batches"]) == 1
        assert data["batches"][0]["batch_id"] == "batch_xyz789"
        assert data["status"] == "active"
        assert data["poll_interval_seconds"] == 180
        assert "id" in data
        assert "created_at" in data
        assert "next_check_at" in data

    def test_create_job_default_poll_interval(
        self, client, sample_openai_secret, sample_keboola_secret
    ):
        """Test creating job with default poll interval."""
        job_data = {
            "name": "Default Interval Job",
            "batch_ids": ["batch_default"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
            # poll_interval_seconds not provided
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 201
        data = response.json()
        assert data["poll_interval_seconds"] == 120  # Default value

    def test_create_job_invalid_openai_secret(self, client, sample_keboola_secret):
        """Test creating job with non-existent OpenAI secret."""
        job_data = {
            "name": "Invalid Job",
            "batch_ids": ["batch_invalid"],
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

    def test_create_job_invalid_keboola_secret(self, client, sample_openai_secret):
        """Test creating job with non-existent Keboola secret."""
        job_data = {
            "name": "Invalid Job",
            "batch_ids": ["batch_invalid"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": 99999,  # Non-existent
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 404
        data = response.json()
        assert "Keboola secret" in data["detail"]

    def test_create_job_invalid_poll_interval(
        self, client, sample_openai_secret, sample_keboola_secret
    ):
        """Test creating job with invalid poll interval."""
        job_data = {
            "name": "Invalid Interval Job",
            "batch_ids": ["batch_invalid_interval"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
            "poll_interval_seconds": 10,  # Below minimum of 30
        }

        response = client.post("/api/jobs", json=job_data)

        assert response.status_code == 422

    def test_create_job_creates_log_entry(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test that creating a job also creates initial log entry."""
        job_data = {
            "name": "Logged Job",
            "batch_ids": ["batch_logged"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 201

        job_id = response.json()["id"]

        # Check that log entry was created
        log = db_session.query(PollingLog).filter(PollingLog.job_id == job_id).first()

        assert log is not None
        assert log.status == "created"

    def test_list_jobs_empty(self, client):
        """Test listing jobs when database is empty."""
        response = client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["jobs"] == []

    def test_list_jobs(self, client, sample_job):
        """Test listing all jobs."""
        response = client.get("/api/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == sample_job.id

    def test_list_jobs_filter_by_status(
        self, client, db_session, sample_openai_secret, sample_keboola_secret
    ):
        """Test filtering jobs by status."""
        from app.models import JobBatch

        # Create jobs with different statuses
        active_job = PollingJob(
            name="Active Job",
            openai_secret_id=sample_openai_secret.id,
            keboola_secret_id=sample_keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="test-component",
            keboola_configuration_id="12345",
            status="active",
        )
        paused_job = PollingJob(
            name="Paused Job",
            openai_secret_id=sample_openai_secret.id,
            keboola_secret_id=sample_keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="test-component",
            keboola_configuration_id="12345",
            status="paused",
        )
        db_session.add_all([active_job, paused_job])
        db_session.flush()

        # Add batches
        active_batch = JobBatch(job_id=active_job.id, batch_id="batch_active", status="in_progress")
        paused_batch = JobBatch(job_id=paused_job.id, batch_id="batch_paused", status="in_progress")
        db_session.add_all([active_batch, paused_batch])
        db_session.commit()

        # Filter for active jobs only
        response = client.get("/api/jobs?status=active")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["jobs"][0]["status"] == "active"

    def test_get_job_by_id(self, client, sample_job):
        """Test retrieving a specific job by ID."""
        response = client.get(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_job.id
        assert data["name"] == sample_job.name
        assert "batches" in data
        assert len(data["batches"]) > 0
        assert "logs" in data

    def test_get_job_with_logs(self, client, db_session, sample_job):
        """Test retrieving job with logs included."""
        # Create some log entries
        log1 = PollingLog(job_id=sample_job.id, status="checking", message="Checking batch status")
        log2 = PollingLog(job_id=sample_job.id, status="pending", message="Batch still in progress")
        db_session.add_all([log1, log2])
        db_session.commit()

        response = client.get(f"/api/jobs/{sample_job.id}?include_logs=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 2

    def test_get_job_without_logs(self, client, db_session, sample_job):
        """Test retrieving job without logs."""
        # Create log entry
        log = PollingLog(job_id=sample_job.id, status="checking", message="Test log")
        db_session.add(log)
        db_session.commit()

        response = client.get(f"/api/jobs/{sample_job.id}?include_logs=false")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 0

    def test_get_job_log_limit(self, client, db_session, sample_job):
        """Test log limit parameter."""
        # Create multiple log entries
        for i in range(10):
            log = PollingLog(job_id=sample_job.id, status="checking", message=f"Log {i}")
            db_session.add(log)
        db_session.commit()

        response = client.get(f"/api/jobs/{sample_job.id}?log_limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 5

    def test_get_job_not_found(self, client):
        """Test retrieving non-existent job."""
        response = client.get("/api/jobs/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert response.headers.get("X-Error-Code") == "1002"

    def test_update_job(self, client, sample_job):
        """Test updating a job."""
        update_data = {"name": "Updated Job Name", "poll_interval_seconds": 300}

        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["poll_interval_seconds"] == update_data["poll_interval_seconds"]

    def test_update_job_partial(self, client, sample_job):
        """Test partial update of job."""
        update_data = {"name": "New Name Only"}

        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        # Other fields should remain unchanged (batches should still exist)
        assert "batches" in data

    def test_update_job_not_found(self, client):
        """Test updating non-existent job."""
        update_data = {"name": "New Name"}

        response = client.put("/api/jobs/99999", json=update_data)

        assert response.status_code == 404

    def test_update_job_creates_log(self, client, db_session, sample_job):
        """Test that updating job creates log entry."""
        update_data = {"name": "Updated Name"}

        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)
        assert response.status_code == 200

        # Check for log entry
        log = (
            db_session.query(PollingLog)
            .filter(PollingLog.job_id == sample_job.id, PollingLog.status == "updated")
            .first()
        )

        assert log is not None

    def test_delete_job(self, client, sample_job):
        """Test deleting a job."""
        response = client.delete(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        # Verify job is deleted
        get_response = client.get(f"/api/jobs/{sample_job.id}")
        assert get_response.status_code == 404

    def test_delete_job_not_found(self, client):
        """Test deleting non-existent job."""
        response = client.delete("/api/jobs/99999")

        assert response.status_code == 404

    def test_delete_job_cascades_to_logs(self, client, db_session, sample_job):
        """Test that deleting job also deletes associated logs."""
        # Create log entries
        log1 = PollingLog(job_id=sample_job.id, status="test", message="Log 1")
        log2 = PollingLog(job_id=sample_job.id, status="test", message="Log 2")
        db_session.add_all([log1, log2])
        db_session.commit()

        # Delete job
        response = client.delete(f"/api/jobs/{sample_job.id}")
        assert response.status_code == 200

        # Verify logs are deleted
        remaining_logs = (
            db_session.query(PollingLog).filter(PollingLog.job_id == sample_job.id).count()
        )
        assert remaining_logs == 0


# ============================================================================
# Job Pause/Resume Tests
# ============================================================================


class TestJobPauseResume:
    """Test cases for job pause and resume functionality."""

    def test_pause_active_job(self, client, sample_job):
        """Test pausing an active job."""
        assert sample_job.status == "active"

        response = client.post(f"/api/jobs/{sample_job.id}/pause")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    def test_pause_job_creates_log(self, client, db_session, sample_job):
        """Test that pausing creates log entry."""
        response = client.post(f"/api/jobs/{sample_job.id}/pause")
        assert response.status_code == 200

        log = (
            db_session.query(PollingLog)
            .filter(PollingLog.job_id == sample_job.id, PollingLog.status == "paused")
            .first()
        )

        assert log is not None
        assert "paused by user" in log.message.lower()

    def test_pause_already_paused_job(self, client, db_session, sample_job):
        """Test pausing a job that is already paused."""
        # Pause the job first
        sample_job.status = "paused"
        db_session.commit()

        response = client.post(f"/api/jobs/{sample_job.id}/pause")

        assert response.status_code == 409
        data = response.json()
        assert "Cannot pause" in data["detail"]

    def test_pause_completed_job(self, client, db_session, sample_job):
        """Test pausing a completed job fails."""
        sample_job.status = "completed"
        db_session.commit()

        response = client.post(f"/api/jobs/{sample_job.id}/pause")

        assert response.status_code == 409

    def test_pause_job_not_found(self, client):
        """Test pausing non-existent job."""
        response = client.post("/api/jobs/99999/pause")

        assert response.status_code == 404

    def test_resume_paused_job(self, client, db_session, sample_job):
        """Test resuming a paused job."""
        # Pause the job first
        sample_job.status = "paused"
        db_session.commit()

        response = client.post(f"/api/jobs/{sample_job.id}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["next_check_at"] is not None

    def test_resume_job_creates_log(self, client, db_session, sample_job):
        """Test that resuming creates log entry."""
        sample_job.status = "paused"
        db_session.commit()

        response = client.post(f"/api/jobs/{sample_job.id}/resume")
        assert response.status_code == 200

        log = (
            db_session.query(PollingLog)
            .filter(PollingLog.job_id == sample_job.id, PollingLog.status == "resumed")
            .first()
        )

        assert log is not None
        assert "resumed by user" in log.message.lower()

    def test_resume_active_job(self, client, sample_job):
        """Test resuming an active job fails."""
        assert sample_job.status == "active"

        response = client.post(f"/api/jobs/{sample_job.id}/resume")

        assert response.status_code == 409
        data = response.json()
        assert "Cannot resume" in data["detail"]

    def test_resume_job_not_found(self, client):
        """Test resuming non-existent job."""
        response = client.post("/api/jobs/99999/resume")

        assert response.status_code == 404

    def test_pause_resume_cycle(self, client, db_session, sample_job):
        """Test full pause/resume cycle."""
        # Initial state: active
        assert sample_job.status == "active"

        # Pause
        pause_response = client.post(f"/api/jobs/{sample_job.id}/pause")
        assert pause_response.status_code == 200
        assert pause_response.json()["status"] == "paused"

        # Resume
        resume_response = client.post(f"/api/jobs/{sample_job.id}/resume")
        assert resume_response.status_code == 200
        assert resume_response.json()["status"] == "active"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test cases for error handling across all endpoints."""

    def test_validation_error_format(self, client):
        """Test validation error response format."""
        # Send invalid data (missing required fields)
        response = client.post("/api/admin/secrets", json={})

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"
        assert "message" in data
        assert "details" in data

    def test_validation_error_details(self, client):
        """Test validation error includes field details."""
        response = client.post("/api/admin/secrets", json={"name": "test"})

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["details"], list)
        # Should include errors for missing fields
        assert len(data["details"]) > 0

    def test_invalid_endpoint(self, client):
        """Test accessing non-existent endpoint."""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404

    def test_invalid_method(self, client):
        """Test using invalid HTTP method."""
        # POST to endpoint that only accepts GET
        response = client.post("/api/health")

        assert response.status_code == 405  # Method Not Allowed

    def test_malformed_json(self, client):
        """Test sending malformed JSON."""
        response = client.post(
            "/api/admin/secrets",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_invalid_id_type(self, client):
        """Test using invalid ID type in URL."""
        response = client.get("/api/jobs/not-a-number")

        assert response.status_code == 422


# ============================================================================
# Response Schema Validation Tests
# ============================================================================


class TestResponseSchemas:
    """Test that API responses match Pydantic schemas."""

    def test_secret_response_schema(self, client, sample_openai_secret):
        """Test secret response matches SecretResponse schema."""
        response = client.get(f"/api/admin/secrets/{sample_openai_secret.id}")

        assert response.status_code == 200
        data = response.json()

        # Check all required fields
        required_fields = ["id", "name", "type", "created_at"]
        for field in required_fields:
            assert field in data
            assert data[field] is not None

    def test_secret_list_response_schema(self, client):
        """Test secret list response matches SecretListResponse schema."""
        response = client.get("/api/admin/secrets")

        assert response.status_code == 200
        data = response.json()

        assert "secrets" in data
        assert "total" in data
        assert isinstance(data["secrets"], list)
        assert isinstance(data["total"], int)

    def test_job_response_schema(self, client, sample_job):
        """Test job response matches PollingJobResponse schema."""
        response = client.get(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "id",
            "name",
            "batches",  # Changed from batch_id to batches array
            "batch_count",
            "completed_count",
            "failed_count",
            "openai_secret_id",
            "keboola_secret_id",
            "keboola_stack_url",
            "keboola_component_id",
            "keboola_configuration_id",
            "poll_interval_seconds",
            "status",
            "created_at",
        ]
        for field in required_fields:
            assert field in data

    def test_job_detail_response_schema(self, client, sample_job):
        """Test job detail response includes logs."""
        response = client.get(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()

        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_message_response_schema(self, client, sample_job):
        """Test message response matches MessageResponse schema."""
        response = client.delete(f"/api/jobs/{sample_job.id}")

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "success" in data
        assert isinstance(data["success"], bool)

    def test_health_response_schema(self, client):
        """Test health response matches HealthResponse schema."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        required_fields = ["status", "timestamp", "database", "version"]
        for field in required_fields:
            assert field in data

    def test_stats_response_schema(self, client):
        """Test stats response matches StatsResponse schema."""
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "total_jobs",
            "active_jobs",
            "paused_jobs",
            "completed_jobs",
            "failed_jobs",
            "total_secrets",
            "total_logs",
        ]
        for field in required_fields:
            assert field in data
            assert isinstance(data[field], int)


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and integration scenarios."""

    def test_create_multiple_jobs_same_batch(
        self, client, sample_openai_secret, sample_keboola_secret
    ):
        """Test creating multiple jobs with the same batch_id."""
        job_data_1 = {
            "name": "Job 1",
            "batch_ids": ["batch_shared"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        job_data_2 = {
            "name": "Job 2",
            "batch_ids": ["batch_shared"],  # Same batch_id
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "54321",
        }

        response1 = client.post("/api/jobs", json=job_data_1)
        response2 = client.post("/api/jobs", json=job_data_2)

        # Both should succeed (same batch_id is allowed in different jobs)
        assert response1.status_code == 201
        assert response2.status_code == 201

    def test_job_with_very_long_names(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with maximum length name."""
        job_data = {
            "name": "A" * 255,  # Max length
            "batch_ids": ["batch_long_name"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 201

    def test_job_with_min_poll_interval(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with minimum poll interval."""
        job_data = {
            "name": "Min Interval Job",
            "batch_ids": ["batch_min_interval"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
            "poll_interval_seconds": 30,  # Minimum allowed
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 201

    def test_job_with_max_poll_interval(self, client, sample_openai_secret, sample_keboola_secret):
        """Test creating job with maximum poll interval."""
        job_data = {
            "name": "Max Interval Job",
            "batch_ids": ["batch_max_interval"],
            "openai_secret_id": sample_openai_secret.id,
            "keboola_secret_id": sample_keboola_secret.id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
            "poll_interval_seconds": 3600,  # Maximum allowed
        }

        response = client.post("/api/jobs", json=job_data)
        assert response.status_code == 201

    def test_unicode_in_secret_name(self, client):
        """Test creating secret with Unicode characters in name."""
        secret_data = {"name": "test-secret-世界", "type": "openai", "value": "sk-test-key"}

        response = client.post("/api/admin/secrets", json=secret_data)
        assert response.status_code == 201
        assert response.json()["name"] == secret_data["name"]

    def test_empty_stats_calculation(self, client):
        """Test stats endpoint handles zero values correctly."""
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # All counts should be 0 or None
        assert data["total_jobs"] == 0
        assert data["active_jobs"] == 0
        assert data["total_secrets"] == 0
