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
# Quick setup
make install                    # Setup environment and install dependencies
python teckochecker.py init --generate-env  # Initialize database and .env

# Running
make run-api                    # Start API server (polling starts automatically)
python teckochecker.py --help   # CLI help

# Testing and Quality
make test                       # Run all tests
make test-coverage              # Run tests with coverage
make format                     # Format and lint code

# For all available commands
make help
```

## Configuration

The application requires a `.env` file with `SECRET_KEY` (Fernet encryption for AES-256), `DATABASE_URL`, and polling interval settings. Use `python teckochecker.py init --generate-env` for automatic setup.

## Interfaces

**Dual Interface Design**: Both API and CLI call the same service layer methods.

**CLI**: Subcommands: `secret`, `job`, `db`, `doctor`, `init`, `status`, `start`, `stop`
- `doctor` and `db schema` commands work without API server running
- API returns Pydantic schemas, CLI formats output with Rich

**API**: Port 8000, Swagger at `/docs`, full REST API for secrets and jobs management

## Polling Engine

Continuous asyncio loop checks OpenAI batch status and triggers Keboola jobs on completion. Jobs processed concurrently (max 10 via semaphore), with individual poll intervals and automatic rescheduling.

## Error Handling

Exponential backoff for API errors, no retry for 4xx (except 429). Database errors rollback and continue. All errors logged to `polling_logs` table.

## Testing

- Unit tests use in-memory SQLite with mocked external APIs
- Integration tests in `tests/integration/`
- Coverage tracking with pytest-cov: `make test-coverage` and `make coverage-report`
- Comprehensive test suite for core services, API endpoints, and polling engine

## Important Implementation Notes

### SQLAlchemy 2.0 Specifics
- Raw SQL queries must use `text()` wrapper: `db.execute(text("SELECT 1"))`
- Models use modern `Mapped` type hints
- `mapped_column` instead of `Column`

### CLI Architecture
- Commands in `app/cli/commands.py` must NOT have `@typer.command()` decorators
- They are registered in `app/cli/main.py` using `app.command(name="...")(function)`
- Subcommands for secrets and jobs use their own Typer apps

### API Response Format
- List endpoints return objects with arrays, not direct arrays:
  - Secrets: `{"secrets": [...], "total": 0}`
  - Jobs: `{"jobs": [...], "total": 0}`
- CLI must extract the array: `data.get("secrets", [])`

### Project Structure
```
teckochecker/
├── app/            # Core: api/, cli/, services/, integrations/, models.py, web/
├── docs/           # PRD, architecture, user guides
├── tests/          # Unit and integration tests
├── Makefile        # Development automation
└── teckochecker.py # CLI entry point
```

### Version
Current version: 0.9.0

## Known Limitations

### CLI vs API
- Most CLI commands require API server running (except `init`, `start`, `doctor`, `db schema`)
- Polling service starts automatically with API server
- Always start API first: `make run-api` or `python teckochecker.py start`

### Deployment
- Single-tenant, admin-only access (no multi-user auth in MVP)
- SQLite database (PostgreSQL-ready for future scaling)