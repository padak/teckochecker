# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TeckoChecker is a polling orchestration system that monitors OpenAI batch job statuses and triggers Keboola Connection jobs upon completion. Built with Python 3.11+, FastAPI, SQLite, and featuring both REST API and CLI interfaces.

The project was inspired by the idea of Tomáš Trnka (tomas.trnka@live.com), who is the spiritual father of this repository.

## Key Architecture Components

### Layered Architecture
The system follows a strict layered architecture with clear separation of concerns:

1. **Interface Layer** (`app/api/`, `app/cli/`)
   - FastAPI endpoints handle REST requests with Pydantic validation
   - Typer CLI uses Rich for formatted output
   - Both interfaces share the same service layer

2. **Service Layer** (`app/services/`)
   - `polling.py`: Main orchestration engine using asyncio for concurrent job processing
   - `secrets.py`: SecretManager handles encrypted storage using Fernet
   - `scheduler.py`: JobScheduler manages polling intervals and job lifecycle
   - `encryption.py`: EncryptionService singleton for AES-256 encryption

3. **Integration Layer** (`app/integrations/`)
   - `openai_client.py`: OpenAIBatchClient with exponential backoff retry logic
   - `keboola_client.py`: KeboolaClient for triggering Storage API jobs
   - Both clients cache connections per secret_id for efficiency

4. **Data Layer** (`app/models.py`, `app/database.py`)
   - SQLAlchemy 2.0 models with modern declarative syntax
   - Three core tables: secrets, polling_jobs, polling_logs
   - Relationships use lazy loading to avoid circular imports

### Critical Design Patterns

- **Singleton Encryption**: Single EncryptionService instance initialized once with master key
- **Lazy Model Imports**: Models imported inside methods to avoid circular dependencies
- **Async Polling Loop**: Uses semaphore (max 10 concurrent) for API rate limiting
- **Client Caching**: Reuses API clients per secret to minimize connection overhead
- **Graceful Shutdown**: Interruptible sleep for responsive daemon termination

## Development Commands

```bash
# Environment setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database initialization
cp .env.example .env
# Edit .env and set SECRET_KEY or use:
python scripts/init_db.py --create-env

# Run API server
python -m uvicorn app.main:app --reload

# Run CLI (after pip install -e .)
python teckochecker.py --help

# Or directly without installation
python -m app.cli.main --help

# Run tests
python -m pytest tests/unit/test_secrets.py -v

# Integration test
python scripts/test_integration.py

# Code formatting
black app/
ruff check app/
```

## Configuration Requirements

The application requires a `.env` file with:
- `SECRET_KEY`: Required for Fernet encryption (32-byte hex string)
- `DATABASE_URL`: SQLite by default, PostgreSQL-ready
- `DEFAULT_POLL_INTERVAL`: Default 120 seconds
- `MIN_POLL_INTERVAL`: Minimum 30 seconds
- `MAX_POLL_INTERVAL`: Maximum 3600 seconds

## API and CLI Dual Interface

The system provides identical functionality through both interfaces:

- **API Server**: Runs on port 8000, provides `/api/*` endpoints
- **CLI**: Uses `teckochecker` command with subcommands for secrets and jobs
- Both interfaces call the same service layer methods
- API returns Pydantic schemas, CLI formats output with Rich

## Polling Engine Workflow

1. `PollingService.polling_loop()` runs continuously
2. `JobScheduler.get_jobs_to_check()` returns jobs where `next_check_at <= now`
3. Jobs processed concurrently with `asyncio.gather()` and semaphore limit
4. For each job:
   - Decrypt secrets via `SecretManager`
   - Check OpenAI batch status
   - If completed: trigger Keboola job
   - If pending: reschedule with job's `poll_interval_seconds`
   - If failed/expired: mark job as failed

## Error Handling Strategy

- **API Errors**: Exponential backoff (1, 2, 4... max 60 seconds) for transient failures
- **4xx Errors**: No retry except 429 (rate limit)
- **Database Errors**: Rollback transaction, log error, continue polling
- **Encryption Errors**: Fatal - stops processing for that job
- **All errors logged**: to `polling_logs` table with job_id reference

## Testing Approach

- Unit tests use in-memory SQLite (`:memory:`)
- Integration test (`test_integration.py`) verifies full stack
- Mock external APIs when testing polling logic
- Test encryption with known key/value pairs