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
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.rate_limiter import limiter, rate_limit_exceeded_handler, get_limit_for_endpoint
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

# Add rate limiter state to app
app.state.limiter = limiter

# Add SlowAPI middleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

app.add_middleware(SlowAPIMiddleware)

# Configure CORS middleware
# CORS (Cross-Origin Resource Sharing) controls which websites can make requests to our API from browsers.
#
# WHEN CORS IS NEEDED:
# CORS is only needed when the Web UI is served from a DIFFERENT domain than the API.
# For example: UI at https://ui.example.com calling API at https://api.example.com
#
# WHEN CORS IS NOT NEEDED (CURRENT SETUP):
# Our Web UI is served from the SAME origin as the API:
# - Web UI: http://localhost:8000/web (or https://tt.keboola.ai/web)
# - API: http://localhost:8000/api (or https://tt.keboola.ai/api)
# Same-origin requests bypass CORS entirely - browsers allow them automatically.
#
# SECURITY CONSIDERATIONS:
# 1. Empty cors_origins list = CORS disabled = only same-origin requests allowed
# 2. If external tools need API access, add specific origins like ["https://tool.example.com"]
# 3. NEVER use allow_origins=["*"] with allow_credentials=True - browsers reject this
# 4. NEVER use allow_origins=["*"] in production - allows any malicious site to call your API
#
# WHAT CORS PROTECTS AGAINST:
# Without CORS restrictions, a malicious website (evil.com) could make authenticated API
# requests on behalf of logged-in users, potentially stealing data or performing actions.
# CORS ensures only trusted origins can make cross-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return rate_limit_exceeded_handler(request, exc)


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
@limiter.limit(get_limit_for_endpoint("GET"))
async def root(request: Request):
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
