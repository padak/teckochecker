# TeckoChecker Custom Check Jobs - Product & Technical Specification

**Document Version:** 1.0
**Last Updated:** 2025-01-24
**Status:** Draft for Review
**Author:** Padak

---

## Table of Contents

1. [Introduction](#introduction)
2. [Use Cases and Requirements](#use-cases-and-requirements)
3. [Feature Scope and Integration Strategy](#feature-scope-and-integration-strategy)
4. [Tech Stack](#tech-stack)
5. [Data Models and Schema](#data-models-and-schema)
6. [Component Architecture](#component-architecture)
7. [API Design](#api-design)
8. [Script Output Specification](#script-output-specification)
9. [Performance and Scalability](#performance-and-scalability)
10. [Security](#security)
11. [Testing Strategy](#testing-strategy)
12. [Implementation Phases](#implementation-phases)
13. [Open Questions and Future Enhancements](#open-questions-and-future-enhancements)

---

## Introduction

### Vision

Transform TeckoChecker from a specialized "OpenAI batch poller" into a **universal async task monitoring platform** with pluggable check logic. Enable users to monitor arbitrary async processes (Gemini API, custom pipelines, CI/CD jobs) by providing their own check scripts that execute safely in E2B sandboxes.

### Current State vs. Target State

**Current State:**
```
TeckoChecker → OpenAI API (hardcoded) → check batch status → trigger Keboola
```

**Target State:**
```
TeckoChecker → Custom Script (user-defined) → check anything → trigger webhook/Keboola
                ↓
           E2B Sandbox (safe, isolated execution)
```

### Key Differentiators

- **Flexibility**: Monitor any async task, not just OpenAI batches
- **Safety**: Execute untrusted user code in E2B sandboxes
- **Simplicity**: Standard output format (JSON with status field)
- **Scale**: Handle 500+ active jobs with 50+ concurrent checks
- **Extensibility**: Python and Node.js support with dependency management

### Relationship to Existing Architecture

This feature **extends** TeckoChecker's existing polling architecture without modifying the current OpenAI polling flow. Both systems run in parallel:
- **Existing**: `PollingJob` for OpenAI batch monitoring (unchanged)
- **New**: `CustomCheckJob` for generic async task monitoring

Future versions may consolidate OpenAI polling as a built-in custom check, but v1.0 maintains backward compatibility.

---

## Use Cases and Requirements

### Use Case 1: Monitor Gemini API Batch Jobs

**Actor:** Data Engineer
**Goal:** Poll Gemini API batch status similar to OpenAI

**Flow:**
1. Upload Python script that calls Gemini API
2. Configure env vars (API key via secret reference)
3. Schedule polling every 2 minutes
4. Trigger webhook when batch completes

**Success Criteria:**
- Script executes in isolated sandbox
- Gemini API credentials injected securely
- Webhook triggered with completion data

---

### Use Case 2: Custom Async Task Monitoring

**Actor:** DevOps Engineer
**Goal:** Monitor arbitrary async processes (CI/CD jobs, data pipelines, ML training)

**Flow:**
1. Provide GitHub URL to check script
2. Configure check parameters (job ID, API endpoint)
3. Poll status until completion
4. Trigger action (webhook, Slack notification)

**Success Criteria:**
- Script fetched from Git on every poll (fresh commit)
- Dependencies installed automatically
- Flexible output schema

---

### Use Case 3: Multi-Provider Batch Jobs

**Actor:** ML Engineer
**Goal:** Monitor batch jobs across multiple AI providers

**Flow:**
1. Create multiple custom check jobs (OpenAI, Anthropic, Gemini)
2. Each job has provider-specific script
3. Monitor all jobs concurrently
4. Aggregate results via webhook

**Success Criteria:**
- Multiple jobs run in parallel
- No cross-contamination between scripts
- Concurrent execution scales to 50+ jobs

---

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Support both Git URL and direct file upload as script sources | **MUST** |
| FR-2 | Execute scripts in Python or Node.js runtimes | **MUST** |
| FR-3 | Auto-install dependencies from requirements.txt / package.json | **MUST** |
| FR-4 | Inject environment variables (with secret references) | **MUST** |
| FR-5 | Parse standardized JSON output from scripts | **MUST** |
| FR-6 | Trigger generic HTTP webhooks on completion | **MUST** |
| FR-7 | Support configurable timeouts per job | **SHOULD** |
| FR-8 | Store script execution logs and outputs | **MUST** |
| FR-9 | Provide CLI and API interfaces for management | **MUST** |
| FR-10 | Maintain backward compatibility with existing OpenAI polling | **MUST** |

---

### Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | **Scale**: Support 500+ active jobs | 500 concurrent jobs |
| NFR-2 | **Concurrency**: Execute 50+ checks simultaneously | 50 parallel E2B sessions |
| NFR-3 | **Latency**: Start script execution within 5 seconds | < 5s from poll trigger |
| NFR-4 | **Isolation**: Zero cross-contamination between script executions | 100% isolation |
| NFR-5 | **Security**: Encrypted secret storage, no credential leakage | AES-256 encryption |
| NFR-6 | **Reliability**: 99% polling loop uptime | Graceful error handling |
| NFR-7 | **Storage**: Limit script size to 50MB (compressed) | Max 50MB .tgz |

---

## Feature Scope and Integration Strategy

### In-Scope (v1.0)

✅ **Core Infrastructure:**
- Database schema (`custom_check_jobs`, `custom_check_logs`)
- Script storage service (filesystem-based)
- E2B executor service (Python/Node)
- Generic webhook trigger client

✅ **API Layer:**
- CRUD endpoints for custom check jobs
- Script upload/Git config endpoints
- Job control (pause/resume/trigger)
- Execution log retrieval

✅ **CLI Interface:**
- `teckochecker.py custom-check create/list/delete`
- `teckochecker.py custom-check upload-script`
- `teckochecker.py custom-check trigger`

✅ **Polling Integration:**
- Extend existing `PollingService` to process both job types
- Unified scheduler for `PollingJob` and `CustomCheckJob`

✅ **Web UI (Basic):**
- List custom check jobs
- View execution logs
- Manual trigger button

---

### Out-of-Scope (Future)

❌ **Not in v1.0:**
- Script versioning/rollback
- Multi-step workflows (DAGs)
- Retry logic with exponential backoff (basic retry only)
- Advanced webhook features (retries, circuit breaker)
- Script marketplace/templates
- Metrics dashboard (Prometheus/Grafana)
- PostgreSQL support (SQLite only)

---

## Tech Stack

### New Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| **e2b-code-interpreter** | ^0.0.10 | E2B SDK for sandbox execution |
| **GitPython** | ^3.1.40 | Clone Git repositories for script fetching |
| **tarfile** (stdlib) | - | Create/extract .tgz archives |

### Existing Stack (Unchanged)

- Python 3.11+
- FastAPI 0.104+
- SQLAlchemy 2.0+
- SQLite 3.38+
- asyncio for concurrency

### Runtime Environments

Scripts execute in E2B sandboxes with:
- **Python**: 3.11+ with pip
- **Node.js**: 20+ with npm

---

## Data Models and Schema

### New Table: `custom_check_jobs`

```sql
CREATE TABLE custom_check_jobs (
    -- Core fields
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,

    -- Script configuration
    script_source_type VARCHAR(20) NOT NULL, -- 'git' or 'upload'
    script_git_url VARCHAR(500),
    script_git_branch VARCHAR(100),
    script_file_path VARCHAR(500),          -- Path to local .tgz
    script_runtime VARCHAR(20) NOT NULL,    -- 'python' or 'node'
    script_entrypoint VARCHAR(255) NOT NULL DEFAULT 'main.py',

    -- Execution configuration
    check_params TEXT NOT NULL,             -- JSON: {"batch_id": "..."}
    env_vars TEXT,                          -- JSON: {"API_KEY": "secret_ref:1"}
    timeout_seconds INTEGER DEFAULT 300,

    -- Webhook action
    webhook_url VARCHAR(500),
    webhook_method VARCHAR(10) DEFAULT 'POST',
    webhook_headers TEXT,                   -- JSON

    -- Polling configuration
    poll_interval_seconds INTEGER DEFAULT 120,

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active, paused, completed, failed
    last_check_status VARCHAR(50),          -- Script output status
    last_check_data TEXT,                   -- JSON from script

    -- Timestamps
    last_check_at DATETIME,
    next_check_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,

    -- Indexes
    INDEX idx_custom_check_status (status),
    INDEX idx_custom_check_next_check (next_check_at)
);
```

### New Table: `custom_check_logs`

```sql
CREATE TABLE custom_check_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,            -- checking, success, failed, error
    message TEXT,
    script_output TEXT,                     -- Full JSON output from script
    execution_time_ms INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES custom_check_jobs(id) ON DELETE CASCADE,
    INDEX idx_custom_log_job_created (job_id, created_at),
    INDEX idx_custom_log_status (status)
);
```

### SQLAlchemy Models

```python
class CustomCheckJob(Base):
    """Polling job for custom user-defined check scripts."""
    __tablename__ = "custom_check_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Script configuration
    script_source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    script_git_url: Mapped[Optional[str]] = mapped_column(String(500))
    script_git_branch: Mapped[Optional[str]] = mapped_column(String(100), default="main")
    script_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    script_runtime: Mapped[str] = mapped_column(String(20), nullable=False)
    script_entrypoint: Mapped[str] = mapped_column(String(255), default="main.py")

    # Execution configuration
    check_params: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    env_vars: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)

    # Webhook action
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500))
    webhook_method: Mapped[str] = mapped_column(String(10), default="POST")
    webhook_headers: Mapped[Optional[str]] = mapped_column(Text)  # JSON

    # Polling configuration
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=120)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    last_check_status: Mapped[Optional[str]] = mapped_column(String(50))
    last_check_data: Mapped[Optional[str]] = mapped_column(Text)  # JSON

    # Timestamps
    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    logs: Mapped[list["CustomCheckLog"]] = relationship(
        "CustomCheckLog",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="CustomCheckLog.created_at.desc()"
    )


class CustomCheckLog(Base):
    """Execution logs for custom check jobs."""
    __tablename__ = "custom_check_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("custom_check_jobs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    script_output: Mapped[Optional[str]] = mapped_column(Text)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["CustomCheckJob"] = relationship("CustomCheckJob", back_populates="logs")
```

---

## Component Architecture

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Interface Layer                                            │
│  - FastAPI Endpoints (app/api/custom_checks.py)            │
│  - CLI Commands (app/cli/commands.py)                      │
│  - Web UI (app/web/*)                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Service Layer                                              │
│  - PollingService (extended for CustomCheckJob)            │
│  - ScriptStorageService (new)                              │
│  - E2BExecutor (new)                                       │
│  - SecretManager (existing, reused)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Integration Layer                                          │
│  - WebhookClient (new)                                     │
│  - E2B SDK (new)                                           │
│  - GitPython (new)                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Data Layer                                                 │
│  - CustomCheckJob, CustomCheckLog models (new)             │
│  - Secret model (existing, reused)                         │
│  - SQLite database                                         │
└─────────────────────────────────────────────────────────────┘
```

---

### New Services

#### 1. ScriptStorageService (`app/services/script_storage.py`)

**Purpose:** Manage script storage, validation, and retrieval.

**Directory Structure:**
```
/var/teckochecker/scripts/
├── {job_id}/
│   ├── script.tgz          # Uploaded or git-fetched archive (max 50MB)
│   ├── metadata.json       # Script metadata (git commit, upload timestamp)
│   └── extracted/          # Temporary extraction (cleaned after each poll)
│       ├── main.py
│       ├── requirements.txt
│       └── ...
```

**Key Methods:**
```python
class ScriptStorageService:
    MAX_SCRIPT_SIZE_MB = 50
    STORAGE_ROOT = "/var/teckochecker/scripts"

    async def store_uploaded_script(self, job_id: int, file: UploadFile) -> str:
        """
        Validate and store uploaded .tgz file.
        - Check size <= 50MB
        - Validate tar format
        - Store to {STORAGE_ROOT}/{job_id}/script.tgz
        - Update metadata.json
        """

    async def fetch_git_script(self, job_id: int, git_url: str, branch: str) -> str:
        """
        Clone Git repo and create .tgz archive.
        - Clone to temp directory
        - Create .tgz archive (exclude .git/)
        - Store to {STORAGE_ROOT}/{job_id}/script.tgz
        - Update metadata.json with commit hash
        """

    async def extract_script(self, job_id: int) -> str:
        """
        Extract script.tgz to temporary directory.
        - Extract to {STORAGE_ROOT}/{job_id}/extracted/
        - Return path to extracted directory
        """

    async def cleanup_extraction(self, job_id: int) -> None:
        """Remove extracted files."""

    async def get_script_path(self, job_id: int) -> str:
        """Get path to script.tgz for job."""
```

---

#### 2. E2BExecutor (`app/services/e2b_executor.py`)

**Purpose:** Execute custom scripts in E2B sandboxes.

**Key Methods:**
```python
from e2b_code_interpreter import Sandbox

class E2BExecutor:
    """Executes custom check scripts in E2B sandbox."""

    async def execute_check(
        self,
        job: CustomCheckJob,
        script_path: str,
        db_session
    ) -> Dict[str, Any]:
        """
        Execute custom check script in E2B sandbox.

        Flow:
        1. Create E2B sandbox (Python or Node)
        2. Resolve env_vars (decrypt secret references)
        3. Upload script files to sandbox
        4. Install dependencies (requirements.txt / package.json)
        5. Execute entrypoint script with check_params
        6. Parse JSON output from stdout
        7. Validate output format
        8. Cleanup sandbox

        Returns:
            {
                "status": "SUCCESS|FAILED|PENDING|ERROR",
                "data": {...},
                "message": "..."
            }
        """
        sandbox = None
        start_time = time.time()

        try:
            # 1. Create sandbox
            sandbox = await self._create_sandbox(job.script_runtime)

            # 2. Resolve and set environment variables
            env_vars = await self._resolve_env_vars(job.env_vars, db_session)
            for key, value in env_vars.items():
                sandbox.set_env(key, value)

            # 3. Upload script
            await self._upload_script(sandbox, script_path)

            # 4. Install dependencies
            await self._install_dependencies(sandbox, job.script_runtime, script_path)

            # 5. Execute script with timeout
            execution_cmd = self._build_execution_command(job)
            execution = await asyncio.wait_for(
                sandbox.run_code(execution_cmd),
                timeout=job.timeout_seconds
            )

            # 6. Parse output
            output = self._parse_output(execution.stdout)
            output["execution_time_ms"] = int((time.time() - start_time) * 1000)

            return output

        except asyncio.TimeoutError:
            return {
                "status": "ERROR",
                "message": f"Execution timeout after {job.timeout_seconds}s",
                "data": {}
            }
        except Exception as e:
            logger.exception(f"E2B execution failed: {e}")
            return {
                "status": "ERROR",
                "message": str(e),
                "data": {}
            }
        finally:
            if sandbox:
                await sandbox.close()

    async def _create_sandbox(self, runtime: str) -> Sandbox:
        """Create E2B sandbox for Python or Node."""
        if runtime == "python":
            return Sandbox(template="python")
        elif runtime == "node":
            return Sandbox(template="node")
        else:
            raise ValueError(f"Unsupported runtime: {runtime}")

    async def _resolve_env_vars(self, env_vars_json: str, db_session) -> Dict[str, str]:
        """
        Resolve env_vars JSON, decrypt secret references.

        Example:
            Input: {"API_KEY": "secret_ref:1", "CUSTOM": "value"}
            Output: {"API_KEY": "decrypted_api_key", "CUSTOM": "value"}
        """
        if not env_vars_json:
            return {}

        env_vars = json.loads(env_vars_json)
        resolved = {}

        # Lazy import to avoid circular dependency
        from app.services.secrets import SecretManager
        secret_manager = SecretManager(db_session)

        for key, value in env_vars.items():
            if isinstance(value, str) and value.startswith("secret_ref:"):
                secret_id = int(value.split(":")[1])
                resolved[key] = await secret_manager.get_decrypted_value(secret_id)
            else:
                resolved[key] = value

        return resolved

    async def _upload_script(self, sandbox: Sandbox, script_path: str) -> None:
        """Upload and extract script files to sandbox."""
        # Extract locally first
        extract_path = script_path.replace(".tgz", "_extracted")
        with tarfile.open(script_path, "r:gz") as tar:
            tar.extractall(extract_path)

        # Upload files to sandbox
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                local_path = os.path.join(root, file)
                remote_path = os.path.relpath(local_path, extract_path)
                with open(local_path, "rb") as f:
                    sandbox.upload_file(remote_path, f.read())

    async def _install_dependencies(
        self,
        sandbox: Sandbox,
        runtime: str,
        script_path: str
    ) -> None:
        """Install dependencies from requirements.txt / package.json."""
        if runtime == "python":
            # Check for requirements.txt
            result = await sandbox.run_code("ls requirements.txt")
            if result.exit_code == 0:
                await sandbox.run_code("pip install -r requirements.txt")

        elif runtime == "node":
            # Check for package.json
            result = await sandbox.run_code("ls package.json")
            if result.exit_code == 0:
                await sandbox.run_code("npm install")

    def _build_execution_command(self, job: CustomCheckJob) -> str:
        """Build execution command with check_params as JSON stdin."""
        if job.script_runtime == "python":
            return f"python {job.script_entrypoint}"
        elif job.script_runtime == "node":
            return f"node {job.script_entrypoint}"

    def _parse_output(self, stdout: str) -> Dict[str, Any]:
        """
        Parse JSON output from script stdout.

        Expected format:
        {
            "status": "SUCCESS|FAILED|PENDING|ERROR",
            "data": {...},
            "message": "..."
        }
        """
        try:
            # Extract last JSON object from stdout (in case of logs)
            lines = stdout.strip().split("\n")
            for line in reversed(lines):
                try:
                    output = json.loads(line)
                    if "status" in output:
                        return output
                except json.JSONDecodeError:
                    continue

            # No valid JSON found
            return {
                "status": "ERROR",
                "message": "Script did not output valid JSON",
                "data": {"raw_output": stdout[:1000]}
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Failed to parse output: {e}",
                "data": {}
            }
```

---

#### 3. WebhookClient (`app/integrations/webhook_client.py`)

**Purpose:** Trigger generic HTTP webhooks with check results.

```python
import httpx
from typing import Dict, Any

class WebhookClient:
    """Triggers generic HTTP webhooks with custom check results."""

    DEFAULT_TIMEOUT = 30  # seconds

    async def trigger_webhook(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> bool:
        """
        Send HTTP request to webhook URL.

        Args:
            url: Webhook endpoint URL
            method: HTTP method (GET, POST, PUT, etc.)
            headers: Custom headers
            payload: JSON payload

        Returns:
            True if successful (2xx status), False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                logger.info(f"Webhook triggered successfully: {url} (status={response.status_code})")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"Webhook failed with status {e.response.status_code}: {url}")
            return False
        except Exception as e:
            logger.exception(f"Webhook failed: {url} - {e}")
            return False

    def build_payload(
        self,
        job: CustomCheckJob,
        check_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build webhook payload from check result.

        Payload structure:
        {
            "job_id": 123,
            "job_name": "Check Gemini API Batch",
            "check_status": "SUCCESS",
            "check_data": {...},
            "check_message": "Batch completed successfully",
            "timestamp": "2025-01-24T10:00:00Z",
            "execution_time_ms": 1234
        }
        """
        return {
            "job_id": job.id,
            "job_name": job.name,
            "check_status": check_result.get("status"),
            "check_data": check_result.get("data", {}),
            "check_message": check_result.get("message"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": check_result.get("execution_time_ms")
        }
```

---

### Modified Services

#### PollingService Extension

**Extend existing** `app/services/polling.py` to handle both job types:

```python
class PollingService:
    """Main polling service (extended for custom checks)."""

    # Updated concurrency limits
    MAX_CONCURRENT_CHECKS = 50  # Increased from 10 to 50
    POLL_BATCH_SIZE = 100       # Increased from 50 to 100

    async def _process_jobs_concurrent(
        self,
        jobs: List[Union[PollingJob, CustomCheckJob]]
    ):
        """Process both polling jobs and custom check jobs concurrently."""
        semaphore = asyncio.Semaphore(self.max_concurrent_checks)
        tasks = []

        for job in jobs:
            if isinstance(job, PollingJob):
                tasks.append(
                    self._check_with_semaphore(
                        semaphore, job, self._process_polling_job
                    )
                )
            elif isinstance(job, CustomCheckJob):
                tasks.append(
                    self._check_with_semaphore(
                        semaphore, job, self._process_custom_check_job
                    )
                )

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_custom_check_job(self, job: CustomCheckJob) -> None:
        """
        Process custom check job.

        Flow:
        1. Log check start
        2. Fetch/extract script
        3. Execute in E2B sandbox
        4. Parse result
        5. Update job status
        6. Trigger webhook if completed
        7. Reschedule or mark complete
        8. Cleanup
        """
        with self._create_db_session() as db:
            try:
                # Lazy imports
                from app.services.script_storage import ScriptStorageService
                from app.services.e2b_executor import E2BExecutor
                from app.integrations.webhook_client import WebhookClient

                storage = ScriptStorageService()
                executor = E2BExecutor()
                webhook = WebhookClient()

                # Log start
                self._log_custom_check(db, job.id, "checking", "Starting check")

                # Fetch script (git or local)
                if job.script_source_type == "git":
                    script_path = await storage.fetch_git_script(
                        job.id, job.script_git_url, job.script_git_branch
                    )
                else:
                    script_path = await storage.get_script_path(job.id)

                # Extract script
                extracted_path = await storage.extract_script(job.id)

                # Execute in E2B
                result = await executor.execute_check(job, extracted_path, db)

                # Update job with result
                job.last_check_status = result["status"]
                job.last_check_data = json.dumps(result.get("data", {}))
                job.last_check_at = datetime.now(timezone.utc)

                # Log result
                self._log_custom_check(
                    db, job.id,
                    result["status"].lower(),
                    result.get("message", "Check completed"),
                    script_output=json.dumps(result),
                    execution_time_ms=result.get("execution_time_ms")
                )

                # Handle status transitions
                if result["status"] in ["SUCCESS", "FAILED"]:
                    # Terminal state - trigger webhook
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)

                    if job.webhook_url:
                        webhook_headers = json.loads(job.webhook_headers or "{}")
                        payload = webhook.build_payload(job, result)

                        success = await webhook.trigger_webhook(
                            job.webhook_url,
                            job.webhook_method,
                            webhook_headers,
                            payload
                        )

                        if success:
                            self._log_custom_check(db, job.id, "triggered", "Webhook triggered")

                elif result["status"] == "PENDING":
                    # Continue polling
                    job.next_check_at = datetime.now(timezone.utc) + timedelta(
                        seconds=job.poll_interval_seconds
                    )

                elif result["status"] == "ERROR":
                    # Error - retry next check
                    job.next_check_at = datetime.now(timezone.utc) + timedelta(
                        seconds=job.poll_interval_seconds
                    )

                db.commit()

                # Cleanup
                await storage.cleanup_extraction(job.id)

            except Exception as e:
                logger.exception(f"Custom check job {job.id} failed: {e}")
                self._log_custom_check(db, job.id, "error", str(e))
                db.rollback()

    def _log_custom_check(
        self,
        db,
        job_id: int,
        status: str,
        message: str,
        script_output: str = None,
        execution_time_ms: int = None
    ):
        """Create custom check log entry."""
        from app.models import CustomCheckLog

        log = CustomCheckLog(
            job_id=job_id,
            status=status,
            message=message,
            script_output=script_output,
            execution_time_ms=execution_time_ms
        )
        db.add(log)
        db.commit()
```

---

## API Design

### New Endpoints (`app/api/custom_checks.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/custom-checks", tags=["Custom Checks"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class CustomCheckJobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    script_source_type: Literal["git", "upload"]
    script_git_url: Optional[str] = Field(None, max_length=500)
    script_git_branch: str = Field("main", max_length=100)
    script_runtime: Literal["python", "node"]
    script_entrypoint: str = Field("main.py", max_length=255)
    check_params: Dict[str, Any] = Field(..., description="JSON object with check parameters")
    env_vars: Optional[Dict[str, str]] = Field(None, description="Env vars (use 'secret_ref:<id>' for secrets)")
    timeout_seconds: int = Field(300, ge=10, le=3600)
    webhook_url: Optional[str] = Field(None, max_length=500)
    webhook_method: str = Field("POST", regex="^(GET|POST|PUT|PATCH|DELETE)$")
    webhook_headers: Optional[Dict[str, str]] = None
    poll_interval_seconds: int = Field(120, ge=10, le=86400)


class CustomCheckJobUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    check_params: Optional[Dict[str, Any]] = None
    env_vars: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=10, le=3600)
    webhook_url: Optional[str] = Field(None, max_length=500)
    webhook_method: Optional[str] = Field(None, regex="^(GET|POST|PUT|PATCH|DELETE)$")
    webhook_headers: Optional[Dict[str, str]] = None
    poll_interval_seconds: Optional[int] = Field(None, ge=10, le=86400)


class CustomCheckJobSchema(BaseModel):
    id: int
    name: str
    script_source_type: str
    script_git_url: Optional[str]
    script_git_branch: Optional[str]
    script_runtime: str
    script_entrypoint: str
    check_params: Dict[str, Any]
    env_vars: Optional[Dict[str, str]]
    timeout_seconds: int
    webhook_url: Optional[str]
    webhook_method: str
    webhook_headers: Optional[Dict[str, str]]
    poll_interval_seconds: int
    status: str
    last_check_status: Optional[str]
    last_check_data: Optional[Dict[str, Any]]
    last_check_at: Optional[datetime]
    next_check_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class CustomCheckLogSchema(BaseModel):
    id: int
    job_id: int
    status: str
    message: Optional[str]
    script_output: Optional[Dict[str, Any]]
    execution_time_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.post("/", response_model=CustomCheckJobSchema, status_code=201)
async def create_custom_check_job(
    job_data: CustomCheckJobCreate,
    db: Session = Depends(get_db)
):
    """Create a new custom check job."""
    from app.models import CustomCheckJob

    # Validate script source
    if job_data.script_source_type == "git" and not job_data.script_git_url:
        raise HTTPException(400, "script_git_url required for git source")

    # Create job
    job = CustomCheckJob(
        name=job_data.name,
        script_source_type=job_data.script_source_type,
        script_git_url=job_data.script_git_url,
        script_git_branch=job_data.script_git_branch,
        script_runtime=job_data.script_runtime,
        script_entrypoint=job_data.script_entrypoint,
        check_params=json.dumps(job_data.check_params),
        env_vars=json.dumps(job_data.env_vars) if job_data.env_vars else None,
        timeout_seconds=job_data.timeout_seconds,
        webhook_url=job_data.webhook_url,
        webhook_method=job_data.webhook_method,
        webhook_headers=json.dumps(job_data.webhook_headers) if job_data.webhook_headers else None,
        poll_interval_seconds=job_data.poll_interval_seconds,
        status="active",
        next_check_at=datetime.now(timezone.utc)
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


@router.get("/", response_model=Dict[str, Any])
async def list_custom_check_jobs(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List custom check jobs with optional filtering."""
    from app.models import CustomCheckJob

    query = db.query(CustomCheckJob)

    if status:
        query = query.filter(CustomCheckJob.status == status)

    total = query.count()
    jobs = query.offset(offset).limit(limit).all()

    return {
        "jobs": jobs,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/{job_id}", response_model=CustomCheckJobSchema)
async def get_custom_check_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get custom check job by ID."""
    from app.models import CustomCheckJob

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    return job


@router.put("/{job_id}", response_model=CustomCheckJobSchema)
async def update_custom_check_job(
    job_id: int,
    job_data: CustomCheckJobUpdate,
    db: Session = Depends(get_db)
):
    """Update custom check job configuration."""
    from app.models import CustomCheckJob

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    # Update fields
    if job_data.name:
        job.name = job_data.name
    if job_data.check_params:
        job.check_params = json.dumps(job_data.check_params)
    if job_data.env_vars is not None:
        job.env_vars = json.dumps(job_data.env_vars)
    if job_data.timeout_seconds:
        job.timeout_seconds = job_data.timeout_seconds
    if job_data.webhook_url is not None:
        job.webhook_url = job_data.webhook_url
    if job_data.webhook_method:
        job.webhook_method = job_data.webhook_method
    if job_data.webhook_headers is not None:
        job.webhook_headers = json.dumps(job_data.webhook_headers)
    if job_data.poll_interval_seconds:
        job.poll_interval_seconds = job_data.poll_interval_seconds

    db.commit()
    db.refresh(job)

    return job


@router.delete("/{job_id}", status_code=204)
async def delete_custom_check_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Delete custom check job and all associated data."""
    from app.models import CustomCheckJob
    from app.services.script_storage import ScriptStorageService

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    # Delete script files
    storage = ScriptStorageService()
    await storage.delete_script(job_id)

    # Delete job (cascades to logs)
    db.delete(job)
    db.commit()


# ============================================================================
# Script Management
# ============================================================================

@router.post("/{job_id}/script/upload", status_code=200)
async def upload_script(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload script .tgz file for custom check job."""
    from app.models import CustomCheckJob
    from app.services.script_storage import ScriptStorageService

    # Validate job
    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    if job.script_source_type != "upload":
        raise HTTPException(400, "Job not configured for upload source")

    # Validate file
    if not file.filename.endswith(".tgz") and not file.filename.endswith(".tar.gz"):
        raise HTTPException(400, "File must be .tgz or .tar.gz")

    # Store script
    storage = ScriptStorageService()
    script_path = await storage.store_uploaded_script(job_id, file)

    # Update job
    job.script_file_path = script_path
    db.commit()

    return {"message": "Script uploaded successfully", "path": script_path}


@router.post("/{job_id}/script/git", status_code=200)
async def configure_git_script(
    job_id: int,
    git_url: str,
    branch: str = "main",
    db: Session = Depends(get_db)
):
    """Configure Git source for custom check job."""
    from app.models import CustomCheckJob

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    if job.script_source_type != "git":
        raise HTTPException(400, "Job not configured for git source")

    # Update job
    job.script_git_url = git_url
    job.script_git_branch = branch
    db.commit()

    return {"message": "Git source configured", "url": git_url, "branch": branch}


@router.get("/{job_id}/script/info")
async def get_script_info(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get script metadata for custom check job."""
    from app.models import CustomCheckJob
    from app.services.script_storage import ScriptStorageService

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    storage = ScriptStorageService()
    metadata = await storage.get_metadata(job_id)

    return {
        "job_id": job_id,
        "source_type": job.script_source_type,
        "git_url": job.script_git_url,
        "git_branch": job.script_git_branch,
        "file_path": job.script_file_path,
        "metadata": metadata
    }


# ============================================================================
# Control Endpoints
# ============================================================================

@router.post("/{job_id}/pause", status_code=200)
async def pause_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Pause custom check job polling."""
    from app.models import CustomCheckJob

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    job.status = "paused"
    job.next_check_at = None
    db.commit()

    return {"message": "Job paused", "job_id": job_id}


@router.post("/{job_id}/resume", status_code=200)
async def resume_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Resume custom check job polling."""
    from app.models import CustomCheckJob

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    job.status = "active"
    job.next_check_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Job resumed", "job_id": job_id}


@router.post("/{job_id}/trigger", status_code=200)
async def trigger_job_now(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Trigger custom check job immediately (force check now)."""
    from app.models import CustomCheckJob

    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    job.next_check_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Job triggered", "job_id": job_id}


# ============================================================================
# Logs
# ============================================================================

@router.get("/{job_id}/logs", response_model=Dict[str, Any])
async def get_job_logs(
    job_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get execution logs for custom check job."""
    from app.models import CustomCheckJob, CustomCheckLog

    # Verify job exists
    job = db.query(CustomCheckJob).filter(CustomCheckJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Custom check job {job_id} not found")

    # Query logs
    query = db.query(CustomCheckLog).filter(CustomCheckLog.job_id == job_id)
    query = query.order_by(CustomCheckLog.created_at.desc())

    total = query.count()
    logs = query.offset(offset).limit(limit).all()

    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset
    }
```

---

## Script Output Specification

### Required Output Format

Custom check scripts MUST output JSON to `stdout` with the following structure:

```json
{
  "status": "SUCCESS|FAILED|PENDING|ERROR",
  "data": {
    "custom_field_1": "value",
    "custom_field_2": 123
  },
  "message": "Optional human-readable status message"
}
```

### Status Values

| Status | Meaning | TeckoChecker Action |
|--------|---------|---------------------|
| `SUCCESS` | Check completed, async task finished successfully | Trigger webhook → Mark job `completed` |
| `FAILED` | Check completed, async task failed | Trigger webhook → Mark job `completed` |
| `PENDING` | Check completed, async task still in progress | Reschedule next check → Continue polling |
| `ERROR` | Check execution failed (script error, API error) | Log error → Retry next check |

### Example Scripts

#### Python Example (`main.py`)

```python
#!/usr/bin/env python3
import json
import os
import sys
import requests

def check_gemini_batch():
    """Check Gemini API batch status."""

    # Get parameters from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    batch_id = os.environ.get("BATCH_ID")

    if not api_key or not batch_id:
        return {
            "status": "ERROR",
            "message": "Missing required environment variables",
            "data": {}
        }

    try:
        # Call Gemini API
        response = requests.get(
            f"https://gemini.googleapis.com/v1/batches/{batch_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )
        response.raise_for_status()

        batch = response.json()
        state = batch.get("state")

        # Map Gemini states to TeckoChecker statuses
        if state == "COMPLETED":
            return {
                "status": "SUCCESS",
                "data": {
                    "batch_id": batch_id,
                    "completed_at": batch.get("completedAt"),
                    "result_count": batch.get("resultCount", 0)
                },
                "message": f"Batch {batch_id} completed successfully"
            }

        elif state in ["FAILED", "CANCELLED"]:
            return {
                "status": "FAILED",
                "data": {
                    "batch_id": batch_id,
                    "error": batch.get("error", {}).get("message")
                },
                "message": f"Batch {batch_id} failed"
            }

        elif state in ["PENDING", "RUNNING"]:
            return {
                "status": "PENDING",
                "data": {
                    "batch_id": batch_id,
                    "progress": batch.get("progress", 0)
                },
                "message": f"Batch {batch_id} still processing ({batch.get('progress', 0)}%)"
            }

        else:
            return {
                "status": "ERROR",
                "message": f"Unknown batch state: {state}",
                "data": {"batch_id": batch_id, "state": state}
            }

    except requests.exceptions.RequestException as e:
        return {
            "status": "ERROR",
            "message": f"API request failed: {str(e)}",
            "data": {}
        }

if __name__ == "__main__":
    result = check_gemini_batch()
    print(json.dumps(result))
    sys.exit(0)
```

**requirements.txt:**
```
requests>=2.31.0
```

---

#### Node.js Example (`index.js`)

```javascript
#!/usr/bin/env node
const https = require('https');

async function checkGeminiBatch() {
    const apiKey = process.env.GEMINI_API_KEY;
    const batchId = process.env.BATCH_ID;

    if (!apiKey || !batchId) {
        return {
            status: "ERROR",
            message: "Missing required environment variables",
            data: {}
        };
    }

    return new Promise((resolve) => {
        const options = {
            hostname: 'gemini.googleapis.com',
            path: `/v1/batches/${batchId}`,
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${apiKey}`
            }
        };

        const req = https.request(options, (res) => {
            let data = '';

            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                try {
                    const batch = JSON.parse(data);
                    const state = batch.state;

                    if (state === 'COMPLETED') {
                        resolve({
                            status: "SUCCESS",
                            data: {
                                batch_id: batchId,
                                completed_at: batch.completedAt,
                                result_count: batch.resultCount || 0
                            },
                            message: `Batch ${batchId} completed successfully`
                        });
                    } else if (['FAILED', 'CANCELLED'].includes(state)) {
                        resolve({
                            status: "FAILED",
                            data: {
                                batch_id: batchId,
                                error: batch.error?.message
                            },
                            message: `Batch ${batchId} failed`
                        });
                    } else if (['PENDING', 'RUNNING'].includes(state)) {
                        resolve({
                            status: "PENDING",
                            data: {
                                batch_id: batchId,
                                progress: batch.progress || 0
                            },
                            message: `Batch ${batchId} still processing (${batch.progress || 0}%)`
                        });
                    } else {
                        resolve({
                            status: "ERROR",
                            message: `Unknown batch state: ${state}`,
                            data: { batch_id: batchId, state }
                        });
                    }
                } catch (e) {
                    resolve({
                        status: "ERROR",
                        message: `Failed to parse response: ${e.message}`,
                        data: {}
                    });
                }
            });
        });

        req.on('error', (e) => {
            resolve({
                status: "ERROR",
                message: `API request failed: ${e.message}`,
                data: {}
            });
        });

        req.end();
    });
}

checkGeminiBatch().then(result => {
    console.log(JSON.stringify(result));
    process.exit(0);
});
```

**package.json:**
```json
{
  "name": "gemini-batch-checker",
  "version": "1.0.0",
  "main": "index.js",
  "dependencies": {}
}
```

---

## Performance and Scalability

### Target Capacity

| Metric | Target | Configuration |
|--------|--------|---------------|
| **Active Jobs** | 500+ concurrent jobs | Tested with 1000 jobs |
| **Concurrent Checks** | 50 parallel executions | Semaphore limit = 50 |
| **Poll Batch Size** | 100 jobs per iteration | Fetch 100 jobs at once |
| **DB Connection Pool** | 20 connections | SQLAlchemy pool size |
| **E2B Rate Limit** | Check with E2B docs | Implement backoff if needed |
| **Polling Loop Latency** | < 5 seconds | Fast job scheduling |

### Scaling Considerations

#### 1. Database Optimization

**Indexes:**
```sql
-- Critical indexes for performance
CREATE INDEX idx_custom_check_status ON custom_check_jobs(status);
CREATE INDEX idx_custom_check_next_check ON custom_check_jobs(next_check_at);
CREATE INDEX idx_custom_log_job_created ON custom_check_logs(job_id, created_at);
```

**Connection Pooling:**
```python
# In app/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Increased from 5
    max_overflow=40,       # Allow burst to 60 total
    pool_pre_ping=True,    # Check connection health
    pool_recycle=3600      # Recycle connections hourly
)
```

#### 2. Concurrency Management

**Semaphore Tuning:**
```python
class PollingService:
    MAX_CONCURRENT_CHECKS = 50  # Up to 50 parallel E2B sessions
    POLL_BATCH_SIZE = 100       # Process 100 jobs per iteration
```

**E2B Session Pooling (Future):**
- Consider E2B session reuse for same script (v1.1+)
- Tradeoff: Performance vs. isolation
- Requires careful state cleanup between runs

#### 3. Monitoring and Metrics

**Key Metrics to Track:**
- Active jobs count
- Polling loop iteration time
- E2B execution time (p50, p95, p99)
- Webhook success rate
- Error rate by status

**Logging:**
```python
# Add performance logging
logger.info(f"Processed {len(jobs)} jobs in {elapsed:.2f}s")
logger.info(f"E2B execution: {execution_time_ms}ms")
```

#### 4. Resource Limits

**Per-Job Limits:**
- Script size: 50MB (compressed)
- Execution timeout: 5 minutes (configurable, max 1 hour)
- Memory: E2B sandbox default (check docs)

**System Limits:**
- Total script storage: Monitor disk usage
- Log retention: Implement log rotation (future)

---

## Security

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| **Malicious Script Execution** | E2B sandbox isolation (no host access) |
| **Secret Leakage** | Encrypted storage, secret references, no logs |
| **Script Injection** | Input validation, tarfile extraction safety |
| **Webhook Abuse** | Rate limiting, HTTPS recommended |
| **Resource Exhaustion** | Timeout limits, size limits, concurrency control |

### Secret Management

**Architecture:**
```
User Input → env_vars: {"API_KEY": "secret_ref:1"}
            ↓
E2B Executor → Decrypt secret_id=1
            ↓
E2B Sandbox → Set env: {"API_KEY": "decrypted_value"}
            ↓
Script → Read from process.env / os.environ
```

**Key Principles:**
- Secrets stored encrypted in DB (existing `Secret` model with AES-256)
- `env_vars` contains references, not values
- Decryption happens in-memory at execution time
- E2B sandboxes have no persistent storage
- Secrets NEVER logged or stored in `last_check_data`

**Secret Reference Validation:**
```python
async def _resolve_env_vars(self, env_vars_json: str, db_session) -> Dict[str, str]:
    """Resolve secret references securely."""
    env_vars = json.loads(env_vars_json)
    resolved = {}

    for key, value in env_vars.items():
        if isinstance(value, str) and value.startswith("secret_ref:"):
            try:
                secret_id = int(value.split(":")[1])
                # Decrypt and inject
                resolved[key] = await secret_manager.get_decrypted_value(secret_id)
            except (ValueError, IndexError):
                raise ValueError(f"Invalid secret reference: {value}")
        else:
            resolved[key] = value

    return resolved
```

### Script Validation

**Upload Validation:**
```python
async def store_uploaded_script(self, job_id: int, file: UploadFile) -> str:
    """Validate and store uploaded script."""

    # 1. Size check
    content = await file.read()
    if len(content) > self.MAX_SCRIPT_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Script exceeds {self.MAX_SCRIPT_SIZE_MB}MB limit")

    # 2. Format check
    try:
        with tarfile.open(fileobj=BytesIO(content), mode="r:gz") as tar:
            # 3. Safe extraction check (prevent path traversal)
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    raise ValueError(f"Unsafe path in archive: {member.name}")
    except tarfile.TarError:
        raise ValueError("Invalid tar.gz file")

    # 4. Store
    script_path = self._get_script_path(job_id)
    os.makedirs(os.path.dirname(script_path), exist_ok=True)

    with open(script_path, "wb") as f:
        f.write(content)

    return script_path
```

**Git URL Validation:**
```python
def _validate_git_url(self, url: str) -> None:
    """Validate Git URL for security."""

    # Only allow HTTPS URLs
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS Git URLs allowed")

    # Block local/private IPs (basic check)
    from urllib.parse import urlparse
    parsed = urlparse(url)

    blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
    if any(blocked in parsed.netloc for blocked in blocked_hosts):
        raise ValueError("Local Git URLs not allowed")
```

### E2B Sandbox Isolation

**Security Properties:**
- **Process Isolation**: Scripts run in separate containers
- **Network Isolation**: No access to host network (configurable)
- **Filesystem Isolation**: No access to host filesystem
- **Resource Limits**: CPU, memory, timeout enforced by E2B

**Configuration:**
```python
sandbox = Sandbox(
    template="python",
    timeout=job.timeout_seconds,
    # Network access: Check E2B docs for restrictions
)
```

### Webhook Security

**Best Practices:**
- Use HTTPS webhooks (TLS encryption)
- Authenticate with custom headers (e.g., `Authorization: Bearer <token>`)
- Consider webhook signing (future enhancement)
- Rate limit webhook endpoints (on receiving side)

**Example Secure Config:**
```json
{
  "webhook_url": "https://api.example.com/teckochecker/callback",
  "webhook_method": "POST",
  "webhook_headers": {
    "Authorization": "Bearer secret_ref:5",
    "X-TeckoChecker-Signature": "computed_signature"
  }
}
```

---

## Testing Strategy

### Unit Tests

**Test Coverage:**
- `ScriptStorageService`: Upload, Git fetch, extraction, validation
- `E2BExecutor`: Sandbox creation, script execution, output parsing
- `WebhookClient`: HTTP requests, error handling
- `CustomCheckJob` model: Properties, validation
- API endpoints: CRUD operations, error cases

**Example Test:**
```python
# tests/unit/test_e2b_executor.py
import pytest
from app.services.e2b_executor import E2BExecutor

@pytest.mark.asyncio
async def test_execute_check_success(mock_sandbox, test_db):
    """Test successful script execution."""
    executor = E2BExecutor()
    job = create_test_job(script_runtime="python")

    result = await executor.execute_check(job, "/path/to/script", test_db)

    assert result["status"] == "SUCCESS"
    assert "data" in result
    assert result["execution_time_ms"] > 0
```

### Integration Tests

**Test Scenarios:**
- End-to-end: Create job → Upload script → Poll → Webhook trigger
- Git source: Fetch from public repo → Execute
- Secret injection: Verify encrypted secrets passed correctly
- Error handling: Timeout, script error, API failure
- Polling loop: Multiple jobs processed concurrently

**Example Test:**
```python
# tests/integration/test_custom_checks_e2e.py
@pytest.mark.asyncio
async def test_custom_check_e2e(client, test_db):
    """Test full custom check workflow."""

    # 1. Create job
    response = await client.post("/api/custom-checks", json={
        "name": "Test Gemini Check",
        "script_source_type": "upload",
        "script_runtime": "python",
        "script_entrypoint": "main.py",
        "check_params": {"batch_id": "test_123"},
        "webhook_url": "https://webhook.site/test",
        "poll_interval_seconds": 60
    })
    assert response.status_code == 201
    job_id = response.json()["id"]

    # 2. Upload script
    with open("tests/fixtures/test_script.tgz", "rb") as f:
        response = await client.post(
            f"/api/custom-checks/{job_id}/script/upload",
            files={"file": f}
        )
    assert response.status_code == 200

    # 3. Trigger check
    response = await client.post(f"/api/custom-checks/{job_id}/trigger")
    assert response.status_code == 200

    # 4. Wait for polling loop to process
    await asyncio.sleep(10)

    # 5. Verify logs
    response = await client.get(f"/api/custom-checks/{job_id}/logs")
    logs = response.json()["logs"]
    assert len(logs) > 0
    assert logs[0]["status"] in ["success", "pending", "error"]
```

### Load Tests

**Performance Testing:**
```python
# tests/performance/test_polling_scale.py
@pytest.mark.asyncio
async def test_polling_500_jobs(test_db):
    """Test polling service with 500 active jobs."""

    # Create 500 jobs
    jobs = [create_test_job() for _ in range(500)]
    test_db.add_all(jobs)
    test_db.commit()

    # Start polling service
    service = PollingService(lambda: test_db, max_concurrent_checks=50)

    # Run one iteration
    start = time.time()
    await service._process_jobs_concurrent(jobs[:100])  # Batch of 100
    elapsed = time.time() - start

    # Verify performance
    assert elapsed < 30  # Should process 100 jobs in < 30s
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (v1.0.0) - 2 weeks

**Deliverables:**
- ✅ Database schema (tables, migrations)
- ✅ `ScriptStorageService` (upload, Git fetch)
- ✅ `E2BExecutor` (sandbox execution, output parsing)
- ✅ `WebhookClient` (HTTP trigger)
- ✅ API endpoints (CRUD, script management)
- ✅ Basic unit tests (80% coverage)

**Success Criteria:**
- Can create custom check job via API
- Can upload script and trigger manual check
- Script executes in E2B, returns JSON output
- Webhook triggered on completion

---

### Phase 2: Polling Integration (v1.1.0) - 1 week

**Deliverables:**
- ✅ Extend `PollingService` for `CustomCheckJob`
- ✅ Unified scheduler (both job types)
- ✅ CLI commands (`custom-check` subcommand)
- ✅ Integration tests

**Success Criteria:**
- Custom checks poll automatically
- 500 active jobs supported
- 50 concurrent checks
- OpenAI polling still works (backward compatibility)

---

### Phase 3: Web UI & Polish (v1.2.0) - 1 week

**Deliverables:**
- ✅ Web UI: List custom check jobs
- ✅ Web UI: View logs and execution history
- ✅ Web UI: Manual trigger button
- ✅ Documentation (user guide, API reference)
- ✅ Performance tuning

**Success Criteria:**
- Web UI usable for basic management
- Performance validated (500 jobs, 50 concurrent)
- Documentation complete

---

## Open Questions and Future Enhancements

### Open Questions (For Discussion)

1. **E2B Pricing**: What are E2B rate limits and costs at scale (500 jobs)?
2. **Script Versioning**: Should we store script history? (DB or filesystem?)
3. **Retry Logic**: Should we implement exponential backoff for ERROR status?
4. **Webhook Retries**: Retry failed webhooks? Circuit breaker pattern?
5. **Multi-step Workflows**: Support DAGs (job dependencies)? Out of scope for v1.0?

### Future Enhancements (Post-v1.0)

**v1.3+:**
- Script marketplace (templates for common providers)
- Retry logic with exponential backoff
- Webhook retries and circuit breaker
- Prometheus metrics export
- PostgreSQL support

**v2.0+:**
- Migrate OpenAI polling to custom check (consolidate)
- Multi-step workflows (DAG support)
- Script versioning and rollback
- Advanced scheduling (cron expressions)
- Multi-region E2B execution

---

## Summary

This PRD defines a comprehensive custom check jobs feature that transforms TeckoChecker into a universal async task monitoring platform. Key highlights:

✅ **Flexibility**: Monitor any async task with user-defined scripts
✅ **Safety**: E2B sandbox isolation for untrusted code
✅ **Scale**: 500+ jobs, 50 concurrent checks
✅ **Simplicity**: Standard JSON output format
✅ **Extensibility**: Python/Node support, Git/upload sources

**Next Steps:**
1. Review and approve PRD
2. Set up E2B account and test API limits
3. Start Phase 1 implementation (core infrastructure)
4. Iterate based on feedback

---

**Document Status:** Draft for Review
**Reviewers:** 
**Approval Required:** Yes (before implementation)
