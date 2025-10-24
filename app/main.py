"""FastAPI application entry point for TeckoChecker."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import init_db, get_db
from app.services.encryption import init_encryption_service
from app.services.polling import PollingService
from app.api import admin, jobs, system
from app.web import router as web_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path


# Load settings early for logging configuration
settings = get_settings()

# Configure logging with both console and file handlers
handlers = [logging.StreamHandler()]
if settings.log_file:
    handlers.append(logging.FileHandler(settings.log_file))

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)


# Application startup time for uptime tracking
app_start_time = datetime.now(timezone.utc)

# Global polling task reference
polling_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    global polling_task

    # Startup
    logger.info("Starting TeckoChecker API...")
    settings = get_settings()

    # Initialize encryption service
    try:
        init_encryption_service(settings.secret_key)
        logger.info("Encryption service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize encryption service: {e}")
        raise

    # Initialize database
    try:
        init_db()
        logger.info(f"Database initialized at {settings.database_url}")

        # Test connection
        from app.database import get_db_manager

        db_manager = get_db_manager()
        if db_manager.check_connection():
            logger.info("Database connection test successful")
        else:
            logger.error("Database connection test failed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Start polling service
    try:
        logger.info("Starting polling service...")
        polling_service = PollingService(
            db_session_factory=get_db, default_poll_interval=settings.default_poll_interval
        )
        polling_task = asyncio.create_task(polling_service.polling_loop())
        logger.info("Polling service started successfully")
    except Exception as e:
        logger.error(f"Failed to start polling service: {e}")
        # Don't raise - allow API to run even if polling fails

    yield

    # Shutdown
    logger.info("Shutting down TeckoChecker API...")

    # Stop polling service
    if polling_task:
        logger.info("Stopping polling service...")
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            logger.info("Polling service stopped")
        except Exception as e:
            logger.error(f"Error stopping polling service: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with custom format."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])  # Skip 'body'
        errors.append({"field": field, "message": error["msg"]})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": errors,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "database_error", "message": "A database error occurred", "code": 3001},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "message": "An unexpected error occurred"},
    )


# Include routers
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])

app.include_router(system.router, prefix="/api", tags=["System"])

# Mount static files for web UI
STATIC_DIR = Path(__file__).parent / "web" / "static"
app.mount("/web/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include web UI router
app.include_router(web_router, prefix="/web", tags=["Web UI"])


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "web_ui": "/web",
        "docs": "/docs",
        "health": "/api/health",
    }


def get_app_start_time() -> datetime:
    """Get application start time for uptime calculations."""
    return app_start_time


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
