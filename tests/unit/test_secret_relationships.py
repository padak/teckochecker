"""
Unit tests for Secret model relationships.

This module specifically tests the relationships between Secret and PollingJob models
to validate that openai_jobs and keboola_jobs relationships work correctly.

Tests validate the bug report from Codex claiming that jobs_as_openai and jobs_as_keboola
don't exist. This test proves that the correct relationship names (openai_jobs and
keboola_jobs) are properly implemented and functional.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Secret, PollingJob, Base
from app.schemas import SecretCreate
from app.services.encryption import init_encryption_service
from app.services.secrets import SecretManager, SecretInUseError


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
def encryption_key():
    """Generate a test encryption key."""
    return "test-secret-key-for-relationship-testing"


@pytest.fixture
def secret_manager(db_session, encryption_key):
    """Create a SecretManager instance."""
    init_encryption_service(encryption_key)
    return SecretManager(db_session)


# ============================================================================
# Relationship Tests
# ============================================================================


class TestSecretRelationships:
    """Test cases for Secret model relationships with PollingJob."""

    def test_secret_openai_jobs_relationship_exists(self, db_session, secret_manager):
        """Test that openai_jobs relationship exists and works."""
        # Create a secret
        secret = secret_manager.create_secret(
            SecretCreate(name="test-openai", type="openai", value="sk-test-key")
        )

        # Get the secret from database
        db_secret = db_session.query(Secret).filter(Secret.id == secret.id).first()

        # Verify openai_jobs relationship exists
        assert hasattr(db_secret, "openai_jobs")
        assert isinstance(db_secret.openai_jobs, list)
        assert len(db_secret.openai_jobs) == 0

    def test_secret_keboola_jobs_relationship_exists(self, db_session, secret_manager):
        """Test that keboola_jobs relationship exists and works."""
        # Create a secret
        secret = secret_manager.create_secret(
            SecretCreate(name="test-keboola", type="keboola", value="keboola-token")
        )

        # Get the secret from database
        db_secret = db_session.query(Secret).filter(Secret.id == secret.id).first()

        # Verify keboola_jobs relationship exists
        assert hasattr(db_secret, "keboola_jobs")
        assert isinstance(db_secret.keboola_jobs, list)
        assert len(db_secret.keboola_jobs) == 0

    def test_secret_used_only_as_openai(self, db_session, secret_manager):
        """Test secret used only as openai_secret in jobs."""
        # Create secrets
        openai_secret = secret_manager.create_secret(
            SecretCreate(name="openai-only", type="openai", value="sk-openai-key")
        )
        keboola_secret = secret_manager.create_secret(
            SecretCreate(name="keboola-only", type="keboola", value="keboola-token")
        )

        # Create job using openai_secret
        job = PollingJob(
            name="test-job-openai-only",
            openai_secret_id=openai_secret.id,  # Using openai secret
            keboola_secret_id=keboola_secret.id,  # Using different keboola secret
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job)
        db_session.flush()

        from app.models import JobBatch
        batch = JobBatch(job_id=job.id, batch_id="batch_123", status="in_progress")
        db_session.add(batch)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(db_session.query(Secret).filter(Secret.id == openai_secret.id).first())
        db_secret = db_session.query(Secret).filter(Secret.id == openai_secret.id).first()

        # Verify relationships
        assert len(db_secret.openai_jobs) == 1
        assert len(db_secret.keboola_jobs) == 0
        assert db_secret.openai_jobs[0].id == job.id

    def test_secret_used_only_as_keboola(self, db_session, secret_manager):
        """Test secret used only as keboola_secret in jobs."""
        # Create secrets
        openai_secret = secret_manager.create_secret(
            SecretCreate(name="openai-only", type="openai", value="sk-openai-key")
        )
        keboola_secret = secret_manager.create_secret(
            SecretCreate(name="keboola-only", type="keboola", value="keboola-token")
        )

        # Create job using keboola_secret
        job = PollingJob(
            name="test-job-keboola-only",
            openai_secret_id=openai_secret.id,  # Using different openai secret
            keboola_secret_id=keboola_secret.id,  # Using keboola secret
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job)
        db_session.flush()

        from app.models import JobBatch
        batch = JobBatch(job_id=job.id, batch_id="batch_456", status="in_progress")
        db_session.add(batch)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(db_session.query(Secret).filter(Secret.id == keboola_secret.id).first())
        db_secret = db_session.query(Secret).filter(Secret.id == keboola_secret.id).first()

        # Verify relationships
        assert len(db_secret.openai_jobs) == 0
        assert len(db_secret.keboola_jobs) == 1
        assert db_secret.keboola_jobs[0].id == job.id

    def test_secret_used_as_both_openai_and_keboola(self, db_session, secret_manager):
        """Test secret used as both openai_secret and keboola_secret."""
        # Create a multi-purpose secret
        secret = secret_manager.create_secret(
            SecretCreate(name="multi-purpose", type="openai", value="sk-key")
        )

        # Create job using the same secret for both
        job = PollingJob(
            name="test-job-both",
            openai_secret_id=secret.id,  # Using as openai
            keboola_secret_id=secret.id,  # Using as keboola
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job)
        db_session.flush()

        from app.models import JobBatch
        batch = JobBatch(job_id=job.id, batch_id="batch_789", status="in_progress")
        db_session.add(batch)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(db_session.query(Secret).filter(Secret.id == secret.id).first())
        db_secret = db_session.query(Secret).filter(Secret.id == secret.id).first()

        # Verify relationships - should appear in both
        assert len(db_secret.openai_jobs) == 1
        assert len(db_secret.keboola_jobs) == 1
        assert db_secret.openai_jobs[0].id == job.id
        assert db_secret.keboola_jobs[0].id == job.id

    def test_secret_used_by_multiple_jobs(self, db_session, secret_manager):
        """Test secret referenced by multiple jobs."""
        # Create secrets
        openai_secret = secret_manager.create_secret(
            SecretCreate(name="shared-openai", type="openai", value="sk-shared-key")
        )
        keboola_secret = secret_manager.create_secret(
            SecretCreate(name="shared-keboola", type="keboola", value="keboola-token")
        )

        # Create multiple jobs using the same openai_secret
        from app.models import JobBatch

        for i in range(3):
            job = PollingJob(
                name=f"test-job-{i}",
                openai_secret_id=openai_secret.id,
                keboola_secret_id=keboola_secret.id,
                keboola_stack_url="https://connection.keboola.com",
                keboola_component_id="kds-team.app-custom-python",
                keboola_configuration_id="12345",
                status="active",
            )
            db_session.add(job)
            db_session.flush()

            batch = JobBatch(job_id=job.id, batch_id=f"batch_{i}", status="in_progress")
            db_session.add(batch)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(db_session.query(Secret).filter(Secret.id == openai_secret.id).first())
        db_secret = db_session.query(Secret).filter(Secret.id == openai_secret.id).first()

        # Verify relationships
        assert len(db_secret.openai_jobs) == 3
        assert all(job.openai_secret_id == openai_secret.id for job in db_secret.openai_jobs)

    def test_delete_secret_checks_both_relationships(self, db_session, secret_manager):
        """
        Test that delete_secret properly checks BOTH openai_jobs and keboola_jobs.

        This is the core test that validates the fix for Codex's bug report.
        The delete_secret method should check:
            len(secret.openai_jobs) + len(secret.keboola_jobs)
        """
        # Create a secret
        secret = secret_manager.create_secret(
            SecretCreate(name="test-both-relationships", type="openai", value="sk-test-key")
        )

        # Create job using secret only as openai_secret
        job1 = PollingJob(
            name="job-using-openai",
            openai_secret_id=secret.id,
            keboola_secret_id=secret.id,  # Also using as keboola
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job1)
        db_session.flush()

        from app.models import JobBatch
        batch = JobBatch(job_id=job1.id, batch_id="batch_1", status="in_progress")
        db_session.add(batch)
        db_session.commit()

        # Try to delete - should fail because secret is in use
        with pytest.raises(SecretInUseError) as exc_info:
            secret_manager.delete_secret(secret.id)

        # Verify error message mentions the total count
        assert "referenced by" in str(exc_info.value)

        # Get the secret to verify counts
        db_secret = db_session.query(Secret).filter(Secret.id == secret.id).first()
        total_jobs = len(db_secret.openai_jobs) + len(db_secret.keboola_jobs)
        assert total_jobs == 2  # Same job appears in both relationships

    def test_relationships_attribute_names(self, db_session):
        """
        Test that the correct relationship attribute names exist.

        This validates that:
        - openai_jobs exists (NOT jobs_as_openai)
        - keboola_jobs exists (NOT jobs_as_keboola)
        """
        # Create a secret directly
        secret = Secret(
            name="test-attributes",
            type="openai",
            value="encrypted-value",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(secret)
        db_session.commit()

        # Verify correct attribute names exist
        assert hasattr(secret, "openai_jobs"), "Missing openai_jobs relationship"
        assert hasattr(secret, "keboola_jobs"), "Missing keboola_jobs relationship"

        # Verify incorrect attribute names do NOT exist
        assert not hasattr(secret, "jobs_as_openai"), "Unexpected jobs_as_openai attribute found"
        assert not hasattr(secret, "jobs_as_keboola"), "Unexpected jobs_as_keboola attribute found"


# ============================================================================
# Integration Test for Delete with Relationships
# ============================================================================


class TestDeleteSecretWithRelationships:
    """Integration tests for deleting secrets with various relationship scenarios."""

    def test_complex_deletion_scenario(self, db_session, secret_manager):
        """Test complex scenario with multiple secrets and jobs."""
        # Create multiple secrets
        openai_secret_1 = secret_manager.create_secret(
            SecretCreate(name="openai-1", type="openai", value="key-1")
        )
        openai_secret_2 = secret_manager.create_secret(
            SecretCreate(name="openai-2", type="openai", value="key-2")
        )
        keboola_secret = secret_manager.create_secret(
            SecretCreate(name="keboola-1", type="keboola", value="token-1")
        )

        # Create job using openai_secret_1
        job1 = PollingJob(
            name="job-1",
            openai_secret_id=openai_secret_1.id,
            keboola_secret_id=keboola_secret.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_component_id="kds-team.app-custom-python",
            keboola_configuration_id="12345",
            status="active",
        )
        db_session.add(job1)
        db_session.flush()

        from app.models import JobBatch
        batch = JobBatch(job_id=job1.id, batch_id="batch_1", status="in_progress")
        db_session.add(batch)
        db_session.commit()

        # Should NOT be able to delete openai_secret_1 (in use)
        with pytest.raises(SecretInUseError):
            secret_manager.delete_secret(openai_secret_1.id)

        # Should NOT be able to delete keboola_secret (in use)
        with pytest.raises(SecretInUseError):
            secret_manager.delete_secret(keboola_secret.id)

        # SHOULD be able to delete openai_secret_2 (not in use)
        secret_manager.delete_secret(openai_secret_2.id)
        assert secret_manager.get_secret_by_id(openai_secret_2.id) is None

        # Force delete should work for secrets in use
        secret_manager.delete_secret(openai_secret_1.id, force=True)
        assert secret_manager.get_secret_by_id(openai_secret_1.id) is None
