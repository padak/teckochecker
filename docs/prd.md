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
- Specify Keboola job to trigger
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
    batch_id TEXT NOT NULL,
    openai_secret_id INTEGER,
    keboola_secret_id INTEGER,
    keboola_stack_url TEXT NOT NULL,
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
teckochecker job create \
  --name "My Batch Job" \
  --batch-id "batch_abc123" \
  --openai-secret "openai-prod" \
  --keboola-secret "keboola-prod" \
  --keboola-stack "https://connection.keboola.com" \
  --config-id "123456" \
  --poll-interval 60  # seconds

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

### Phase 2: Enhancements (Future)
- Web UI for management
- Multi-user support
- Additional polling sources (not just OpenAI)
- Webhook actions (not just Keboola)
- Metrics and monitoring
- Docker deployment

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

### Error Codes
- 1001: Secret not found
- 1002: Job not found
- 2001: OpenAI API error
- 2002: Keboola API error
- 3001: Database error
- 3002: Encryption error

---

*Document Version: 1.0*
*Last Updated: 2025-01-22*
*Status: Ready for Implementation*