"""Jobs API endpoints for polling job management."""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.rate_limiter import limiter, get_limit_for_endpoint
from app.models import PollingJob, Secret, PollingLog, JobBatch
from app.schemas import (
    PollingJobCreate,
    PollingJobUpdate,
    PollingJobResponse,
    PollingJobListResponse,
    PollingJobDetailResponse,
    MessageResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=PollingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new polling job",
    description="Create a new job to poll OpenAI batch status and trigger Keboola job",
)
@limiter.limit(get_limit_for_endpoint("POST"))
async def create_job(request: Request, job_data: PollingJobCreate, db: Session = Depends(get_db)):
    """
    Create a new polling job with multiple batch IDs.

    BREAKING CHANGE: Now accepts batch_ids (array) instead of batch_id (string).

    Args:
        job_data: Job creation data with batch_ids array
        db: Database session

    Returns:
        Created job details with batches array and computed counts

    Raises:
        404 Not Found: If referenced secrets don't exist
    """
    # Validate that secrets exist
    openai_secret = (
        db.query(Secret)
        .filter(Secret.id == job_data.openai_secret_id, Secret.type == "openai")
        .first()
    )

    if not openai_secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OpenAI secret with ID {job_data.openai_secret_id} not found",
            headers={"X-Error-Code": "1001"},
        )

    keboola_secret = (
        db.query(Secret)
        .filter(Secret.id == job_data.keboola_secret_id, Secret.type == "keboola")
        .first()
    )

    if not keboola_secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keboola secret with ID {job_data.keboola_secret_id} not found",
            headers={"X-Error-Code": "1001"},
        )

    # Create job (without batch_id field)
    job = PollingJob(
        name=job_data.name,
        openai_secret_id=job_data.openai_secret_id,
        keboola_secret_id=job_data.keboola_secret_id,
        keboola_stack_url=job_data.keboola_stack_url,
        keboola_component_id=job_data.keboola_component_id,
        keboola_configuration_id=job_data.keboola_configuration_id,
        poll_interval_seconds=job_data.poll_interval_seconds,
        status="active",
        next_check_at=datetime.now(timezone.utc),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Create JobBatch records for each batch_id
    for batch_id in job_data.batch_ids:
        batch = JobBatch(
            job_id=job.id,
            batch_id=batch_id,
            status="in_progress",
        )
        db.add(batch)

    db.commit()
    db.refresh(job)

    # Create initial log entry
    batch_ids_str = ", ".join(job_data.batch_ids)
    log = PollingLog(
        job_id=job.id,
        status="created",
        message=f"Job created with {len(job_data.batch_ids)} batch(es): {batch_ids_str}. "
        f"Poll interval: {job.poll_interval_seconds}s",
    )
    db.add(log)
    db.commit()

    # Add secret names to the response
    job.openai_secret_name = openai_secret.name
    job.keboola_secret_name = keboola_secret.name

    logger.info(
        f"Created polling job: {job.name} (ID: {job.id}) with {len(job_data.batch_ids)} batch(es)"
    )

    # Use custom from_orm to compute batch counts
    return PollingJobResponse.from_orm(job)


@router.get(
    "",
    response_model=PollingJobListResponse,
    summary="List all polling jobs",
    description="Get a list of all polling jobs with optional status filtering",
)
@limiter.limit(get_limit_for_endpoint("GET"))
async def list_jobs(
    request: Request,
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter jobs by status: active, paused, completed, failed"
    ),
    db: Session = Depends(get_db),
):
    """
    List all polling jobs with batches array and computed counts.

    Batches are eager-loaded via lazy="joined" in model relationship.

    Args:
        status_filter: Optional status filter
        db: Database session

    Returns:
        List of jobs with batches array, batch counts, and total count
    """
    query = db.query(PollingJob)

    if status_filter:
        query = query.filter(PollingJob.status == status_filter)

    jobs = query.order_by(PollingJob.created_at.desc()).all()

    # Convert each job using custom from_orm
    job_responses = [PollingJobResponse.from_orm(job) for job in jobs]

    return PollingJobListResponse(jobs=job_responses, total=len(job_responses))


@router.get(
    "/{job_id}",
    response_model=PollingJobDetailResponse,
    summary="Get job details",
    description="Get detailed information about a specific job including batches and logs",
)
@limiter.limit(get_limit_for_endpoint("GET"))
async def get_job(
    request: Request,
    job_id: int,
    include_logs: bool = Query(True, description="Include job logs in response"),
    log_limit: int = Query(50, ge=1, le=500, description="Maximum number of logs to return"),
    db: Session = Depends(get_db),
):
    """
    Get job details by ID with batches array and computed counts.

    Args:
        job_id: Job ID
        include_logs: Whether to include logs
        log_limit: Maximum number of logs to return
        db: Database session

    Returns:
        Job details with batches array, computed counts, and optional logs

    Raises:
        404 Not Found: If job doesn't exist
    """
    job = db.query(PollingJob).filter(PollingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
            headers={"X-Error-Code": "1002"},
        )

    # Get secret names
    openai_secret = db.query(Secret).filter(Secret.id == job.openai_secret_id).first()
    keboola_secret = db.query(Secret).filter(Secret.id == job.keboola_secret_id).first()

    # Add secret names as attributes for from_orm
    job.openai_secret_name = openai_secret.name if openai_secret else None
    job.keboola_secret_name = keboola_secret.name if keboola_secret else None

    # Get logs if requested
    logs = []
    if include_logs:
        logs = (
            db.query(PollingLog)
            .filter(PollingLog.job_id == job_id)
            .order_by(PollingLog.created_at.desc())
            .limit(log_limit)
            .all()
        )

    # Get batches (eager-loaded via lazy="joined")
    batches = job.batches if hasattr(job, "batches") else []

    # Compute batch statistics
    batch_count = len(batches)
    completed_count = sum(1 for b in batches if b.status == "completed")
    failed_count = sum(1 for b in batches if b.status in {"failed", "cancelled", "expired"})

    # Build response dict with all fields
    job_dict = {
        "id": job.id,
        "name": job.name,
        "batches": batches,
        "batch_count": batch_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "openai_secret_id": job.openai_secret_id,
        "openai_secret_name": openai_secret.name if openai_secret else None,
        "keboola_secret_id": job.keboola_secret_id,
        "keboola_secret_name": keboola_secret.name if keboola_secret else None,
        "keboola_stack_url": job.keboola_stack_url,
        "keboola_component_id": job.keboola_component_id,
        "keboola_configuration_id": job.keboola_configuration_id,
        "poll_interval_seconds": job.poll_interval_seconds,
        "status": job.status,
        "last_check_at": job.last_check_at,
        "next_check_at": job.next_check_at,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "logs": logs,
    }

    return PollingJobDetailResponse(**job_dict)


@router.put(
    "/{job_id}",
    response_model=PollingJobResponse,
    summary="Update a job",
    description="Update job configuration (name, intervals, Keboola settings)",
)
@limiter.limit(get_limit_for_endpoint("PUT"))
async def update_job(request: Request, job_id: int, job_update: PollingJobUpdate, db: Session = Depends(get_db)):
    """
    Update a polling job.

    Only allows updating certain fields. Cannot change batch_id or secrets.

    Args:
        job_id: Job ID
        job_update: Fields to update
        db: Database session

    Returns:
        Updated job details

    Raises:
        404 Not Found: If job doesn't exist
    """
    job = db.query(PollingJob).filter(PollingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
            headers={"X-Error-Code": "1002"},
        )

    # Update fields
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)

    # Log the update
    log = PollingLog(
        job_id=job.id, status="updated", message=f"Job updated: {', '.join(update_data.keys())}"
    )
    db.add(log)
    db.commit()

    logger.info(f"Updated job {job_id}: {update_data}")

    # Add secret names for response
    openai_secret = db.query(Secret).filter(Secret.id == job.openai_secret_id).first()
    keboola_secret = db.query(Secret).filter(Secret.id == job.keboola_secret_id).first()
    job.openai_secret_name = openai_secret.name if openai_secret else None
    job.keboola_secret_name = keboola_secret.name if keboola_secret else None

    return PollingJobResponse.from_orm(job)


@router.delete(
    "/{job_id}",
    response_model=MessageResponse,
    summary="Delete a job",
    description="Delete a polling job and its logs",
)
@limiter.limit(get_limit_for_endpoint("DELETE"))
async def delete_job(request: Request, job_id: int, db: Session = Depends(get_db)):
    """
    Delete a polling job.

    This will also delete all associated logs due to CASCADE.

    Args:
        job_id: Job ID to delete
        db: Database session

    Returns:
        Success message

    Raises:
        404 Not Found: If job doesn't exist
    """
    job = db.query(PollingJob).filter(PollingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
            headers={"X-Error-Code": "1002"},
        )

    job_name = job.name
    db.delete(job)
    db.commit()

    logger.info(f"Deleted job: {job_name} (ID: {job_id})")
    return MessageResponse(message=f"Job '{job_name}' deleted successfully", success=True)


@router.post(
    "/{job_id}/pause",
    response_model=PollingJobResponse,
    summary="Pause a job",
    description="Pause an active polling job",
)
@limiter.limit(get_limit_for_endpoint("POST"))
async def pause_job(request: Request, job_id: int, db: Session = Depends(get_db)):
    """
    Pause a polling job.

    Args:
        job_id: Job ID to pause
        db: Database session

    Returns:
        Updated job details

    Raises:
        404 Not Found: If job doesn't exist
        409 Conflict: If job is not active
    """
    job = db.query(PollingJob).filter(PollingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
            headers={"X-Error-Code": "1002"},
        )

    if job.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot pause job with status '{job.status}'. Only active jobs can be paused.",
        )

    job.status = "paused"
    db.commit()
    db.refresh(job)

    # Log the pause
    log = PollingLog(job_id=job.id, status="paused", message="Job paused by user")
    db.add(log)
    db.commit()

    logger.info(f"Paused job: {job.name} (ID: {job_id})")

    # Add secret names for response
    openai_secret = db.query(Secret).filter(Secret.id == job.openai_secret_id).first()
    keboola_secret = db.query(Secret).filter(Secret.id == job.keboola_secret_id).first()
    job.openai_secret_name = openai_secret.name if openai_secret else None
    job.keboola_secret_name = keboola_secret.name if keboola_secret else None

    return PollingJobResponse.from_orm(job)


@router.post(
    "/{job_id}/resume",
    response_model=PollingJobResponse,
    summary="Resume a job",
    description="Resume a paused polling job",
)
@limiter.limit(get_limit_for_endpoint("POST"))
async def resume_job(request: Request, job_id: int, db: Session = Depends(get_db)):
    """
    Resume a paused polling job.

    Args:
        job_id: Job ID to resume
        db: Database session

    Returns:
        Updated job details

    Raises:
        404 Not Found: If job doesn't exist
        409 Conflict: If job is not paused
    """
    job = db.query(PollingJob).filter(PollingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found",
            headers={"X-Error-Code": "1002"},
        )

    if job.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot resume job with status '{job.status}'. Only paused jobs can be resumed.",
        )

    job.status = "active"
    job.next_check_at = datetime.now(timezone.utc)  # Schedule immediate check
    db.commit()
    db.refresh(job)

    # Log the resume
    log = PollingLog(job_id=job.id, status="resumed", message="Job resumed by user")
    db.add(log)
    db.commit()

    logger.info(f"Resumed job: {job.name} (ID: {job_id})")

    # Add secret names for response
    openai_secret = db.query(Secret).filter(Secret.id == job.openai_secret_id).first()
    keboola_secret = db.query(Secret).filter(Secret.id == job.keboola_secret_id).first()
    job.openai_secret_name = openai_secret.name if openai_secret else None
    job.keboola_secret_name = keboola_secret.name if keboola_secret else None

    return PollingJobResponse.from_orm(job)
