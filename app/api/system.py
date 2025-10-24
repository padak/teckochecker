"""System API endpoints for health checks and statistics."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.database import get_db
from app.rate_limiter import limiter, get_limit_for_endpoint
from app.models import PollingJob, Secret, PollingLog
from app.schemas import HealthResponse, StatsResponse


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and database",
)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.

    Returns the health status of the API and database connection.

    Args:
        db: Database session

    Returns:
        Health status information
    """
    # Test database connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
        overall_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        database=db_status,
        version="0.1.0",
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="System statistics",
    description="Get system statistics including job counts and database metrics",
)
@limiter.limit(get_limit_for_endpoint("GET"))
async def get_stats(request: Request, db: Session = Depends(get_db)):
    """
    Get system statistics.

    Returns counts of jobs by status, secrets, and logs.

    Args:
        db: Database session

    Returns:
        System statistics
    """
    # Count jobs by status
    total_jobs = db.query(func.count(PollingJob.id)).scalar() or 0
    active_jobs = (
        db.query(func.count(PollingJob.id)).filter(PollingJob.status == "active").scalar() or 0
    )
    paused_jobs = (
        db.query(func.count(PollingJob.id)).filter(PollingJob.status == "paused").scalar() or 0
    )
    completed_jobs = (
        db.query(func.count(PollingJob.id)).filter(PollingJob.status == "completed").scalar() or 0
    )
    failed_jobs = (
        db.query(func.count(PollingJob.id)).filter(PollingJob.status == "failed").scalar() or 0
    )

    # Count secrets
    total_secrets = db.query(func.count(Secret.id)).scalar() or 0

    # Count logs
    total_logs = db.query(func.count(PollingLog.id)).scalar() or 0

    # Calculate uptime (if app start time is available)
    try:
        from app.main import get_app_start_time

        start_time = get_app_start_time()
        uptime_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
    except Exception:
        uptime_seconds = None

    return StatsResponse(
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        paused_jobs=paused_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        total_secrets=total_secrets,
        total_logs=total_logs,
        uptime_seconds=uptime_seconds,
    )
