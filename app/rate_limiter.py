"""Rate limiting configuration for FastAPI endpoints."""

import logging
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import status
from fastapi.responses import JSONResponse

from app.config import get_settings


logger = logging.getLogger(__name__)


def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key based on client IP address.

    For more sophisticated setups, this could use authenticated user ID,
    but for admin-only API, IP-based limiting is sufficient.

    Args:
        request: FastAPI request object

    Returns:
        Unique identifier for rate limiting (IP address)
    """
    # Check for X-Forwarded-For header (proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (client IP)
        return forwarded.split(",")[0].strip()

    # Fallback to direct connection IP
    return get_remote_address(request)


# Initialize limiter with custom key function
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[],  # We'll apply limits per endpoint
    storage_uri="memory://",  # In-memory storage (no Redis needed for single instance)
    strategy="fixed-window",  # Fixed time window strategy
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns a JSON response with proper HTTP 429 status and Retry-After header.

    Args:
        request: FastAPI request object
        exc: RateLimitExceeded exception

    Returns:
        JSON response with error details
    """
    settings = get_settings()

    # Extract retry-after from exception if available
    retry_after = getattr(exc, "retry_after", None)

    logger.warning(
        f"Rate limit exceeded for {get_rate_limit_key(request)} on {request.url.path}"
    )

    headers = {}
    if retry_after:
        headers["Retry-After"] = str(int(retry_after))

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "code": 4029,
        },
        headers=headers,
    )


def get_limit_for_endpoint(method: str) -> str:
    """
    Get the appropriate rate limit string based on HTTP method.

    This function is called at decorator time to determine the rate limit.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)

    Returns:
        Rate limit string (e.g., "200/minute") or empty string to disable
    """
    settings = get_settings()

    # If rate limiting is disabled, return empty string (no limit)
    if not settings.rate_limit_enabled:
        return ""

    if method == "GET":
        return settings.rate_limit_read
    elif method in ["POST", "PUT", "DELETE", "PATCH"]:
        return settings.rate_limit_write
    else:
        return settings.rate_limit_default
