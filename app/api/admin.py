"""Admin API endpoints for secrets management."""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Secret, PollingJob
from app.schemas import (
    SecretCreate,
    SecretResponse,
    SecretListResponse,
    MessageResponse,
    ErrorResponse
)
from app.services.encryption import get_encryption_service


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/secrets",
    response_model=SecretResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new secret",
    description="Store a new encrypted secret (OpenAI or Keboola API key)"
)
async def create_secret(
    secret_data: SecretCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new secret.
    
    The secret value will be encrypted before storing in the database.
    Secret names must be unique.
    
    Args:
        secret_data: Secret creation data
        db: Database session
        
    Returns:
        Created secret (without the encrypted value)
        
    Raises:
        409 Conflict: If a secret with the same name already exists
        500 Internal Server Error: If encryption fails
    """
    try:
        # Encrypt the secret value
        encryption_service = get_encryption_service()
        encrypted_value = encryption_service.encrypt(secret_data.value)
        
        # Create secret record
        secret = Secret(
            name=secret_data.name,
            type=secret_data.type,
            value=encrypted_value
        )
        
        db.add(secret)
        db.commit()
        db.refresh(secret)
        
        logger.info(f"Created secret: {secret.name} (type: {secret.type})")
        return secret
        
    except IntegrityError:
        db.rollback()
        logger.warning(f"Attempted to create duplicate secret: {secret_data.name}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Secret with name '{secret_data.name}' already exists"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create secret: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create secret",
            headers={"X-Error-Code": "3002"}
        )


@router.get(
    "/secrets",
    response_model=SecretListResponse,
    summary="List all secrets",
    description="Get a list of all secrets (without their values)"
)
async def list_secrets(db: Session = Depends(get_db)):
    """
    List all secrets.
    
    Returns secret metadata without the encrypted values.
    
    Args:
        db: Database session
        
    Returns:
        List of secrets with total count
    """
    secrets = db.query(Secret).order_by(Secret.created_at.desc()).all()
    
    return SecretListResponse(
        secrets=secrets,
        total=len(secrets)
    )


@router.get(
    "/secrets/{secret_id}",
    response_model=SecretResponse,
    summary="Get secret details",
    description="Get details of a specific secret (without the value)"
)
async def get_secret(
    secret_id: int,
    db: Session = Depends(get_db)
):
    """
    Get secret details by ID.
    
    Args:
        secret_id: Secret ID
        db: Database session
        
    Returns:
        Secret details (without the encrypted value)
        
    Raises:
        404 Not Found: If secret doesn't exist
    """
    secret = db.query(Secret).filter(Secret.id == secret_id).first()
    
    if not secret:
        logger.warning(f"Secret not found: {secret_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found",
            headers={"X-Error-Code": "1001"}
        )
    
    return secret


@router.delete(
    "/secrets/{secret_id}",
    response_model=MessageResponse,
    summary="Delete a secret",
    description="Delete a secret if it's not referenced by any active jobs"
)
async def delete_secret(
    secret_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a secret.
    
    Secrets cannot be deleted if they are referenced by active polling jobs.
    
    Args:
        secret_id: Secret ID to delete
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        404 Not Found: If secret doesn't exist
        409 Conflict: If secret is referenced by active jobs
    """
    secret = db.query(Secret).filter(Secret.id == secret_id).first()
    
    if not secret:
        logger.warning(f"Attempted to delete non-existent secret: {secret_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found",
            headers={"X-Error-Code": "1001"}
        )
    
    # Check if secret is referenced by any active jobs
    jobs_using_secret = db.query(PollingJob).filter(
        ((PollingJob.openai_secret_id == secret_id) | 
         (PollingJob.keboola_secret_id == secret_id)) &
        (PollingJob.status.in_(["active", "paused"]))
    ).all()
    
    if jobs_using_secret:
        job_ids = [job.id for job in jobs_using_secret]
        logger.warning(
            f"Attempted to delete secret {secret_id} referenced by jobs: {job_ids}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete secret. It is referenced by active jobs: {job_ids}"
        )
    
    # Delete the secret
    db.delete(secret)
    db.commit()
    
    logger.info(f"Deleted secret: {secret.name} (ID: {secret_id})")
    return MessageResponse(
        message=f"Secret '{secret.name}' deleted successfully",
        success=True
    )
