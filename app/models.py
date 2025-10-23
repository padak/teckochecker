"""
SQLAlchemy models for TeckoChecker.
Defines the database schema for secrets, polling jobs, and polling logs.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Secret(Base):
    """
    Model for storing encrypted API keys and tokens.

    Attributes:
        id: Primary key
        name: Unique name for the secret
        type: Type of secret ('openai', 'keboola')
        value: Encrypted secret value
        created_at: Timestamp when secret was created
    """

    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    openai_jobs: Mapped[list["PollingJob"]] = relationship(
        "PollingJob",
        back_populates="openai_secret",
        foreign_keys="PollingJob.openai_secret_id",
        cascade="all, delete-orphan",
    )
    keboola_jobs: Mapped[list["PollingJob"]] = relationship(
        "PollingJob",
        back_populates="keboola_secret",
        foreign_keys="PollingJob.keboola_secret_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Secret(id={self.id}, name='{self.name}', type='{self.type}')>"


class JobBatch(Base):
    """
    Model for individual batch IDs monitored by a polling job.

    Attributes:
        id: Primary key
        job_id: Foreign key to polling job
        batch_id: OpenAI batch job ID (e.g., 'batch_abc123')
        status: Current OpenAI batch status ('in_progress', 'completed', 'failed', 'cancelled', 'expired')
        created_at: When this batch was added to the job
        completed_at: When the batch reached terminal state
    """

    __tablename__ = "job_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("polling_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    batch_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="in_progress")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    job: Mapped["PollingJob"] = relationship("PollingJob", back_populates="batches")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_batch_job_id", "job_id"),
        Index("idx_batch_batch_id", "batch_id"),
        Index("idx_batch_status", "status"),
        # Ensure no duplicate batch_ids within same job
        Index("idx_batch_job_batch_unique", "job_id", "batch_id", unique=True),
        # Check constraint for format (SQLite 3.38+)
        CheckConstraint(
            "batch_id LIKE 'batch_%'",
            name="check_batch_id_format"
        ),
        # Length constraint
        CheckConstraint(
            "LENGTH(batch_id) <= 255",
            name="check_batch_id_length"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<JobBatch(id={self.id}, job_id={self.job_id}, "
            f"batch_id='{self.batch_id}', status='{self.status}')>"
        )

    @property
    def is_terminal(self) -> bool:
        """Check if batch is in terminal state (completed, failed, cancelled, expired)."""
        return self.status in {"completed", "failed", "cancelled", "expired"}

    @property
    def is_completed(self) -> bool:
        """Check if batch completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if batch failed (any terminal state except completed)."""
        return self.status in {"failed", "cancelled", "expired"}


class PollingJob(Base):
    """
    Model for polling jobs that monitor OpenAI batch jobs.

    NEW: Supports multiple batch_ids via JobBatch relationship
    REMOVED: batch_id column (replaced by batches relationship)

    Attributes:
        id: Primary key
        name: Human-readable name for the job
        openai_secret_id: Foreign key to OpenAI secret
        keboola_secret_id: Foreign key to Keboola secret
        keboola_stack_url: Keboola Connection stack URL
        keboola_component_id: Keboola component ID (e.g., 'kds-team.app-custom-python')
        keboola_configuration_id: Keboola configuration to trigger
        poll_interval_seconds: How often to check status (in seconds)
        status: Current job status ('active', 'paused', 'completed', 'failed', 'completed_with_failures')
        last_check_at: When the job was last checked
        next_check_at: When the job should be checked next
        created_at: When the job was created
        completed_at: When the job was completed (if applicable)
    """

    __tablename__ = "polling_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Foreign keys
    openai_secret_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("secrets.id", ondelete="SET NULL"), nullable=True
    )
    keboola_secret_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("secrets.id", ondelete="SET NULL"), nullable=True
    )

    # Keboola configuration
    keboola_stack_url: Mapped[str] = mapped_column(String(500), nullable=False)
    keboola_component_id: Mapped[str] = mapped_column(String(255), nullable=False)
    keboola_configuration_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Polling configuration
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)

    # Job status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)

    # Timestamps
    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    openai_secret: Mapped[Optional["Secret"]] = relationship(
        "Secret", back_populates="openai_jobs", foreign_keys=[openai_secret_id]
    )
    keboola_secret: Mapped[Optional["Secret"]] = relationship(
        "Secret", back_populates="keboola_jobs", foreign_keys=[keboola_secret_id]
    )
    logs: Mapped[list["PollingLog"]] = relationship(
        "PollingLog",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PollingLog.created_at.desc()",
    )
    # NEW: Multi-batch relationship
    batches: Mapped[list["JobBatch"]] = relationship(
        "JobBatch",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobBatch.created_at",
        lazy="joined",  # Eager loading to avoid N+1 queries
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_job_status_next_check", "status", "next_check_at"),
    )

    def __repr__(self) -> str:
        batch_count = len(self.batches) if hasattr(self, 'batches') else 0
        return (
            f"<PollingJob(id={self.id}, name='{self.name}', "
            f"batch_count={batch_count}, status='{self.status}')>"
        )

    @property
    def is_active(self) -> bool:
        """Check if the job is currently active."""
        return self.status == "active"

    @property
    def is_completed(self) -> bool:
        """Check if the job is completed."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if the job has failed."""
        return self.status == "failed"

    @property
    def is_paused(self) -> bool:
        """Check if the job is paused."""
        return self.status == "paused"

    # NEW: Multi-batch helper properties
    @property
    def all_batches_terminal(self) -> bool:
        """Check if ALL batches are in terminal state."""
        if not self.batches:
            return False
        return all(batch.is_terminal for batch in self.batches)

    @property
    def completed_batches(self) -> list["JobBatch"]:
        """Get list of successfully completed batches."""
        return [b for b in self.batches if b.is_completed]

    @property
    def failed_batches(self) -> list["JobBatch"]:
        """Get list of failed batches (failed/cancelled/expired)."""
        return [b for b in self.batches if b.is_failed]

    @property
    def batch_completion_summary(self) -> dict:
        """Get summary of batch completion status."""
        return {
            "total": len(self.batches),
            "completed": len(self.completed_batches),
            "failed": len(self.failed_batches),
            "in_progress": len([b for b in self.batches if not b.is_terminal]),
        }


class PollingLog(Base):
    """
    Model for logging polling job checks and results.

    Attributes:
        id: Primary key
        job_id: Foreign key to polling job
        status: Status at time of log ('checking', 'pending', 'completed', 'failed', 'error')
        message: Log message with details
        created_at: When the log entry was created
    """

    __tablename__ = "polling_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("polling_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    job: Mapped["PollingJob"] = relationship("PollingJob", back_populates="logs")

    # Indexes for efficient log queries
    __table_args__ = (
        Index("idx_log_job_created", "job_id", "created_at"),
        Index("idx_log_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PollingLog(id={self.id}, job_id={self.job_id}, "
            f"status='{self.status}', created_at={self.created_at})>"
        )


# Valid status values for documentation and validation
SECRET_TYPES = ["openai", "keboola"]
JOB_STATUSES = ["active", "paused", "completed", "failed", "completed_with_failures"]
LOG_STATUSES = ["checking", "pending", "completed", "failed", "error", "triggered"]
BATCH_STATUSES = ["in_progress", "completed", "failed", "cancelled", "expired"]
