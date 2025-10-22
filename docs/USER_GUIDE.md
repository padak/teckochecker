# TeckoChecker - Complete User Guide

## Table of Contents
1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Managing Secrets](#managing-secrets)
5. [Managing Polling Jobs](#managing-polling-jobs)
6. [Running Polling Service](#running-polling-service)
7. [REST API](#rest-api)
8. [Troubleshooting](#troubleshooting)

## Quick Start

TeckoChecker in 5 steps:

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize database
python scripts/init_db.py --create-env

# 4. Start API server (in separate terminal)
python -m uvicorn app.main:app --reload

# 5. Add secrets (in another terminal)
python teckochecker.py secret add --name "openai-prod" --type openai
python teckochecker.py secret add --name "keboola-prod" --type keboola

# 6. Create polling job
python teckochecker.py job create \
  --name "My batch job" \
  --batch-id "batch_abc123" \
  --openai-secret "openai-prod" \
  --keboola-secret "keboola-prod" \
  --keboola-stack "https://connection.keboola.com" \
  --config-id "123456" \
  --poll-interval 120

# 7. Start polling service
python teckochecker.py start --daemon
```

## Installation

### Requirements
- Python 3.11+
- pip
- SQLite (part of Python)

### Step 1: Clone the repository
```bash
git clone https://github.com/yourusername/teckochecker.git
cd teckochecker
```

### Step 2: Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Initialize database
```bash
# Automatic creation of .env file with generated SECRET_KEY
python scripts/init_db.py --create-env

# Or manual configuration
cp .env.example .env
# Edit .env and set SECRET_KEY
python scripts/init_db.py
```

### Step 5: Install CLI
```bash
# For development
pip install -e .

# Or direct execution
python teckochecker.py --help
```

### Step 6: Shell completion (optional)
```bash
# Automatic installation for your shell
teckochecker install-completion

# Or for specific shell
teckochecker install-completion bash
teckochecker install-completion zsh
teckochecker install-completion fish
```

## Configuration

### Configuration file .env

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=sqlite:///./teckochecker.db  # Or postgresql://...

# Security
SECRET_KEY=your-secret-key-here  # Generate using: openssl rand -hex 32

# Polling
DEFAULT_POLL_INTERVAL=120  # Default interval in seconds
MIN_POLL_INTERVAL=30       # Minimum allowed interval
MAX_POLL_INTERVAL=3600     # Maximum allowed interval (1 hour)
MAX_RETRIES=3              # Number of retries on failure
RETRY_DELAY=60             # Delay between retries

# API Server
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000"]  # For future UI

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=teckochecker.log
```

### Verify configuration
```bash
python scripts/verify_setup.py
```

## Managing Secrets

Secrets are encrypted API keys stored in the database.

### Add a secret
```bash
# OpenAI API key
teckochecker secret add --name "openai-prod" --type openai
Enter secret value: **********************

# Keboola Storage API token
teckochecker secret add --name "keboola-prod" --type keboola
Enter secret value: **********************
```

### List all secrets
```bash
teckochecker secret list

╭──────────────────────────────────────────────────────╮
│                   Stored Secrets                     │
├────┬─────────────┬─────────┬──────────────────────┤
│ ID │ Name        │ Type    │ Created At           │
├────┼─────────────┼─────────┼──────────────────────┤
│ 1  │ openai-prod │ openai  │ 2025-01-22 10:00:00 │
│ 2  │ keboola-prod│ keboola │ 2025-01-22 10:01:00 │
╰────┴─────────────┴─────────┴──────────────────────╯
```

### Delete a secret
```bash
# With confirmation
teckochecker secret delete openai-test
Are you sure you want to delete secret 'openai-test'? [y/N]: y

# Without confirmation
teckochecker secret delete openai-test --force
```

## Managing Polling Jobs

### Create a new job
```bash
teckochecker job create \
  --name "Batch processing job" \
  --batch-id "batch_abc123" \
  --openai-secret "openai-prod" \
  --keboola-secret "keboola-prod" \
  --keboola-stack "https://connection.keboola.com" \
  --config-id "123456" \
  --poll-interval 120  # Check every 2 minutes

✓ Polling job 'Batch processing job' created successfully (ID: 1)
```

### Parameters for job creation
- `--name`: Descriptive job name
- `--batch-id`: OpenAI batch job ID
- `--openai-secret`: OpenAI secret name
- `--keboola-secret`: Keboola secret name
- `--keboola-stack`: Keboola stack URL
- `--config-id`: Configuration ID in Keboola
- `--poll-interval`: Check interval in seconds (30-3600)

### List jobs
```bash
# All jobs
teckochecker job list

# Only active jobs
teckochecker job list --status active

# Only completed jobs
teckochecker job list --status completed
```

### Job details
```bash
teckochecker job show 1

╭─────────────────────────────────────────────────────╮
│              Polling Job Details                    │
├─────────────────┬───────────────────────────────────┤
│ ID              │ 1                                 │
│ Name            │ Batch processing job             │
│ Status          │ 🟢 active                        │
│ Batch ID        │ batch_abc123                      │
│ Poll Interval   │ 120 seconds                       │
│ Last Check      │ 2025-01-22 10:15:00              │
│ Next Check      │ 2025-01-22 10:17:00              │
│ Created At      │ 2025-01-22 10:00:00              │
╰─────────────────┴───────────────────────────────────╯
```

### Managing job state
```bash
# Pause job
teckochecker job pause 1
✓ Job 'Batch processing job' has been paused

# Resume job
teckochecker job resume 1
✓ Job 'Batch processing job' has been resumed

# Delete job
teckochecker job delete 1 --force
✓ Job deleted successfully
```

## Running Polling Service

### Start API server
```bash
# In first terminal, start API server
source venv/bin/activate
python -m uvicorn app.main:app --reload

# Server will run on http://127.0.0.1:8000
# Swagger documentation: http://127.0.0.1:8000/docs
# ReDoc documentation: http://127.0.0.1:8000/redoc
```

### Start polling service
```bash
# In second terminal, start polling service
source venv/bin/activate
python teckochecker.py start

# Or as daemon in background
python teckochecker.py start --daemon
```

### Check status
```bash
teckochecker status

╭─────────────────────────────────────────────────────╮
│              System Status                          │
├─────────────────┬───────────────────────────────────┤
│ Service         │ 🟢 Running                       │
│ Uptime          │ 2 hours 15 minutes                │
│ Active Jobs     │ 3                                 │
│ Completed Jobs  │ 12                                │
│ Failed Jobs     │ 0                                 │
│ API Server      │ http://0.0.0.0:8000              │
│ Database        │ Connected                         │
╰─────────────────┴───────────────────────────────────╯
```

### Stop service
```bash
teckochecker stop
✓ TeckoChecker daemon stopped
```

## REST API

API runs on `http://localhost:8000` when the service is running.

### Swagger documentation
Visit `http://localhost:8000/docs` for interactive API documentation.

### Main endpoints

#### Health Check
```bash
curl http://localhost:8000/api/health
```

#### Statistics
```bash
curl http://localhost:8000/api/stats
```

#### Secrets (Admin)
```bash
# List secrets
curl http://localhost:8000/api/admin/secrets

# Create secret
curl -X POST http://localhost:8000/api/admin/secrets \
  -H "Content-Type: application/json" \
  -d '{"name": "openai-test", "type": "openai", "value": "sk-..."}'

# Delete secret
curl -X DELETE http://localhost:8000/api/admin/secrets/1
```

#### Polling Jobs
```bash
# List jobs
curl http://localhost:8000/api/jobs

# Job details
curl http://localhost:8000/api/jobs/1

# Create job
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test job",
    "batch_id": "batch_123",
    "openai_secret_id": 1,
    "keboola_secret_id": 2,
    "keboola_stack_url": "https://connection.keboola.com",
    "keboola_configuration_id": "123456",
    "poll_interval_seconds": 120
  }'

# Pause job
curl -X POST http://localhost:8000/api/jobs/1/pause

# Resume job
curl -X POST http://localhost:8000/api/jobs/1/resume
```

## Troubleshooting

### Database

**Problem**: Database initialization error
```bash
# Reset database (WARNING: deletes all data!)
python scripts/init_db.py --reset

# Check schema
python scripts/show_schema.py
```

**Problem**: SQLite locked error
- Make sure only one instance of the application is running
- Restart the application

### Secrets

**Problem**: "Secret not found" error
```bash
# Check existing secrets
teckochecker secret list

# Add missing secret
teckochecker secret add --name "name" --type "type"
```

**Problem**: Encryption error
- Check that you have SECRET_KEY set in .env
- SECRET_KEY must be the same as when secrets were created

### Polling

**Problem**: Job is not starting
```bash
# Check job status
teckochecker job show JOB_ID

# Check if polling service is running
teckochecker status

# Check logs
tail -f teckochecker.log
```

**Problem**: OpenAI API errors
- Verify API key validity
- Check rate limits
- Verify batch_id correctness

**Problem**: Keboola API errors
- Verify Storage API token validity
- Check stack URL correctness
- Verify configuration ID

### General

**Problem**: Command not found
```bash
# Reinstall
pip install -e .

# Or use direct execution
python teckochecker.py --help
```

**Problem**: Permission denied
```bash
# Set correct permissions
chmod +x teckochecker.py
chmod +x scripts/*.py
```

## Advanced Usage

### Custom polling intervals
Each job can have its own interval:
- Minimum: 30 seconds
- Maximum: 3600 seconds (1 hour)
- Recommended: 60-300 seconds

### Migration to PostgreSQL
For production deployment:
1. Install PostgreSQL
2. Create database
3. Edit DATABASE_URL in .env:
   ```
   DATABASE_URL=postgresql://user:password@localhost/teckochecker
   ```
4. Run initialization: `python scripts/init_db.py`

### Docker deployment
```bash
# Build image
docker build -t teckochecker .

# Run container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/teckochecker.db:/app/teckochecker.db \
  -v $(pwd)/.env:/app/.env \
  teckochecker
```

### Systemd service
For automatic startup on Linux server, create `/etc/systemd/system/teckochecker.service`:
```ini
[Unit]
Description=TeckoChecker Polling Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/teckochecker
Environment=PATH=/opt/teckochecker/venv/bin
ExecStart=/opt/teckochecker/venv/bin/python /opt/teckochecker/teckochecker.py start
Restart=always

[Install]
WantedBy=multi-user.target
```

## Support

For bug reports or feature suggestions, use GitHub Issues.