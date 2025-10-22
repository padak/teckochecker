"""
Secrets management service for TeckoChecker.

This module provides the SecretManager class that handles:
- Storing secrets with encryption
- Retrieving and decrypting secrets
- Validating secret types
- CRUD operations for secrets
"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import Secret
from app.schemas import SecretCreate, SecretResponse, SecretListResponse
from app.services.encryption import get_encryption_service


class SecretNotFoundError(Exception):
    """Raised when a secret is not found."""
    pass


class SecretValidationError(Exception):
    """Raised when secret validation fails."""
    pass


class SecretAlreadyExistsError(Exception):
    """Raised when attempting to create a secret with a name that already exists."""
    pass


class SecretInUseError(Exception):
    """Raised when attempting to delete a secret that is referenced by active jobs."""
    pass


class SecretManager:
    """
    Manager for secure secret storage and retrieval.

    This class handles all operations related to secrets including:
    - Creating new secrets with encryption
    - Retrieving secrets (with or without decryption)
    - Updating secret values
    - Deleting secrets (with validation)
    - Listing secrets
    """

    VALID_SECRET_TYPES = {"openai", "keboola"}

    def __init__(self, db: Session):
        """
        Initialize the secret manager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.encryption_service = get_encryption_service()

    def validate_secret_type(self, secret_type: str) -> None:
        """
        Validate that the secret type is supported.

        Args:
            secret_type: Type of secret to validate

        Raises:
            SecretValidationError: If secret type is not valid
        """
        if secret_type not in self.VALID_SECRET_TYPES:
            raise SecretValidationError(
                f"Invalid secret type '{secret_type}'. "
                f"Must be one of: {', '.join(self.VALID_SECRET_TYPES)}"
            )

    def create_secret(self, secret_data: SecretCreate) -> SecretResponse:
        """
        Create a new secret with encryption.

        Args:
            secret_data: Secret creation data including name, type, and value

        Returns:
            SecretResponse with created secret information (without value)

        Raises:
            SecretValidationError: If secret type is invalid
            SecretAlreadyExistsError: If secret name already exists
            SQLAlchemyError: If database operation fails
        """
        # Validate secret type
        self.validate_secret_type(secret_data.type)

        try:
            # Encrypt the secret value
            encrypted_value = self.encryption_service.encrypt(secret_data.value)

            # Create secret model
            secret = Secret(
                name=secret_data.name,
                type=secret_data.type,
                value=encrypted_value,
                created_at=datetime.utcnow()
            )

            # Add to database
            self.db.add(secret)
            self.db.commit()
            self.db.refresh(secret)

            # Return response without the encrypted value
            return SecretResponse.model_validate(secret)

        except IntegrityError as e:
            self.db.rollback()
            if "UNIQUE constraint" in str(e) or "unique" in str(e).lower():
                raise SecretAlreadyExistsError(
                    f"Secret with name '{secret_data.name}' already exists"
                )
            raise SQLAlchemyError(f"Database error: {str(e)}")

        except Exception as e:
            self.db.rollback()
            raise SQLAlchemyError(f"Failed to create secret: {str(e)}")

    def get_secret_by_id(
        self,
        secret_id: int,
        decrypt: bool = False
    ) -> Optional[Secret]:
        """
        Get a secret by ID.

        Args:
            secret_id: ID of the secret to retrieve
            decrypt: If True, decrypt the secret value before returning

        Returns:
            Secret model or None if not found
        """
        secret = self.db.query(Secret).filter(Secret.id == secret_id).first()

        if secret and decrypt:
            # Decrypt the value in memory (don't modify the DB object)
            secret.value = self.encryption_service.decrypt(secret.value)

        return secret

    def get_secret_by_name(
        self,
        name: str,
        decrypt: bool = False
    ) -> Optional[Secret]:
        """
        Get a secret by name.

        Args:
            name: Name of the secret to retrieve
            decrypt: If True, decrypt the secret value before returning

        Returns:
            Secret model or None if not found
        """
        secret = self.db.query(Secret).filter(Secret.name == name).first()

        if secret and decrypt:
            # Decrypt the value in memory (don't modify the DB object)
            secret.value = self.encryption_service.decrypt(secret.value)

        return secret

    def get_decrypted_value(self, secret_id: int) -> str:
        """
        Get the decrypted value of a secret.

        This is a convenience method for getting just the decrypted value.

        Args:
            secret_id: ID of the secret

        Returns:
            Decrypted secret value

        Raises:
            SecretNotFoundError: If secret is not found
        """
        secret = self.get_secret_by_id(secret_id, decrypt=False)
        if not secret:
            raise SecretNotFoundError(f"Secret with id {secret_id} not found")

        return self.encryption_service.decrypt(secret.value)

    def list_secrets(
        self,
        secret_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> SecretListResponse:
        """
        List all secrets (without their values).

        Args:
            secret_type: Optional filter by secret type
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            SecretListResponse with list of secrets and total count

        Raises:
            SecretValidationError: If secret_type filter is invalid
        """
        # Validate type filter if provided
        if secret_type is not None:
            self.validate_secret_type(secret_type)

        # Build query
        query = self.db.query(Secret)

        if secret_type:
            query = query.filter(Secret.type == secret_type)

        # Get total count
        total = query.count()

        # Get paginated results
        secrets = query.order_by(Secret.created_at.desc()).offset(skip).limit(limit).all()

        # Convert to response models
        secret_responses = [SecretResponse.model_validate(s) for s in secrets]

        return SecretListResponse(
            secrets=secret_responses,
            total=total
        )

    def update_secret(
        self,
        secret_id: int,
        new_value: str
    ) -> SecretResponse:
        """
        Update a secret's value.

        Only the value can be updated. To change name or type, delete and recreate.

        Args:
            secret_id: ID of the secret to update
            new_value: New secret value (will be encrypted)

        Returns:
            Updated SecretResponse

        Raises:
            SecretNotFoundError: If secret is not found
            SQLAlchemyError: If database operation fails
        """
        secret = self.get_secret_by_id(secret_id, decrypt=False)
        if not secret:
            raise SecretNotFoundError(f"Secret with id {secret_id} not found")

        try:
            # Encrypt new value
            encrypted_value = self.encryption_service.encrypt(new_value)

            # Update secret
            secret.value = encrypted_value

            self.db.commit()
            self.db.refresh(secret)

            return SecretResponse.model_validate(secret)

        except Exception as e:
            self.db.rollback()
            raise SQLAlchemyError(f"Failed to update secret: {str(e)}")

    def delete_secret(self, secret_id: int, force: bool = False) -> None:
        """
        Delete a secret.

        By default, prevents deletion of secrets that are referenced by jobs.
        Use force=True to override this check (not recommended).

        Args:
            secret_id: ID of the secret to delete
            force: If True, skip the "in use" check

        Raises:
            SecretNotFoundError: If secret is not found
            SecretInUseError: If secret is referenced by active jobs
            SQLAlchemyError: If database operation fails
        """
        secret = self.get_secret_by_id(secret_id, decrypt=False)
        if not secret:
            raise SecretNotFoundError(f"Secret with id {secret_id} not found")

        # Check if secret is in use (unless force is True)
        if not force:
            # Check if secret is referenced by any jobs
            jobs_using_secret = (
                len(secret.jobs_as_openai) + len(secret.jobs_as_keboola)
            )

            if jobs_using_secret > 0:
                raise SecretInUseError(
                    f"Cannot delete secret '{secret.name}': "
                    f"it is referenced by {jobs_using_secret} job(s). "
                    f"Delete the jobs first or use force=True."
                )

        try:
            self.db.delete(secret)
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise SQLAlchemyError(f"Failed to delete secret: {str(e)}")

    def secret_exists(self, name: str) -> bool:
        """
        Check if a secret with the given name exists.

        Args:
            name: Secret name to check

        Returns:
            True if secret exists, False otherwise
        """
        return self.db.query(Secret).filter(Secret.name == name).count() > 0

    def get_secrets_by_type(self, secret_type: str) -> List[Secret]:
        """
        Get all secrets of a specific type.

        Args:
            secret_type: Type of secrets to retrieve

        Returns:
            List of Secret models (without decrypted values)

        Raises:
            SecretValidationError: If secret type is invalid
        """
        self.validate_secret_type(secret_type)

        return self.db.query(Secret).filter(Secret.type == secret_type).all()

    def validate_secret_reference(
        self,
        secret_id: int,
        expected_type: str
    ) -> None:
        """
        Validate that a secret exists and has the expected type.

        This is useful when creating jobs to ensure the secret IDs are valid
        and of the correct type.

        Args:
            secret_id: ID of the secret to validate
            expected_type: Expected type of the secret

        Raises:
            SecretNotFoundError: If secret is not found
            SecretValidationError: If secret type doesn't match expected type
        """
        self.validate_secret_type(expected_type)

        secret = self.get_secret_by_id(secret_id, decrypt=False)
        if not secret:
            raise SecretNotFoundError(f"Secret with id {secret_id} not found")

        if secret.type != expected_type:
            raise SecretValidationError(
                f"Secret '{secret.name}' has type '{secret.type}', "
                f"but expected type '{expected_type}'"
            )


def get_secret_manager(db: Session) -> SecretManager:
    """
    Get a SecretManager instance.

    This is a convenience function for dependency injection in FastAPI.

    Args:
        db: Database session

    Returns:
        SecretManager instance

    Example:
        @app.post("/secrets")
        def create_secret(
            secret: SecretCreate,
            db: Session = Depends(get_db),
            manager: SecretManager = Depends(get_secret_manager)
        ):
            return manager.create_secret(secret)
    """
    return SecretManager(db)
