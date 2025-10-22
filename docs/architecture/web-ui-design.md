# TeckoChecker Web UI Design

> **Status:** IMPLEMENTED in v0.9.0
>
> This document contains the original design specifications for the TeckoChecker Web UI.
> The Web UI has been fully implemented and is available at `/web`.
>
> See [docs/WEB_UI.md](../WEB_UI.md) for current user documentation.

## Architecture Overview

### Technology Stack
- **Frontend**: Vanilla HTML/CSS/JavaScript (KISS principle)
- **Styling**: Terminal/hacker aesthetic with custom CSS
- **Backend**: FastAPI static files + template rendering
- **Communication**: REST API (existing endpoints)

### Directory Structure
```
app/
├── web/                      # New web UI module
│   ├── __init__.py
│   ├── routes.py            # Web routes (/web/*)
│   └── static/
│       ├── css/
│       │   └── terminal.css # Terminal-style theme
│       ├── js/
│       │   ├── app.js      # Main application
│       │   ├── api.js      # API client
│       │   └── terminal.js # Terminal UI helpers
│       └── index.html       # Single page app
```

## UI Components

### 1. Secrets Management
```javascript
// Features:
- Add secret (modal with type selection)
- List secrets (table with names, types, created dates)
- Delete secret (with confirmation)
- No editing (security: delete and recreate)

// UI:
┌─ SECRETS ─────────────────────────────────┐
│ > secret list                             │
│                                           │
│ NAME          TYPE      CREATED           │
│ ─────────────────────────────────────     │
│ openai-prod   openai    2025-01-22       │
│ keboola-prod  keboola   2025-01-22       │
│                                           │
│ [+ Add Secret] [↻ Refresh]                │
└───────────────────────────────────────────┘
```

### 2. Jobs Management
```javascript
// Features:
- Create job (form with all fields)
- List jobs with status indicators
- Pause/Resume/Delete actions
- Real-time status updates

// UI:
┌─ JOBS ────────────────────────────────────┐
│ > job list --active                       │
│                                           │
│ ID  NAME         STATUS    NEXT CHECK     │
│ ──────────────────────────────────────    │
│ 1   Batch-123   ● active   in 45s        │
│ 2   Batch-456   ◌ paused   -             │
│ 3   Batch-789   ✓ done     -             │
│                                           │
│ [+ Create Job] [↻ Refresh]                │
└───────────────────────────────────────────┘
```

### 3. Monitoring Dashboard
```javascript
// Features:
- System stats (active jobs, total processed)
- Recent activity feed
- Job timeline visualization
- Health status indicator

// UI:
┌─ MONITOR ─────────────────────────────────┐
│ > system status                           │
│                                           │
│ SYSTEM STATUS: ● RUNNING                  │
│ Active Jobs: 5                            │
│ Total Processed: 127                      │
│ Uptime: 2d 14h 23m                       │
│                                           │
│ > recent activity                         │
│ [12:34:56] Job #1 checked - pending      │
│ [12:33:45] Job #2 completed ✓            │
│ [12:32:10] Job #3 triggered Keboola      │
└───────────────────────────────────────────┘
```

### 4. Logs Viewer
```javascript
// Features:
- Tail-like log streaming
- Filter by job ID or log level
- Search functionality
- Auto-scroll with pause option

// UI:
┌─ LOGS ────────────────────────────────────┐
│ > tail -f polling.log | grep job_id=1    │
│                                           │
│ 2025-01-22 12:34:56 INFO  Checking job #1│
│ 2025-01-22 12:34:57 INFO  Status: pending│
│ 2025-01-22 12:35:56 INFO  Next check: 60s│
│ 2025-01-22 12:36:56 INFO  Checking job #1│
│                                           │
│ [⏸ Pause] [🔍 Filter] [⬇ Auto-scroll]    │
└───────────────────────────────────────────┘
```

## Styling Theme

```css
/* Terminal/Hacker Theme Variables */
:root {
  --bg-primary: #0a0a0a;
  --bg-secondary: #1a1a1a;
  --text-primary: #00ff00;
  --text-secondary: #00aa00;
  --text-dim: #006600;
  --accent: #00ffff;
  --error: #ff0040;
  --warning: #ffaa00;
  --border: #00ff00;
  --font-mono: 'Fira Code', 'Courier New', monospace;
}

/* ASCII Art Header */
.ascii-header {
  white-space: pre;
  font-family: var(--font-mono);
  color: var(--accent);
  text-shadow: 0 0 10px var(--accent);
}

/* Terminal Container */
.terminal {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
  padding: 20px;
  font-family: var(--font-mono);
}

/* Blinking Cursor */
.cursor::after {
  content: '█';
  animation: blink 1s infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}
```

## API Integration

```javascript
// api.js - Simple API client
class TeckoAPI {
  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl;
  }

  async request(method, path, body = null) {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };

    if (body) options.body = JSON.stringify(body);

    const response = await fetch(`${this.baseUrl}${path}`, options);
    if (!response.ok) throw new Error(`API Error: ${response.status}`);
    return response.json();
  }

  // Secrets
  async getSecrets() {
    return this.request('GET', '/admin/secrets');
  }

  async addSecret(data) {
    return this.request('POST', '/admin/secrets', data);
  }

  // Jobs
  async getJobs() {
    return this.request('GET', '/jobs');
  }

  async createJob(data) {
    return this.request('POST', '/jobs', data);
  }

  async pauseJob(id) {
    return this.request('POST', `/jobs/${id}/pause`);
  }

  // System
  async getStats() {
    return this.request('GET', '/stats');
  }

  async getHealth() {
    return this.request('GET', '/health');
  }
}
```

## FastAPI Integration

```python
# app/web/routes.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

router = APIRouter()
STATIC_DIR = Path(__file__).parent / "static"

# Mount static files
app.mount("/web/static", StaticFiles(directory=STATIC_DIR), name="static")

@router.get("/web", response_class=HTMLResponse)
async def web_ui():
    """Serve the main web UI"""
    with open(STATIC_DIR / "index.html") as f:
        return HTMLResponse(content=f.read())
```

## Implementation Steps

1. **Phase 1: Basic Structure** (2 hours)
   - Create web module structure
   - Set up static file serving
   - Create base HTML template
   - Implement terminal CSS theme

2. **Phase 2: Core Features** (3 hours)
   - Secrets management UI
   - Jobs CRUD interface
   - Basic monitoring view
   - API integration

3. **Phase 3: Polish** (1 hour)
   - Log viewer with filtering
   - Real-time updates (polling)
   - Error handling
   - Loading states

## Security Considerations

- No authentication (admin-only for MVP)
- All API calls through existing endpoints
- No secret values displayed in UI
- CSRF protection via SameSite cookies
- Input sanitization on all forms

## Future Enhancements

- WebSocket for real-time updates
- Job history graphs
- Export functionality
- Keyboard shortcuts
- Dark/light theme toggle
- Mobile responsive design