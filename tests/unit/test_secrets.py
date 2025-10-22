"""
Unit tests for secrets management system.

This module tests:
- Encryption service functionality
- SecretManager CRUD operations
- Secret validation
- Error handling
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models import Secret, PollingJob, Base
from app.schemas import SecretCreate
from app.services.encryption import (
    EncryptionService,
    init_encryption_service,
    get_encryption_service
)
from app.services.secrets import (
    SecretManager,
    SecretNotFoundError,
    SecretValidationError,
    SecretAlreadyExistsError,
    SecretInUseError
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return "test-secret-key-for-testing-purposes"


@pytest.fixture
def encryption_service(encryption_key):
    """Create an encryption service instance."""
    return EncryptionService(secret_key=encryption_key)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def secret_manager(db_session, encryption_key):
    """Create a SecretManager instance with mocked encryption service."""
    # Initialize the global encryption service
    init_encryption_service(encryption_key)
    manager = SecretManager(db_session)
    yield manager


@pytest.fixture
def sample_secret_data():
    """Sample secret creation data."""
    return SecretCreate(
        name="test-openai-key",
        type="openai",
        value="sk-test-key-12345"
    )


# ============================================================================
# EncryptionService Tests
# ============================================================================

class TestEncryptionService:
    """Test cases for EncryptionService."""

    def test_initialization_with_key(self, encryption_key):
        """Test encryption service initialization with provided key."""
        service = EncryptionService(secret_key=encryption_key)
        assert service is not None
        assert service.fernet is not None

    def test_encrypt_decrypt_roundtrip(self, encryption_service):
        """Test that encryption and decryption work correctly."""
        plaintext = "my-secret-api-key"
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert encrypted != plaintext
        assert decrypted == plaintext

    def test_decrypt_with_wrong_key(self, encryption_key):
        """Test that decrypting with wrong key fails."""
        # Encrypt with one key
        service1 = EncryptionService(secret_key=encryption_key)
        encrypted = service1.encrypt("secret-data")

        # Try to decrypt with different key
        different_key = "different-secret-key"
        service2 = EncryptionService(secret_key=different_key)

        # Should raise an exception (InvalidToken from Fernet)
        with pytest.raises(Exception):
            service2.decrypt(encrypted)

    def test_encrypt_unicode(self, encryption_service):
        """Test encrypting and decrypting Unicode strings."""
        plaintext = "Hello 世界 🌍"
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_init_and_get_encryption_service(self, encryption_key):
        """Test initializing and getting global encryption service."""
        # Initialize the service
        service1 = init_encryption_service(encryption_key)
        assert service1 is not None

        # Get the same instance
        service2 = get_encryption_service()
        assert service1 is service2

    def test_get_encryption_service_not_initialized(self):
        """Test getting encryption service before initialization."""
        # Reset the global instance
        import app.services.encryption as enc_module
        enc_module._encryption_service = None

        with pytest.raises(RuntimeError, match="not initialized"):
            get_encryption_service()


# ============================================================================
# SecretManager Tests
# ============================================================================

class TestSecretManager:
    """Test cases for SecretManager."""

    def test_validate_secret_type_valid(self, secret_manager):
        """Test validating valid secret types."""
        secret_manager.validate_secret_type("openai")
        secret_manager.validate_secret_type("keboola")
        # Should not raise any exceptions

    def test_validate_secret_type_invalid(self, secret_manager):
        """Test validating invalid secret type."""
        with pytest.raises(SecretValidationError, match="Invalid secret type"):
            secret_manager.validate_secret_type("invalid_type")

    def test_create_secret(self, secret_manager, sample_secret_data):
        """Test creating a new secret."""
        response = secret_manager.create_secret(sample_secret_data)

        assert response.id > 0
        assert response.name == sample_secret_data.name
        assert response.type == sample_secret_data.type
        assert isinstance(response.created_at, datetime)
        # Value should not be in response
        assert not hasattr(response, 'value') or response.value is None

    def test_create_secret_invalid_type(self, secret_manager):
        """Test creating secret with invalid type."""
        invalid_data = SecretCreate(
            name="test-secret",
            type="invalid",
            value="test-value"
        )

        with pytest.raises(SecretValidationError):
            secret_manager.create_secret(invalid_data)

    def test_create_secret_duplicate_name(self, secret_manager, sample_secret_data):
        """Test that creating duplicate secret name fails."""
        # Create first secret
        secret_manager.create_secret(sample_secret_data)

        # Try to create duplicate
        with pytest.raises(SecretAlreadyExistsError, match="already exists"):
            secret_manager.create_secret(sample_secret_data)

    def test_create_secret_encryption(self, secret_manager, sample_secret_data, db_session):
        """Test that secret value is encrypted in database."""
        response = secret_manager.create_secret(sample_secret_data)

        # Get secret from database
        db_secret = db_session.query(Secret).filter(Secret.id == response.id).first()

        # Encrypted value should be different from original
        assert db_secret.value != sample_secret_data.value
        # But should be decryptable
        decrypted = secret_manager.encryption_service.decrypt(db_secret.value)
        assert decrypted == sample_secret_data.value

    def test_get_secret_by_id(self, secret_manager, sample_secret_data):
        """Test retrieving secret by ID."""
        created = secret_manager.create_secret(sample_secret_data)
        retrieved = secret_manager.get_secret_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == sample_secret_data.name

    def test_get_secret_by_id_not_found(self, secret_manager):
        """Test retrieving non-existent secret by ID."""
        result = secret_manager.get_secret_by_id(99999)
        assert result is None

    def test_get_secret_by_id_with_decrypt(self, secret_manager, sample_secret_data):
        """Test retrieving and decrypting secret by ID."""
        created = secret_manager.create_secret(sample_secret_data)
        retrieved = secret_manager.get_secret_by_id(created.id, decrypt=True)

        assert retrieved is not None
        assert retrieved.value == sample_secret_data.value

    def test_get_secret_by_name(self, secret_manager, sample_secret_data):
        """Test retrieving secret by name."""
        secret_manager.create_secret(sample_secret_data)
        retrieved = secret_manager.get_secret_by_name(sample_secret_data.name)

        assert retrieved is not None
        assert retrieved.name == sample_secret_data.name

    def test_get_secret_by_name_not_found(self, secret_manager):
        """Test retrieving non-existent secret by name."""
        result = secret_manager.get_secret_by_name("non-existent")
        assert result is None

    def test_get_secret_by_name_with_decrypt(self, secret_manager, sample_secret_data):
        """Test retrieving and decrypting secret by name."""
        secret_manager.create_secret(sample_secret_data)
        retrieved = secret_manager.get_secret_by_name(
            sample_secret_data.name,
            decrypt=True
        )

        assert retrieved is not None
        assert retrieved.value == sample_secret_data.value

    def test_get_decrypted_value(self, secret_manager, sample_secret_data):
        """Test getting decrypted value directly."""
        created = secret_manager.create_secret(sample_secret_data)
        value = secret_manager.get_decrypted_value(created.id)

        assert value == sample_secret_data.value

    def test_get_decrypted_value_not_found(self, secret_manager):
        """Test getting decrypted value for non-existent secret."""
        with pytest.raises(SecretNotFoundError):
            secret_manager.get_decrypted_value(99999)

    def test_list_secrets_empty(self, secret_manager):
        """Test listing secrets when database is empty."""
        result = secret_manager.list_secrets()

        assert result.total == 0
        assert len(result.secrets) == 0

    def test_list_secrets(self, secret_manager):
        """Test listing all secrets."""
        # Create multiple secrets
        secret_manager.create_secret(SecretCreate(
            name="openai-1",
            type="openai",
            value="key1"
        ))
        secret_manager.create_secret(SecretCreate(
            name="keboola-1",
            type="keboola",
            value="key2"
        ))

        result = secret_manager.list_secrets()

        assert result.total == 2
        assert len(result.secrets) == 2

    def test_list_secrets_by_type(self, secret_manager):
        """Test listing secrets filtered by type."""
        # Create secrets of different types
        secret_manager.create_secret(SecretCreate(
            name="openai-1",
            type="openai",
            value="key1"
        ))
        secret_manager.create_secret(SecretCreate(
            name="keboola-1",
            type="keboola",
            value="key2"
        ))

        # List only OpenAI secrets
        result = secret_manager.list_secrets(secret_type="openai")

        assert result.total == 1
        assert result.secrets[0].type == "openai"

    def test_list_secrets_pagination(self, secret_manager):
        """Test listing secrets with pagination."""
        # Create multiple secrets
        for i in range(5):
            secret_manager.create_secret(SecretCreate(
                name=f"secret-{i}",
                type="openai",
                value=f"key{i}"
            ))

        # Get first page
        result1 = secret_manager.list_secrets(skip=0, limit=2)
        assert len(result1.secrets) == 2
        assert result1.total == 5

        # Get second page
        result2 = secret_manager.list_secrets(skip=2, limit=2)
        assert len(result2.secrets) == 2
        assert result2.total == 5

        # Ensure different results
        assert result1.secrets[0].id != result2.secrets[0].id

    def test_update_secret(self, secret_manager, sample_secret_data):
        """Test updating secret value."""
        created = secret_manager.create_secret(sample_secret_data)
        new_value = "new-secret-value"

        updated = secret_manager.update_secret(created.id, new_value)

        assert updated.id == created.id
        # Verify new value is stored (encrypted)
        decrypted = secret_manager.get_decrypted_value(created.id)
        assert decrypted == new_value

    def test_update_secret_not_found(self, secret_manager):
        """Test updating non-existent secret."""
        with pytest.raises(SecretNotFoundError):
            secret_manager.update_secret(99999, "new-value")

    def test_delete_secret(self, secret_manager, sample_secret_data):
        """Test deleting a secret."""
        created = secret_manager.create_secret(sample_secret_data)

        # Delete the secret
        secret_manager.delete_secret(created.id)

        # Verify it's deleted
        result = secret_manager.get_secret_by_id(created.id)
        assert result is None

    def test_delete_secret_not_found(self, secret_manager):
        """Test deleting non-existent secret."""
        with pytest.raises(SecretNotFoundError):
            secret_manager.delete_secret(99999)

    def test_delete_secret_in_use(self, secret_manager, sample_secret_data, db_session):
        """Test that deleting secret in use fails."""
        # Create secret
        created = secret_manager.create_secret(sample_secret_data)

        # Create a job that references this secret
        job = PollingJob(
            name="test-job",
            batch_id="batch_123",
            openai_secret_id=created.id,
            keboola_secret_id=created.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_configuration_id="12345",
            status="active"
        )
        db_session.add(job)
        db_session.commit()

        # Try to delete secret
        with pytest.raises(SecretInUseError, match="referenced by"):
            secret_manager.delete_secret(created.id)

    def test_delete_secret_in_use_force(self, secret_manager, sample_secret_data, db_session):
        """Test force deleting secret that is in use."""
        # Create secret
        created = secret_manager.create_secret(sample_secret_data)

        # Create a job that references this secret
        job = PollingJob(
            name="test-job",
            batch_id="batch_123",
            openai_secret_id=created.id,
            keboola_secret_id=created.id,
            keboola_stack_url="https://connection.keboola.com",
            keboola_configuration_id="12345",
            status="active"
        )
        db_session.add(job)
        db_session.commit()

        # Force delete should work
        secret_manager.delete_secret(created.id, force=True)

        # Verify it's deleted
        result = secret_manager.get_secret_by_id(created.id)
        assert result is None

    def test_secret_exists(self, secret_manager, sample_secret_data):
        """Test checking if secret exists."""
        assert secret_manager.secret_exists(sample_secret_data.name) is False

        secret_manager.create_secret(sample_secret_data)

        assert secret_manager.secret_exists(sample_secret_data.name) is True

    def test_get_secrets_by_type(self, secret_manager):
        """Test getting all secrets of a specific type."""
        # Create secrets of different types
        secret_manager.create_secret(SecretCreate(
            name="openai-1",
            type="openai",
            value="key1"
        ))
        secret_manager.create_secret(SecretCreate(
            name="openai-2",
            type="openai",
            value="key2"
        ))
        secret_manager.create_secret(SecretCreate(
            name="keboola-1",
            type="keboola",
            value="key3"
        ))

        openai_secrets = secret_manager.get_secrets_by_type("openai")

        assert len(openai_secrets) == 2
        assert all(s.type == "openai" for s in openai_secrets)

    def test_validate_secret_reference(self, secret_manager, sample_secret_data):
        """Test validating secret reference."""
        created = secret_manager.create_secret(sample_secret_data)

        # Should pass for correct type
        secret_manager.validate_secret_reference(created.id, "openai")

    def test_validate_secret_reference_not_found(self, secret_manager):
        """Test validating non-existent secret reference."""
        with pytest.raises(SecretNotFoundError):
            secret_manager.validate_secret_reference(99999, "openai")

    def test_validate_secret_reference_wrong_type(self, secret_manager, sample_secret_data):
        """Test validating secret reference with wrong type."""
        created = secret_manager.create_secret(sample_secret_data)

        # Should fail for wrong type
        with pytest.raises(SecretValidationError, match="expected type"):
            secret_manager.validate_secret_reference(created.id, "keboola")


# ============================================================================
# Integration Tests
# ============================================================================

class TestSecretsIntegration:
    """Integration tests for the complete secrets workflow."""

    def test_full_secret_lifecycle(self, secret_manager):
        """Test complete secret lifecycle: create, read, update, delete."""
        # Create
        secret_data = SecretCreate(
            name="lifecycle-test",
            type="openai",
            value="initial-value"
        )
        created = secret_manager.create_secret(secret_data)
        assert created.id > 0

        # Read
        retrieved = secret_manager.get_secret_by_id(created.id, decrypt=True)
        assert retrieved.value == "initial-value"

        # Update
        updated = secret_manager.update_secret(created.id, "updated-value")
        assert updated.id == created.id

        # Verify update
        retrieved = secret_manager.get_secret_by_id(created.id, decrypt=True)
        assert retrieved.value == "updated-value"

        # Delete
        secret_manager.delete_secret(created.id)
        assert secret_manager.get_secret_by_id(created.id) is None

    def test_multiple_secret_types(self, secret_manager):
        """Test managing secrets of different types."""
        # Create OpenAI secret
        openai_secret = secret_manager.create_secret(SecretCreate(
            name="openai-prod",
            type="openai",
            value="sk-openai-key"
        ))

        # Create Keboola secret
        keboola_secret = secret_manager.create_secret(SecretCreate(
            name="keboola-prod",
            type="keboola",
            value="keboola-token"
        ))

        # List all secrets
        all_secrets = secret_manager.list_secrets()
        assert all_secrets.total == 2

        # List by type
        openai_only = secret_manager.list_secrets(secret_type="openai")
        assert openai_only.total == 1
        assert openai_only.secrets[0].id == openai_secret.id

        keboola_only = secret_manager.list_secrets(secret_type="keboola")
        assert keboola_only.total == 1
        assert keboola_only.secrets[0].id == keboola_secret.id
