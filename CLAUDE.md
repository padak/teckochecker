# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TeckoChecker is a polling orchestration system that monitors OpenAI batch job statuses and triggers Keboola Connection jobs upon completion. Built with Python 3.11+, FastAPI, SQLite, and featuring both REST API, CLI, and Web UI interfaces.

**Key Feature**: Multi-batch monitoring - track up to 10 OpenAI batch jobs per polling job, with automatic Keboola triggering when all batches complete.

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
   - Four core tables: secrets, polling_jobs, job_batches, polling_logs
   - Multi-batch support: job_batches table tracks individual batch status
   - Relationships use lazy/joined loading strategies to optimize queries

### Critical Design Patterns

- **Multi-Batch Processing**: Each polling job can monitor 1-10 batch IDs concurrently
- **Singleton Encryption**: Single EncryptionService instance initialized once with master key
- **Lazy Model Imports**: Models imported inside methods to avoid circular dependencies
- **Async Polling Loop**: Uses semaphore (max 10 concurrent) for API rate limiting
- **Concurrent Batch Checks**: Multiple batches checked in parallel with asyncio.gather()
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

Continuous asyncio loop checks OpenAI batch statuses and triggers Keboola jobs when all batches complete.

**Multi-Batch Flow**:
1. Jobs processed concurrently (max 10 via semaphore)
2. Each job checks multiple batches in parallel with asyncio.gather()
3. When all batches reach terminal state, Keboola is triggered with metadata
4. Metadata includes: batch_ids_completed, batch_ids_failed, counts
5. Individual poll intervals and automatic rescheduling

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
- Job responses include multi-batch fields:
  - `batches`: Array of JobBatchSchema objects
  - `batch_count`: Total number of batches
  - `completed_count`: Count of completed batches
  - `failed_count`: Count of failed/cancelled/expired batches

### Keboola Variables Integration
TeckoChecker uses Keboola's `variableValuesData` (inline variables) to pass batch metadata:

**How it works:**
1. **TeckoChecker** sends batch metadata as `variableValuesData` in the job trigger request
2. **KeboolaClient** automatically converts parameters to Keboola variable format:
   - Lists → JSON strings: `json.dumps(["batch_001"])`
   - Numbers → strings: `str(42)`
3. **Keboola** maps variables to User Parameters in the Custom Python component
4. **Python script** receives variables directly via `CommonInterface.configuration.parameters`

**Key points:**
- Variables are **NOT nested** in `user_properties` - they're in root `parameters`
- Lists come as JSON strings and must be parsed: `json.loads(params["batch_ids_completed"])`
- Numbers come as strings and must be converted: `int(params["batch_count_total"])`
- See `demo/keboola_config.json` for User Parameters configuration example
- See `demo/keboola_batch_handler.py` for receiving script implementation
- Use `scripts/test_trigger_keboola.py` to test Keboola triggering independently

**Secrets handling:**
- Secrets are automatically trimmed (`.strip()`) when stored and retrieved
- Prevents issues with accidental whitespace in API tokens
- Applied in `SecretManager.create_secret()` and `get_decrypted_value()`

### Project Structure
```
teckochecker/
├── app/            # Core: api/, cli/, services/, integrations/, models.py, web/
├── demo/           # OpenAI Batch API and Keboola integration demos
├── docs/           # PRD, architecture, user guides, migration guides
├── tests/          # Unit and integration tests
├── Makefile        # Development automation
└── teckochecker.py # CLI entry point
```

### Version
Current version: 0.9.5

**New in v0.9.5 (Multi-Batch Feature)**:
- API now accepts `batch_ids` (array) instead of `batch_id` (string)
- Responses include `batches` array with individual batch status
- CLI `--batch-id` flag can be repeated for multi-batch jobs (1-10 batches)
- Web UI shows batch completion ratios and auto-refreshes
- See `docs/MIGRATION_v0.9_to_v1.0.md` for migration guide from v0.9.0

## Known Limitations

### CLI vs API
- Most CLI commands require API server running (except `init`, `start`, `doctor`, `db schema`)
- Polling service starts automatically with API server
- Always start API first: `make run-api` or `python teckochecker.py start`

### Deployment
- Single-tenant, admin-only access (no multi-user auth in MVP)
- SQLite database (PostgreSQL-ready for future scaling)

## Demo Scripts

The `demo/` directory contains practical examples:

1. **OpenAI Batch API Demo** (`openai_batch_demo.py`)
   - Standalone script for testing OpenAI Batch API
   - Creates, monitors, and downloads batch results
   - See `demo/README_OPENAI.md`

2. **Keboola Integration Demo** (`keboola_batch_handler.py`)
   - Keboola Custom Python script receives batch metadata from TeckoChecker
   - Processes completion notifications with batch IDs and counts
   - Deploy to Keboola Custom Python component
   - See `demo/README_KEBOOLA.md`

Both demos are documented in `demo/README.md` with quick start instructions.

## Available Skills

Skills are specialized tools invoked via the Skill tool when needed:

- **codex**: Interact with OpenAI Codex CLI for second opinions, multi-model analysis, and structured output generation. Useful for code review from different AI perspective, architectural validation, or when you need structured JSON responses with schemas.

Usage: "Use the codex skill to [task]" or "Invoke codex skill"

### Key Principles
1. **Agent-First Workflow**: When the work plan allows, prefer using sub-agents (Task tool) for complex, multi-step tasks. This enables parallel execution, specialized expertise, and better resource management. Use sub-agents for exploration, testing, documentation, and any task that can be delegated.