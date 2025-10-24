# TeckoChecker - Product Requirements Document (PRD)

## Executive Summary

TeckoChecker is a lightweight polling orchestration system designed to monitor asynchronous job statuses and trigger downstream actions. The initial implementation focuses on monitoring OpenAI batch job completion and triggering Keboola Connection jobs.

### Key Principles
- **KISS** (Keep It Simple, Stupid) - Minimize complexity
- **YAGNI** (You Aren't Gonna Need It) - Build only what's needed now
- **Single-tenant** - One organization, admin-only access initially
- **Extensible** - Ready for future UI and additional polling sources

## Problem Statement

Organizations need to coordinate asynchronous workflows between different systems. Specifically:
1. OpenAI batch jobs run for unpredictable durations
2. Manual checking of job status is inefficient
3. Downstream processes (like Keboola jobs) need to start immediately when prerequisites complete
4. No existing lightweight solution for this specific integration

## Solution Overview

TeckoChecker provides:
- Automated polling of OpenAI batch job status
- Automatic triggering of Keboola jobs upon completion
- Secure secrets management
- REST API for future UI integration
- CLI for administrative operations
- Flexible polling intervals (configurable per job)

## Functional Requirements

### 1. Polling Jobs Management

#### 1.1 Create Polling Job
- Define OpenAI batch ID to monitor
- Specify Keboola component and configuration to trigger
- Set custom polling interval (e.g., 30 seconds to 10 minutes)
- Associate with stored secrets

#### 1.2 List Polling Jobs
- View all polling jobs with current status
- See last check time and next scheduled check

#### 1.3 View Job Details
- Detailed information about specific polling job
- Current status and history

#### 1.4 Modify Polling Job
- Update polling interval
- Change associated Keboola configuration
- Pause/resume polling

#### 1.5 Delete Polling Job
- Remove job and associated logs

### 2. Secrets Management

#### 2.1 Store Secrets
- Securely store OpenAI API keys
- Store Keboola Storage API tokens
- Encrypt all secrets at rest
- Named secrets for easy reference

#### 2.2 List Secrets
- Show secret names and types (without values)
- Display creation timestamps

#### 2.3 Delete Secrets
- Remove unused secrets
- Prevent deletion if referenced by active jobs

### 3. Polling Engine

#### 3.1 Status Checking
- Poll OpenAI batch job status at configured intervals
- Support flexible intervals per job (30 seconds to hours)
- Handle API rate limits gracefully

#### 3.2 Trigger Actions
- Execute Keboola job when OpenAI batch completes
- Only trigger on "completed" status
- Handle failures gracefully

#### 3.3 Scheduling
- Maintain schedule for all active jobs
- Respect individual polling intervals
- Efficient resource usage

### 4. System Administration

#### 4.1 Health Monitoring
- System health check endpoint
- Basic statistics (jobs processed, active jobs)

#### 4.2 Daemon Management
- Start/stop polling service
- Graceful shutdown
- Auto-restart capability

## Technical Requirements

### Architecture

#### Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: SQLite
- **ORM**: SQLAlchemy
- **CLI**: Typer
- **Encryption**: Fernet (cryptography library)
- **Scheduler**: asyncio with background tasks

#### Data Model

```sql
-- Secrets storage
CREATE TABLE secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL, -- 'openai', 'keboola'
    value TEXT NOT NULL, -- encrypted
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Polling jobs
CREATE TABLE polling_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    openai_secret_id INTEGER,
    keboola_secret_id INTEGER,
    keboola_stack_url TEXT NOT NULL,
    keboola_component_id TEXT NOT NULL,
    keboola_configuration_id TEXT NOT NULL,
    poll_interval_seconds INTEGER DEFAULT 120,
    status TEXT DEFAULT 'active', -- 'active', 'paused', 'completed', 'failed'
    last_check_at TIMESTAMP,
    next_check_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (openai_secret_id) REFERENCES secrets(id),
    FOREIGN KEY (keboola_secret_id) REFERENCES secrets(id)
);

-- Job batches (multi-batch support)
CREATE TABLE job_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    polling_job_id INTEGER NOT NULL,
    batch_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (polling_job_id) REFERENCES polling_jobs(id) ON DELETE CASCADE,
    UNIQUE(polling_job_id, batch_id)
);

-- Polling logs (optional for debugging)
CREATE TABLE polling_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    status TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES polling_jobs(id) ON DELETE CASCADE
);
```

### API Specification

#### Admin Endpoints
```
POST   /api/admin/secrets           # Store new secret
GET    /api/admin/secrets           # List secrets (without values)
DELETE /api/admin/secrets/{id}      # Delete secret
```

#### Polling Jobs Endpoints
```
POST   /api/jobs                    # Create new polling job
GET    /api/jobs                    # List all jobs
GET    /api/jobs/{id}               # Get job details
PUT    /api/jobs/{id}               # Update job
DELETE /api/jobs/{id}               # Delete job
POST   /api/jobs/{id}/pause         # Pause job
POST   /api/jobs/{id}/resume        # Resume job
```

#### System Endpoints
```
GET    /api/health                  # Health check
GET    /api/stats                   # System statistics
```

### CLI Commands

```bash
# System initialization
teckochecker init

# Secrets management
teckochecker secret add --name "openai-prod" --type openai
teckochecker secret list
teckochecker secret delete openai-prod

# Jobs management

# Single batch job
teckochecker job create \
  --name "My Batch Job" \
  --batch-id "batch_abc123" \
  --openai-secret "openai-prod" \
  --keboola-secret "keboola-prod" \
  --keboola-stack "https://connection.eu-central-1.keboola.com" \
  --component-id "kds-team.app-custom-python" \
  --config-id "123456" \
  --poll-interval 60  # seconds

# Multi-batch job (1-10 batches)
teckochecker job create \
  --name "Multi-Batch Job" \
  --batch-id "batch_abc123" \
  --batch-id "batch_def456" \
  --batch-id "batch_ghi789" \
  --openai-secret "openai-prod" \
  --keboola-secret "keboola-prod" \
  --keboola-stack "https://connection.eu-central-1.keboola.com" \
  --component-id "kds-team.app-custom-python" \
  --config-id "123456" \
  --poll-interval 120

teckochecker job list
teckochecker job show 1
teckochecker job pause 1
teckochecker job resume 1
teckochecker job delete 1

# System management
teckochecker status
teckochecker start  # Start polling daemon
teckochecker stop   # Stop polling daemon
```

## Non-Functional Requirements

### Performance
- Handle 100+ concurrent polling jobs
- Sub-second API response times
- Minimal resource usage (< 100MB RAM)

### Security
- All secrets encrypted at rest (AES-256)
- No secrets in logs
- API authentication (future: when multi-user added)

### Reliability
- Graceful handling of API failures
- Automatic retry with exponential backoff
- No data loss on service restart

### Scalability
- SQLite supports single-node scale
- Design allows future migration to PostgreSQL
- API structure supports horizontal scaling

## Web UI Requirements

### Overview
TeckoChecker includes a production-ready web interface accessible at `http://127.0.0.1:8000/web` once the API server is running. The UI follows KISS principles with vanilla HTML/CSS/JavaScript and features a terminal/hacker aesthetic matching the CLI design.

### Design Philosophy
- **No frameworks** - Pure vanilla JavaScript (ES6+)
- **No build process** - Works immediately without compilation
- **Terminal aesthetic** - Matches CLI with matrix-style green-on-black theme
- **Single-page application** - Fast navigation without page reloads
- **Responsive components** - Works on modern desktop browsers

### Core Features

#### 1. Secrets Management Tab
- **Add Secret**: Store encrypted OpenAI and Keboola API credentials via modal form
- **List Secrets**: Display all stored secrets showing names and types only (values always hidden)
- **Delete Secret**: Remove unused secrets with confirmation dialog
- **Protection**: Prevents deletion of secrets referenced by active jobs

**User Flow:**
1. Click "Secrets" tab
2. Click "+ Add Secret" button
3. Enter name, select type (OpenAI/Keboola), paste API key/token
4. Submit to create encrypted secret

#### 2. Jobs Management Tab
- **Create Job**: Set up polling jobs with full configuration (batch ID, secrets, Keboola component details, poll interval)
- **List Jobs**: View all jobs with real-time status indicators
- **Status Indicators**:
  - 🟢 Green pulsing dot: Active and polling
  - ⚪ Yellow dot: Paused
  - ✓ Gray dot: Completed
  - 🔴 Red dot: Failed
- **Job Controls**: Pause/resume/delete with confirmation dialogs
- **Auto-loading**: Secrets automatically populate in dropdowns

**User Flow:**
1. Ensure secrets exist first
2. Click "Jobs" tab → "+ Create Job"
3. Fill job configuration form
4. Submit to start polling

#### 3. Monitor Dashboard Tab
- **System Status**: Real-time health check display
- **Statistics**:
  - Active jobs count
  - Total jobs count
  - Database type and status
- **Recent Activity**: Feed of latest job events
- **Auto-refresh**: Toggle for continuous updates every 5 seconds

#### 4. Logs Viewer Tab
- **Tail-like Display**: Terminal-style log output
- **Color-coded Messages**:
  - Green: Success/Info
  - Yellow: Warning
  - Red: Error
- **Controls**:
  - Auto-refresh toggle (5-second intervals)
  - Manual refresh button
  - Clear logs button

#### 5. System Information Tab
- **Health Check**: API server status verification
- **API Endpoints**: Quick reference documentation
- **System Details**: Configuration and version information

### UI/UX Design Theme

#### Terminal/Hacker Aesthetic
```
Visual Elements:
- ASCII art header matching CLI output
- Monospace fonts (Fira Code, Cascadia Code, SF Mono)
- Green-on-black color scheme
- Glowing borders and shadow effects
- Blinking cursors and terminal-style elements
- Fade-in animations and smooth transitions
```

#### Color Palette
```css
Background:    #0a0a0a (primary), #1a1a1a (secondary)
Text:          #00ff00 (primary green), #00cc00 (secondary)
Accent:        #00ffff (cyan for headers)
Success:       #00ff88
Warning:       #ffaa00
Error:         #ff0040
Border:        #00ff00 with glow effect
```

#### Component Design
- **Navigation**: Tab-based with active state highlighting
- **Modal Dialogs**: Terminal-style forms with glowing borders
- **Data Tables**: Hover effects with row highlighting
- **Buttons**: Terminal-bordered with glow on hover
- **Form Inputs**: Focus glow effects, monospace text
- **Status Dots**: Animated pulsing for active states
- **Scrollbars**: Custom-styled matching theme

### Technical Architecture

#### Frontend Stack
```
Technology:    Pure HTML5/CSS3/JavaScript (ES6+)
Files:         Single-page application (~1,550 lines total)
Dependencies:  None (zero external libraries)
Communication: Fetch API for REST calls
State:         In-memory JavaScript objects
```

#### File Structure
```
app/web/
├── __init__.py              # Module initialization
├── routes.py                # FastAPI routes for web UI
└── static/
    ├── css/
    │   └── terminal.css     # Terminal theme styles (~600 lines)
    ├── js/
    │   ├── api.js          # REST API client (~140 lines)
    │   └── app.js          # Main application logic (~470 lines)
    └── index.html           # Single-page app (~330 lines)
```

#### API Integration
The Web UI uses the same REST API as external integrations:

```javascript
// All operations go through /api/* endpoints
GET    /api/health              // System health check
GET    /api/stats               // System statistics
GET    /api/admin/secrets       // List secrets (no values)
POST   /api/admin/secrets       // Add new secret
DELETE /api/admin/secrets/{id}  // Delete secret
GET    /api/jobs                // List all jobs
POST   /api/jobs                // Create polling job
POST   /api/jobs/{id}/pause     // Pause job
POST   /api/jobs/{id}/resume    // Resume job
DELETE /api/jobs/{id}           // Delete job
```

#### Backend Integration
```python
# FastAPI serves both API and Web UI on same port (8000)
- Static files mounted at /web/static
- Web routes included at /web
- No separate server required
- CORS configured for local development
```

### Security Implementation

**Current (MVP - Admin-only)**:
- All secrets encrypted at rest with AES-256 (Fernet)
- Secret values never displayed in UI
- Input sanitization (HTML escaping)
- No authentication required (single-tenant admin access)

**Future Considerations**:
- Multi-user authentication when needed
- HTTPS enforcement for production
- API rate limiting
- CSRF protection

### Browser Compatibility
- ✅ Chrome/Edge (Chromium-based)
- ✅ Firefox
- ✅ Safari
- Requires modern browser with ES6+ support

### Performance Characteristics
```
Bundle Size:    ~37 KB total (uncompressed)
Load Time:      < 100ms first load
Caching:        Static files cached by browser
Memory:         Minimal JavaScript overhead
Updates:        Efficient DOM updates, no memory leaks
```

### Usage Best Practices
1. **Add secrets first** before creating jobs
2. **Use descriptive names** for secrets and jobs (e.g., "openai-prod", "batch-processor")
3. **Set appropriate poll intervals** (30 seconds minimum, consider API rate limits)
4. **Monitor regularly** for failed jobs in Monitor tab
5. **Enable auto-refresh** on Logs tab for real-time troubleshooting

### Keyboard Shortcuts (Command Line)
The command line at bottom accepts:
- `help` - Show available commands
- `refresh` - Reload the page
- `clear` - Clear command input

### Known Limitations
1. **No WebSocket** - Uses HTTP polling for real-time updates (5-second interval when enabled)
2. **No Authentication** - Admin-only access assumed (MVP scope)
3. **No Pagination** - Works efficiently for < 100 jobs (sufficient for MVP)
4. **Desktop-first** - Not optimized for mobile devices yet
5. **Single Theme** - Only dark terminal theme available currently

### Future Web UI Enhancements
**High Priority:**
- WebSocket for true real-time log streaming
- Job history charts (last 24h activity graphs)
- Export functionality (CSV/JSON downloads)
- Search and filter capabilities

**Medium Priority:**
- Keyboard shortcuts (Ctrl+K for command palette)
- Multiple theme options (light mode, custom colors)
- Mobile-responsive design
- Pagination for large datasets

**Low Priority:**
- User preferences stored in localStorage
- Custom dashboard widgets
- Browser notifications
- Advanced filtering and sorting

### Troubleshooting

**Web UI not loading:**
- Ensure API server is running: `python teckochecker.py start`
- Verify static files exist in `app/web/static/`
- Check no port conflicts on 8000

**Cannot create jobs:**
- Add secrets first (OpenAI and Keboola credentials required)
- Verify secret types match requirements
- Check all form fields are completed

**Logs not updating:**
- Click refresh button manually
- Enable auto-refresh toggle
- Verify API endpoints responding at `/api/jobs`

**Styles not loading:**
- Hard refresh: Ctrl+Shift+R (Cmd+Shift+R on Mac)
- Check browser console for errors
- Verify `/web/static/css/terminal.css` exists

## Implementation Phases

### Phase 1: MVP (10-12 hours)
1. **Core Setup** (2-3 hours)
   - Project structure
   - Database models
   - Basic FastAPI application

2. **Secrets Management** (2 hours)
   - Encryption implementation
   - CRUD operations
   - CLI commands

3. **Polling Jobs** (3-4 hours)
   - Job CRUD operations
   - OpenAI integration
   - Keboola integration

4. **Polling Engine** (2-3 hours)
   - Async polling loop
   - Job scheduling
   - Status management

5. **Testing & Polish** (2 hours)
   - Error handling
   - Basic tests
   - Documentation

### Phase 2: Web UI (Completed)
- Web interface for management
- Terminal-style aesthetic matching CLI
- Full feature parity with CLI
- Real-time monitoring dashboard
- No-build vanilla JavaScript approach

### Phase 3: Future Enhancements
- Multi-user support and authentication
- Additional polling sources (not just OpenAI)
- Webhook actions (not just Keboola)
- Advanced metrics and monitoring
- Docker deployment
- WebSocket for real-time updates

## Success Criteria

### MVP Success Metrics
- ✅ Successfully polls OpenAI batch job status
- ✅ Triggers Keboola job on completion
- ✅ Runs continuously for 1 month without intervention
- ✅ Handles 10+ concurrent polling jobs
- ✅ Zero security incidents (no leaked secrets)

### User Experience Goals
- Admin can set up new polling job in < 1 minute
- System requires < 5 minutes to learn
- Zero maintenance in normal operation

## Constraints & Assumptions

### Constraints
- Single-tenant (one organization)
- Admin-only access (no multi-user initially)
- SQLite database (no external database server)
- Local or simple server deployment

### Assumptions
- OpenAI API remains stable
- Keboola API remains stable
- Python 3.11+ available on deployment server
- Low to medium volume (< 1000 jobs per day)

## Future Considerations

### Extensibility Points
1. **Multiple Polling Sources**
   - Design allows adding new source types
   - Abstract polling interface

2. **Multiple Action Types**
   - Currently Keboola-only
   - Can add webhooks, email, Slack, etc.

3. **Web UI**
   - API designed for UI consumption
   - RESTful design supports any frontend

4. **Multi-tenancy**
   - Database structure supports user separation
   - API can add authentication layer

## Appendix

### Sample Configuration File (.env)
```env
# Database
DATABASE_URL=sqlite:///./teckochecker.db

# Security
SECRET_KEY=your-secret-key-for-encryption

# Polling
DEFAULT_POLL_INTERVAL=120  # seconds
MIN_POLL_INTERVAL=30      # seconds
MAX_POLL_INTERVAL=3600    # seconds (1 hour)
MAX_RETRIES=3
RETRY_DELAY=60            # seconds

# API
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_FILE=teckochecker.log
```

### Keboola Integration

The system requires the following for Keboola job triggering:
- **Stack URL**: e.g., `https://connection.eu-central-1.keboola.com`
- **Component ID**: e.g., `kds-team.app-custom-python`
- **Configuration ID**: The specific configuration to run
- **Storage API Token**: For authentication (stored as encrypted secret)

Jobs are triggered via POST to `https://queue.{region}.keboola.com/jobs` with:
```json
{
  "mode": "run",
  "component": "component_id",
  "config": "configuration_id"
}
```

### Error Codes
- 1001: Secret not found
- 1002: Job not found
- 2001: OpenAI API error
- 2002: Keboola API error
- 3001: Database error
- 3002: Encryption error

---

*Document Version: 3.0*
*Last Updated: 2025-10-23*
*Status: v1.0 Complete - Multi-Batch Support Integrated*
*Note: Multi-batch polling (1-10 batches per job) with intelligent triggering when all batches terminal*