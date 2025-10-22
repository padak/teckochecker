"""Web UI routes for TeckoChecker"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(tags=["Web UI"])

# Get the static directory path
STATIC_DIR = Path(__file__).parent / "static"


@router.get("/", response_class=HTMLResponse)
async def web_ui():
    """Serve the main web UI"""
    index_path = STATIC_DIR / "index.html"

    if not index_path.exists():
        return HTMLResponse(
            content="<h1>Web UI not found</h1><p>Please ensure index.html exists</p>",
            status_code=404,
        )

    with open(index_path) as f:
        return HTMLResponse(content=f.read())


@router.get("/health")
async def web_health():
    """Web UI health check"""
    return {"status": "healthy", "ui": "web"}
