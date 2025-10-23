"""Pydantic schemas for request validation and response serialization."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Secret Schemas
# ============================================================================


class SecretCreate(BaseModel):
    """Schema for creating a new secret."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique name for the secret")
    type: str = Field(..., description="Type of secret: 'openai' or 'keboola'")
    value: str = Field(..., min_length=1, description="The secret value (will be encrypted)")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate that type is either 'openai' or 'keboola'."""
        if v not in ["openai", "keboola"]:
            raise ValueError("Type must be either 'openai' or 'keboola'")
        return v


class SecretResponse(BaseModel):
    """Schema for secret response (without the actual value)."""

    id: int
    name: str
    type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SecretListResponse(BaseModel):
    """Schema for listing secrets."""

    secrets: List[SecretResponse]
    total: int


# ============================================================================
# Polling Job Schemas
# ============================================================================


class JobBatchSchema(BaseModel):
    """Schema for individual batch within a job."""
    id: int
    batch_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PollingJobCreate(BaseModel):
    """
    Schema for creating a new polling job.

    BREAKING CHANGE: batch_id (str) → batch_ids (List[str])
    """

    name: str = Field(..., min_length=1, max_length=255, description="Job name")
    batch_ids: List[str] = Field(..., min_length=1, max_length=10, description="List of OpenAI batch IDs (1-10)")
    openai_secret_id: int = Field(..., gt=0, description="ID of OpenAI secret")
    keboola_secret_id: int = Field(..., gt=0, description="ID of Keboola secret")
    keboola_stack_url: str = Field(..., min_length=1, description="Keboola stack URL")
    keboola_component_id: str = Field(..., min_length=1, description="Keboola component ID")
    keboola_configuration_id: str = Field(..., min_length=1, description="Keboola configuration ID")
    poll_interval_seconds: int = Field(
        default=120, ge=30, le=3600, description="Polling interval in seconds (30-3600)"
    )

    @field_validator("batch_ids")
    @classmethod
    def validate_batch_ids(cls, v: List[str]) -> List[str]:
        """
        Validate batch_ids array:
        - No duplicates
        - Valid batch_id format (starts with 'batch_')
        - Character whitelist: [a-zA-Z0-9_-]
        - Max 255 chars per ID
        """
        if len(v) != len(set(v)):
            raise ValueError("Duplicate batch IDs are not allowed")

        for batch_id in v:
            # Format validation
            if not batch_id.startswith("batch_"):
                raise ValueError(
                    f"Invalid batch ID format: '{batch_id}' (must start with 'batch_')"
                )

            # Character whitelist (prevents injection attacks)
            allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
            if not all(c in allowed_chars for c in batch_id):
                raise ValueError(
                    f"Batch ID '{batch_id}' contains invalid characters. "
                    f"Only alphanumeric, underscore, and hyphen allowed."
                )

            # Length limit
            if len(batch_id) > 255:
                raise ValueError(f"Batch ID '{batch_id}' exceeds 255 character limit")

            # Minimum length (prevent empty string after prefix)
            if len(batch_id) <= 6:  # "batch_" is 6 chars
                raise ValueError(
                    f"Batch ID '{batch_id}' too short (must have content after 'batch_')"
                )

        return v


class PollingJobUpdate(BaseModel):
    """Schema for updating a polling job."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    keboola_stack_url: Optional[str] = Field(None, min_length=1)
    keboola_component_id: Optional[str] = Field(None, min_length=1)
    keboola_configuration_id: Optional[str] = Field(None, min_length=1)
    poll_interval_seconds: Optional[int] = Field(None, ge=30, le=3600)


class PollingJobResponse(BaseModel):
    """
    Schema for polling job response.

    BREAKING CHANGE: batch_id (str) → batches (List[JobBatchSchema])
    Added computed fields: batch_count, completed_count, failed_count
    """

    id: int
    name: str
    batches: List[JobBatchSchema] = []
    batch_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    openai_secret_id: int
    openai_secret_name: Optional[str] = None
    keboola_secret_id: int
    keboola_secret_name: Optional[str] = None
    keboola_stack_url: str
    keboola_component_id: str
    keboola_configuration_id: str
    poll_interval_seconds: int
    status: str
    last_check_at: Optional[datetime]
    next_check_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj: Any) -> "PollingJobResponse":
        """
        Custom from_orm to compute batch counts from batches relationship.

        Args:
            obj: PollingJob model instance

        Returns:
            PollingJobResponse with computed batch statistics
        """
        # Get batches list
        batches = obj.batches if hasattr(obj, "batches") else []

        # Compute statistics
        batch_count = len(batches)
        completed_count = sum(1 for b in batches if b.status == "completed")
        failed_count = sum(
            1 for b in batches if b.status in {"failed", "cancelled", "expired"}
        )

        # Build response dict
        data = {
            "id": obj.id,
            "name": obj.name,
            "batches": batches,
            "batch_count": batch_count,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "openai_secret_id": obj.openai_secret_id,
            "openai_secret_name": getattr(obj, "openai_secret_name", None),
            "keboola_secret_id": obj.keboola_secret_id,
            "keboola_secret_name": getattr(obj, "keboola_secret_name", None),
            "keboola_stack_url": obj.keboola_stack_url,
            "keboola_component_id": obj.keboola_component_id,
            "keboola_configuration_id": obj.keboola_configuration_id,
            "poll_interval_seconds": obj.poll_interval_seconds,
            "status": obj.status,
            "last_check_at": obj.last_check_at,
            "next_check_at": obj.next_check_at,
            "created_at": obj.created_at,
            "completed_at": obj.completed_at,
        }

        return cls(**data)


class PollingJobListResponse(BaseModel):
    """Schema for listing polling jobs."""

    jobs: List[PollingJobResponse]
    total: int


# ============================================================================
# Polling Log Schemas
# ============================================================================


class PollingLogResponse(BaseModel):
    """Schema for polling log response."""

    id: int
    job_id: int
    status: str
    message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PollingJobDetailResponse(PollingJobResponse):
    """Schema for detailed job response with logs."""

    logs: List[PollingLogResponse] = []


# ============================================================================
# System Schemas
# ============================================================================


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str = Field(..., description="Health status: 'healthy' or 'unhealthy'")
    timestamp: datetime
    database: str = Field(..., description="Database connection status")
    version: str = Field(default="0.1.0", description="API version")


class StatsResponse(BaseModel):
    """Schema for system statistics response."""

    total_jobs: int
    active_jobs: int
    paused_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_secrets: int
    total_logs: int
    uptime_seconds: Optional[float] = None


# ============================================================================
# Error Schemas
# ============================================================================


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    code: Optional[int] = Field(None, description="Application-specific error code")


class ValidationErrorDetail(BaseModel):
    """Schema for validation error details."""

    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    """Schema for validation error responses."""

    error: str = "validation_error"
    message: str
    details: List[ValidationErrorDetail]


# ============================================================================
# Generic Response Schemas
# ============================================================================


class MessageResponse(BaseModel):
    """Schema for simple message responses."""

    message: str
    success: bool = True
