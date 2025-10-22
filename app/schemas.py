"""Pydantic schemas for request validation and response serialization."""

from datetime import datetime
from typing import Optional, List
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


class PollingJobCreate(BaseModel):
    """Schema for creating a new polling job."""

    name: str = Field(..., min_length=1, max_length=255, description="Job name")
    batch_id: str = Field(..., min_length=1, max_length=255, description="OpenAI batch ID")
    openai_secret_id: int = Field(..., gt=0, description="ID of OpenAI secret")
    keboola_secret_id: int = Field(..., gt=0, description="ID of Keboola secret")
    keboola_stack_url: str = Field(..., min_length=1, description="Keboola stack URL")
    keboola_component_id: str = Field(..., min_length=1, description="Keboola component ID")
    keboola_configuration_id: str = Field(..., min_length=1, description="Keboola configuration ID")
    poll_interval_seconds: int = Field(
        default=120, ge=30, le=3600, description="Polling interval in seconds (30-3600)"
    )


class PollingJobUpdate(BaseModel):
    """Schema for updating a polling job."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    keboola_stack_url: Optional[str] = Field(None, min_length=1)
    keboola_component_id: Optional[str] = Field(None, min_length=1)
    keboola_configuration_id: Optional[str] = Field(None, min_length=1)
    poll_interval_seconds: Optional[int] = Field(None, ge=30, le=3600)


class PollingJobResponse(BaseModel):
    """Schema for polling job response."""

    id: int
    name: str
    batch_id: str
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
