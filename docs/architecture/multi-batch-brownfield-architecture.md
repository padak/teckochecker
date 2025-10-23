# TeckoChecker Multi-Batch Enhancement - Brownfield Architecture

**Document Version:** 1.0
**Last Updated:** 2025-10-23
**Status:** Ready for Implementation
**Author:** Winston (BMad Architect)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Existing Project Analysis](#existing-project-analysis)
3. [Enhancement Scope and Integration Strategy](#enhancement-scope-and-integration-strategy)
4. [Tech Stack](#tech-stack)
5. [Data Models and Schema Changes](#data-models-and-schema-changes)
6. [Component Architecture](#component-architecture)
7. [API Design and Integration](#api-design-and-integration)
8. [Source Tree](#source-tree)
9. [Infrastructure and Deployment Integration](#infrastructure-and-deployment-integration)
10. [Coding Standards](#coding-standards)
11. [Testing Strategy](#testing-strategy)
12. [Security Integration](#security-integration)
13. [Next Steps](#next-steps)
14. [Implementation Summary](#implementation-summary)

---

## Introduction

### Complexity Verification & Scope Assessment

Na základě analýzy všech agentů potvrzuji, že rozšíření **multi-batch funkcionality vyžaduje komplexní architektonické plánování**. Důvody:

**1. Rozsah změn napříč všemi vrstvami:**
- ✅ **Data Layer**: Nové databázové schéma (junction table)
- ✅ **Service Layer**: Fundamentální změna polling logiky (1 batch → N batches)
- ✅ **API Layer**: Změna schemas a validace
- ✅ **CLI Layer**: Nové parametry pro přijímání multiple IDs
- ✅ **Web UI Layer**: Form redesign a display logic

**2. Kritické business logiky změny:**
- Trigger condition: `if completed` → `if ALL batches in terminal state (completed/failed)`
- State tracking: Per-batch status vs. job-level status
- Error handling: Partial failures, retry strategy
- **Keboola metadata**: Pass completed vs. failed batch IDs as parameters

**3. Dostupné vstupy (všechny splněny):**
- ✅ Completed `docs/prd.md` (627 řádků)
- ✅ Existing technical documentation (`docs/architecture/`, `docs/SETUP.md`)
- ✅ Complete codebase access and analysis
- ✅ Paralelní agenti provedli hloubkovou analýzu všech komponent

### Enhancement Description

**Cíl**: Rozšířit TeckoChecker polling jobs o schopnost monitorovat **více OpenAI batch_ids současně** (až 10, škálovatelně) a spustit Keboola job pouze když jsou **všechny batche v terminálním stavu** (completed OR failed).

**Současný stav**: 1 job = 1 batch_id = 1 trigger
**Cílový stav**: 1 job = N batch_ids = 1 trigger (po dokončení všech)

**Klíčová business logika**:
- ✅ **Completed batch** = hotový
- ✅ **Failed batch** = hotový (terminální stav)
- ✅ **Trigger Keboola když VŠECHNY batche jsou v terminálním stavu**
- ✅ **Předat Keboola jobu metadata o completed vs. failed batches jako parameters**

### Relationship to Existing Architecture

Tento dokument **doplňuje** existující TeckoChecker architekturu v `docs/architecture/README.md`. Kde dojde ke konfliktům mezi stávajícími a novými vzory, poskytuje tento dokument guidance pro udržení konzistence při implementaci rozšíření.

---

## Existing Project Analysis

Na základě paralelní analýzy 5 agentů jsem identifikoval následující o vašem existujícím systému:

### Current Project State

**Primary Purpose**: Lightweight polling orchestration system - monitoruje OpenAI batch job completion a triggeruje Keboola Connection jobs

**Current Tech Stack**:
- Python 3.11+ (modern async features)
- FastAPI (REST API, auto-documentation)
- SQLite (SQLAlchemy 2.0 ORM, modern Mapped types)
- Typer + Rich (CLI with formatted output)
- Vanilla JavaScript (Web UI, no frameworks, ~1,550 lines)
- Fernet encryption (AES-256 for secrets)
- asyncio (background polling with semaphore concurrency control)

**Architecture Style**:
- Layered architecture (Interface → Service → Integration → Data)
- Service-oriented with clear separation of concerns
- Single-tenant, admin-only (MVP scope)

**Deployment Method**:
- Local: SQLite file + uvicorn (localhost:8000)
- Production: systemd service + optional nginx reverse proxy
- Polling starts automatically with API server (single process)

### Available Documentation

Kompletní dokumentace analyzovaná:
- `docs/prd.md` (627 lines) - kompletní PRD včetně Web UI requirements
- `docs/architecture/README.md` (514 lines) - detailní system architecture
- `docs/SETUP.md` (355 lines) - setup guide s troubleshooting
- `docs/USER_GUIDE.md` (478 lines) - complete user guide
- `CLAUDE.md` - project instructions for AI development

### Identified Constraints

**Technical Constraints:**
- SQLite single-writer limitation (readers unlimited)
- Single polling process (no horizontal scaling yet)
- In-memory scheduling (no external queue like Redis)
- No migration framework (direct `create_all()`, Alembic chybí)
- Python 3.11+ required (modern type hints)

**Design Constraints:**
- KISS principle - minimize complexity
- YAGNI principle - build only what's needed
- Single-tenant assumption (no multi-user auth)
- **No backward compatibility required** (můžeme breaking changes)

**Current Limitations:**
- `batch_id` hardcoded as String(255) single field
- Polling loop assumes 1:1 job-to-batch ratio
- No batch-level status tracking (only job-level)
- No uniqueness constraint on `batch_id` (by design)

---

## Enhancement Scope and Integration Strategy

### Enhancement Overview

**Enhancement Type**: **Core Feature Extension** (breaking change acceptable)

**Scope**:
- **Primary**: Extend `PollingJob` to monitor multiple OpenAI `batch_ids` (1→N batches)
- **Secondary**: Enhance Keboola trigger to pass batch completion metadata
- **Tertiary**: Update all interfaces (API, CLI, Web UI) to support multi-batch input/display

**Integration Impact Level**: **HIGH**

Tento enhancement ovlivňuje **všechny 4 vrstvy** architektury:
- ✅ **Data Layer**: Schema migration (new `job_batches` table)
- ✅ **Service Layer**: Polling logic rewrite (single batch → multiple batches check)
- ✅ **Integration Layer**: Keboola client - add `parameters` support
- ✅ **Interface Layer**: API schemas, CLI args, Web UI forms

**Business Impact**:
- Uživatelé mohou monitorovat až **10 batches per job** (škálovatelně více)
- **Trigger condition change**: Všechny batche musí být v terminálním stavu
- **Failed batches = OK**: Job se triggeruje i když některé batche failnou
- **Metadata passing**: Keboola dostává info o completed vs. failed batches

### Integration Approach

#### Code Integration Strategy

**Pattern**: **Additive Enhancement s Breaking Changes**

Jelikož nemusíme zachovat zpětnou kompatibilitu, zvolíme **clean break approach**:

1. **Database**: Vytvořit novou `job_batches` junction table
2. **Models**: Přidat `JobBatch` model, upravit `PollingJob` relationships
3. **Services**: Refactor `polling.py` - změnit `_process_job()` na multi-batch loop
4. **API**: Update Pydantic schemas (`batch_id: str` → `batch_ids: List[str]`)
5. **CLI**: Accept multiple `--batch-id` flags
6. **Web UI**: Textarea input pro multiple batch IDs

**Key Decision**: **Junction Table** doporučuji pro production:
- ✅ Normalizované (3NF)
- ✅ Indexovatelné per-batch queries
- ✅ Scalable pro 100+ batches
- ✅ Podporuje per-batch status tracking

#### Database Integration Approach

**Migration Strategy**: **Manual SQL Script** (no Alembic)

```python
# scripts/migrate_to_multibatch.py

def migrate():
    # Step 1: Create job_batches table
    # Step 2: Migrate existing data (single batch_id → JobBatch record)
    # Step 3: Drop old batch_id column (table recreation required for SQLite)
    # Step 4: Create indexes
```

**Schema Changes**:
- **Add**: `job_batches` table (junction table)
- **Modify**: `polling_jobs.batch_id` → remove
- **Add**: New relationship: `PollingJob.batches` → `List[JobBatch]`

#### API Integration Approach

**Schema Evolution**: **Breaking Change v1.0**

```python
# Before (v0.9.x)
class PollingJobCreate(BaseModel):
    batch_id: str  # Single batch

# After (v1.0)
class PollingJobCreate(BaseModel):
    batch_ids: List[str] = Field(min_items=1, max_items=10)
```

#### UI Integration Approach

**Web UI Changes**:
- **Form Input**: Textarea (one batch_id per line)
- **Job List**: Show batch count badge
- **Job Detail**: List all batch IDs with statuses

**CLI Changes**: Repeated flag pattern
```bash
teckochecker job create --batch-id "batch_1" --batch-id "batch_2"
```

### Compatibility Requirements

#### Breaking Change Acceptable

**No backward compatibility** - old API clients must upgrade:
- Migration script: Converts existing jobs to 1-batch-per-job in new schema
- Fresh SQLite DB: Schema recreation allowed

#### Performance Impact

**Performance Budget**:
- ✅ **API latency**: Max +50ms for job creation
- ✅ **Polling overhead**: N OpenAI API calls per job (max 10 concurrent via semaphore)
- ✅ **Database queries**: Indexed lookups, no full table scans
- ✅ **Memory**: Minimal increase (<10MB for 100 jobs × 10 batches)

---

## Tech Stack

Multi-batch enhancement **nepřidává nové technologie** - využívá plně existující TeckoChecker stack.

### Existing Technology Stack

| Category | Current Technology | Version | Usage in Enhancement |
|----------|-------------------|---------|---------------------|
| **Language** | Python | 3.11+ | Modern type hints (`Mapped`, `List[str]`) |
| **Web Framework** | FastAPI | Latest | Pydantic schemas updated for `batch_ids` array |
| **Database** | SQLite | 3.38+ | New `job_batches` junction table |
| **ORM** | SQLAlchemy | 2.0+ | `JobBatch` model, relationships |
| **Validation** | Pydantic | 2.x | `@field_validator` pro batch ID format |
| **CLI Framework** | Typer | Latest | `List[str]` type for repeated flags |
| **CLI Output** | Rich | Latest | Batch count, status tables |
| **Encryption** | Fernet | Latest | No changes (secrets unchanged) |
| **Async Runtime** | asyncio | Built-in | N batches checked per job |
| **Frontend** | Vanilla JS (ES6+) | N/A | Textarea parsing, batch display |

### New Technology Additions

**Žádné nové technologie nejsou potřeba.** ✅

Multi-batch enhancement je čistě **feature extension v rámci existujícího stacku**.

---

## Data Models and Schema Changes

### New Model: JobBatch

**Junction table** pro many-to-one relationship mezi `PollingJob` a OpenAI batch IDs.

```python
# app/models.py

class JobBatch(Base):
    """
    Model for individual batch IDs monitored by a polling job.

    Attributes:
        id: Primary key
        job_id: Foreign key to polling job
        batch_id: OpenAI batch job ID (e.g., 'batch_abc123')
        status: Current OpenAI batch status ('in_progress', 'completed', 'failed', 'cancelled', 'expired')
        created_at: When this batch was added to the job
        completed_at: When the batch reached terminal state
    """

    __tablename__ = "job_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("polling_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    batch_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="in_progress")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    job: Mapped["PollingJob"] = relationship("PollingJob", back_populates="batches")

    # Indexes
    __table_args__ = (
        Index("idx_batch_job_id", "job_id"),
        Index("idx_batch_batch_id", "batch_id"),
        Index("idx_batch_status", "status"),
        # Ensure no duplicate batch_ids within same job
        Index("idx_batch_job_batch_unique", "job_id", "batch_id", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<JobBatch(id={self.id}, job_id={self.job_id}, "
            f"batch_id='{self.batch_id}', status='{self.status}')>"
        )

    @property
    def is_terminal(self) -> bool:
        """Check if batch is in terminal state (completed, failed, cancelled, expired)."""
        return self.status in {"completed", "failed", "cancelled", "expired"}

    @property
    def is_completed(self) -> bool:
        """Check if batch completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if batch failed (any terminal state except completed)."""
        return self.status in {"failed", "cancelled", "expired"}


# Valid batch statuses from OpenAI API
BATCH_STATUSES = ["in_progress", "completed", "failed", "cancelled", "expired"]
```

### Modified Model: PollingJob

**Remove `batch_id` column**, add `batches` relationship:

```python
# app/models.py - Changes to PollingJob

class PollingJob(Base):
    """
    Model for polling jobs that monitor OpenAI batch jobs.

    NEW: Supports multiple batch_ids via JobBatch relationship
    REMOVED: batch_id column (replaced by batches relationship)
    """

    __tablename__ = "polling_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # REMOVED: batch_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # ... (all other fields remain unchanged)

    # NEW Relationship
    batches: Mapped[list["JobBatch"]] = relationship(
        "JobBatch",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobBatch.created_at",
        lazy="selectinload",  # Eager loading to avoid N+1 queries
    )

    # ... (keep existing relationships: openai_secret, keboola_secret, logs)

    # NEW: Job completion status for multi-batch
    @property
    def all_batches_terminal(self) -> bool:
        """Check if ALL batches are in terminal state."""
        if not self.batches:
            return False
        return all(batch.is_terminal for batch in self.batches)

    @property
    def completed_batches(self) -> list["JobBatch"]:
        """Get list of successfully completed batches."""
        return [b for b in self.batches if b.is_completed]

    @property
    def failed_batches(self) -> list["JobBatch"]:
        """Get list of failed batches (failed/cancelled/expired)."""
        return [b for b in self.batches if b.is_failed]

    @property
    def batch_completion_summary(self) -> dict:
        """Get summary of batch completion status."""
        return {
            "total": len(self.batches),
            "completed": len(self.completed_batches),
            "failed": len(self.failed_batches),
            "in_progress": len([b for b in self.batches if not b.is_terminal]),
        }
```

### Database Migration Strategy

**Migration Script**: `scripts/migrate_to_multibatch.py`

```python
"""
Database migration script: Single batch_id → Multi-batch junction table
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, get_db_url
from app.models import PollingJob, JobBatch, Secret, PollingLog


def migrate(dry_run: bool = False):
    """
    Migrate database from single batch_id to multi-batch schema.

    Steps:
    1. Create new job_batches table
    2. Migrate existing polling_jobs.batch_id → JobBatch records
    3. Recreate polling_jobs table without batch_id column (SQLite limitation)
    4. Create indexes
    """

    db_url = get_db_url()
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("=" * 60)
    print("TeckoChecker Multi-Batch Migration")
    print("=" * 60)
    print(f"Database: {db_url}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    print()

    try:
        # Step 1: Check current schema
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print("Step 1: Checking existing schema...")
        if "polling_jobs" not in tables:
            print("❌ ERROR: polling_jobs table not found. Is database initialized?")
            return False

        if "job_batches" in tables:
            print("⚠️  WARNING: job_batches table already exists. Migration may have run before.")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                return False

        # Step 2: Read existing jobs
        print("\nStep 2: Reading existing polling jobs...")
        result = session.execute(text("SELECT id, batch_id FROM polling_jobs"))
        existing_jobs = [(row[0], row[1]) for row in result.fetchall()]
        print(f"Found {len(existing_jobs)} existing jobs")

        if dry_run:
            print("\n[DRY RUN] Would migrate the following jobs:")
            for job_id, batch_id in existing_jobs[:5]:  # Show first 5
                print(f"  - Job {job_id}: batch_id='{batch_id}' → JobBatch record")
            if len(existing_jobs) > 5:
                print(f"  ... and {len(existing_jobs) - 5} more")
            return True

        # Step 3: Create job_batches table
        print("\nStep 3: Creating job_batches table...")
        JobBatch.__table__.create(engine, checkfirst=True)
        print("✓ job_batches table created")

        # Step 4: Migrate data
        print("\nStep 4: Migrating batch_id data to job_batches...")
        migrated_count = 0
        for job_id, batch_id in existing_jobs:
            job_batch = JobBatch(
                job_id=job_id,
                batch_id=batch_id,
                status="in_progress",  # Preserve existing behavior
                created_at=datetime.now(timezone.utc),
            )
            session.add(job_batch)
            migrated_count += 1

        session.commit()
        print(f"✓ Migrated {migrated_count} batch_id records to job_batches")

        # Step 5: Recreate polling_jobs table (SQLite can't drop columns)
        print("\nStep 5: Recreating polling_jobs table without batch_id...")

        # Backup existing data
        result = session.execute(text("""
            SELECT id, name, openai_secret_id, keboola_secret_id,
                   keboola_stack_url, keboola_component_id, keboola_configuration_id,
                   poll_interval_seconds, status, last_check_at, next_check_at,
                   created_at, completed_at
            FROM polling_jobs
        """))
        jobs_data = result.fetchall()

        # Drop and recreate
        session.execute(text("DROP TABLE polling_jobs"))
        PollingJob.__table__.create(engine)

        # Restore data
        for row in jobs_data:
            session.execute(text("""
                INSERT INTO polling_jobs
                (id, name, openai_secret_id, keboola_secret_id,
                 keboola_stack_url, keboola_component_id, keboola_configuration_id,
                 poll_interval_seconds, status, last_check_at, next_check_at,
                 created_at, completed_at)
                VALUES
                (:id, :name, :openai_secret_id, :keboola_secret_id,
                 :keboola_stack_url, :keboola_component_id, :keboola_configuration_id,
                 :poll_interval_seconds, :status, :last_check_at, :next_check_at,
                 :created_at, :completed_at)
            """), {
                "id": row[0], "name": row[1], "openai_secret_id": row[2],
                "keboola_secret_id": row[3], "keboola_stack_url": row[4],
                "keboola_component_id": row[5], "keboola_configuration_id": row[6],
                "poll_interval_seconds": row[7], "status": row[8],
                "last_check_at": row[9], "next_check_at": row[10],
                "created_at": row[11], "completed_at": row[12]
            })

        session.commit()
        print("✓ polling_jobs table recreated without batch_id column")

        # Step 6: Create indexes
        print("\nStep 6: Creating indexes...")
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_batch_job_id ON job_batches (job_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_batch_batch_id ON job_batches (batch_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_batch_status ON job_batches (status)"))
        session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_job_batch_unique ON job_batches (job_id, batch_id)"))
        session.commit()
        print("✓ Indexes created")

        # Verify
        print("\nStep 7: Verifying migration...")
        result = session.execute(text("SELECT COUNT(*) FROM job_batches"))
        batch_count = result.scalar()
        print(f"✓ job_batches table has {batch_count} records")

        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        session.rollback()
        return False

    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate TeckoChecker to multi-batch schema")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without making changes")
    args = parser.parse_args()

    success = migrate(dry_run=args.dry_run)
    sys.exit(0 if success else 1)
```

### Schema Diagram

**Before (v0.9.x)**:
```
polling_jobs
├── id (PK)
├── name
├── batch_id  <-- Single batch ID
├── openai_secret_id (FK)
├── keboola_secret_id (FK)
└── ...
```

**After (v1.0)**:
```
polling_jobs                    job_batches
├── id (PK)                     ├── id (PK)
├── name                        ├── job_id (FK) ───┐
├── openai_secret_id (FK)       ├── batch_id       │
├── keboola_secret_id (FK)      ├── status         │
└── ...                         ├── created_at     │
    └─────────────────────────────┘ completed_at   │
                                                   │
                                One-to-Many ───────┘
```

---

## Component Architecture

### 1. Service Layer: PollingService Refactor

**File**: `app/services/polling.py`

#### Current Implementation (v0.9.x)
```python
async def _process_job(self, job: PollingJob) -> None:
    """Process single batch_id polling check."""

    # Single batch status check
    status_result = await openai_client.check_batch_status(job.batch_id)

    if status_result["status"] == "completed":
        # Trigger Keboola immediately
        await self._trigger_keboola(job)
```

#### New Implementation (v1.0)
```python
async def _process_job(self, job: PollingJob) -> None:
    """
    Process multi-batch polling check.

    Logic:
    1. Loop through all job.batches
    2. For each non-terminal batch, check OpenAI status
    3. Update batch status in database
    4. If ALL batches terminal → trigger Keboola with metadata
    5. Otherwise → reschedule next check
    """

    openai_client = self._get_openai_client(job.openai_secret_id)

    # Check each batch that's not yet terminal
    batches_to_check = [b for b in job.batches if not b.is_terminal]

    if not batches_to_check:
        # All already terminal - shouldn't happen, but handle gracefully
        if job.all_batches_terminal and job.status == "active":
            await self._trigger_keboola_with_results(job)
        return

    # Process batches concurrently (respects semaphore limit)
    check_tasks = [
        self._check_single_batch(openai_client, job_batch)
        for job_batch in batches_to_check
    ]

    await asyncio.gather(*check_tasks, return_exceptions=True)

    # Refresh job from DB to get updated batch statuses
    await self.db.refresh(job)

    # Log current state
    summary = job.batch_completion_summary
    await self._log(
        job,
        "checking",
        f"Batch status: {summary['completed']} completed, "
        f"{summary['failed']} failed, {summary['in_progress']} in progress"
    )

    # Check if all batches are terminal
    if job.all_batches_terminal:
        await self._trigger_keboola_with_results(job)
        job.status = "completed_with_failures" if job.failed_batches else "completed"
        job.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
    else:
        # Reschedule next check
        job.next_check_at = datetime.now(timezone.utc) + timedelta(
            seconds=job.poll_interval_seconds
        )
        await self.db.commit()


async def _check_single_batch(
    self,
    openai_client: OpenAIBatchClient,
    job_batch: JobBatch
) -> None:
    """
    Check status of single batch and update database.
    """
    try:
        status_result = await openai_client.check_batch_status(job_batch.batch_id)
        new_status = status_result["status"]

        if new_status != job_batch.status:
            job_batch.status = new_status

            if job_batch.is_terminal:
                job_batch.completed_at = datetime.now(timezone.utc)

            await self.db.commit()

    except Exception as e:
        await self._log(
            job_batch.job,
            "error",
            f"Failed to check batch {job_batch.batch_id}: {str(e)}"
        )


async def _trigger_keboola_with_results(self, job: PollingJob) -> None:
    """
    Trigger Keboola job with batch completion metadata.

    Passes parameters:
    - batch_ids_completed: List of successfully completed batch IDs
    - batch_ids_failed: List of failed/cancelled/expired batch IDs
    - batch_count_total: Total number of batches
    - batch_count_completed: Number of completed batches
    - batch_count_failed: Number of failed batches
    """

    keboola_client = self._get_keboola_client(job.keboola_secret_id)

    # Prepare metadata
    completed_ids = [b.batch_id for b in job.completed_batches]
    failed_ids = [b.batch_id for b in job.failed_batches]

    parameters = {
        "batch_ids_completed": completed_ids,
        "batch_ids_failed": failed_ids,
        "batch_count_total": len(job.batches),
        "batch_count_completed": len(completed_ids),
        "batch_count_failed": len(failed_ids),
    }

    try:
        result = await keboola_client.trigger_job(
            component_id=job.keboola_component_id,
            config_id=job.keboola_configuration_id,
            parameters=parameters  # NEW: Pass batch metadata
        )

        await self._log(
            job,
            "triggered",
            f"Keboola job triggered with {len(completed_ids)} completed, "
            f"{len(failed_ids)} failed batches"
        )

    except Exception as e:
        await self._log(job, "error", f"Failed to trigger Keboola: {str(e)}")
        job.status = "failed"
        await self.db.commit()
```

### 2. Integration Layer: KeboolaClient Extension

**File**: `app/integrations/keboola_client.py`

```python
async def trigger_job(
    self,
    component_id: str,
    config_id: str,
    parameters: Optional[dict] = None  # NEW parameter
) -> dict:
    """
    Trigger a Keboola Storage API job.

    NEW: Accepts optional parameters dict to pass to Keboola job.

    Args:
        component_id: Keboola component ID (e.g., 'kds-team.app-custom-python')
        config_id: Configuration ID to run
        parameters: Optional dict of parameters to pass to the job (NEW)

    Returns:
        dict: Job trigger response with job_id
    """

    url = f"{self.stack_url}/v2/storage/jobs"

    payload = {
        "component": component_id,
        "config": config_id,
        "mode": "run"
    }

    # NEW: Add parameters if provided
    if parameters:
        payload["configData"] = {
            "parameters": parameters
        }

    headers = {
        "X-StorageApi-Token": self.token,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        return response.json()
```

### 3. API Layer: Schema Changes

**File**: `app/schemas.py`

```python
# Pydantic schemas for API validation

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class JobBatchSchema(BaseModel):
    """Schema for individual batch within a job."""
    id: int
    batch_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PollingJobCreate(BaseModel):
    """
    Schema for creating a new polling job.

    BREAKING CHANGE: batch_id (str) → batch_ids (List[str])
    """
    name: str = Field(..., min_length=1, max_length=255)
    batch_ids: List[str] = Field(..., min_items=1, max_items=10)  # NEW: Array
    openai_secret_id: int
    keboola_secret_id: int
    keboola_stack_url: str
    keboola_component_id: str
    keboola_configuration_id: str
    poll_interval_seconds: int = Field(default=120, ge=30, le=3600)

    @field_validator("batch_ids")
    @classmethod
    def validate_batch_ids(cls, v: List[str]) -> List[str]:
        """
        Validate batch_ids array:
        - No duplicates
        - Valid batch_id format (starts with 'batch_')
        - Character whitelist: [a-zA-Z0-9_-]
        """
        if len(v) != len(set(v)):
            raise ValueError("Duplicate batch IDs are not allowed")

        for batch_id in v:
            if not batch_id.startswith("batch_"):
                raise ValueError(f"Invalid batch ID format: '{batch_id}' (must start with 'batch_')")

            # Character whitelist
            if not all(c.isalnum() or c in {'_', '-'} for c in batch_id):
                raise ValueError(f"Batch ID '{batch_id}' contains invalid characters")

            if len(batch_id) > 255:
                raise ValueError(f"Batch ID '{batch_id}' exceeds 255 characters")

        return v


class PollingJobResponse(BaseModel):
    """Schema for polling job API responses."""
    id: int
    name: str
    batches: List[JobBatchSchema]  # NEW: Array of batches
    openai_secret_id: Optional[int]
    keboola_secret_id: Optional[int]
    keboola_stack_url: str
    keboola_component_id: str
    keboola_configuration_id: str
    poll_interval_seconds: int
    status: str
    last_check_at: Optional[datetime]
    next_check_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]

    # NEW: Computed fields
    batch_count: int = Field(default=0)
    completed_count: int = Field(default=0)
    failed_count: int = Field(default=0)

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, job: PollingJob):
        """Create response from PollingJob ORM model."""
        return cls(
            **job.__dict__,
            batches=[JobBatchSchema.from_orm(b) for b in job.batches],
            batch_count=len(job.batches),
            completed_count=len(job.completed_batches),
            failed_count=len(job.failed_batches),
        )
```

**File**: `app/api/jobs.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import PollingJobCreate, PollingJobResponse
from app.models import PollingJob, JobBatch

router = APIRouter()


@router.post("/jobs", response_model=PollingJobResponse, status_code=201)
async def create_job(job_data: PollingJobCreate, db: Session = Depends(get_db)):
    """
    Create new polling job with multiple batch IDs.

    BREAKING CHANGE: Accepts batch_ids array instead of single batch_id.
    """

    # Create job
    job = PollingJob(
        name=job_data.name,
        openai_secret_id=job_data.openai_secret_id,
        keboola_secret_id=job_data.keboola_secret_id,
        keboola_stack_url=job_data.keboola_stack_url,
        keboola_component_id=job_data.keboola_component_id,
        keboola_configuration_id=job_data.keboola_configuration_id,
        poll_interval_seconds=job_data.poll_interval_seconds,
        status="active",
        next_check_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()  # Get job.id

    # Create JobBatch records for each batch_id
    for batch_id in job_data.batch_ids:
        job_batch = JobBatch(
            job_id=job.id,
            batch_id=batch_id,
            status="in_progress",
        )
        db.add(job_batch)

    db.commit()
    db.refresh(job)

    return PollingJobResponse.from_orm(job)
```

### 4. CLI Layer: Command Updates

**File**: `app/cli/commands.py`

```python
import typer
from typing import List

# Job subcommand
job_app = typer.Typer()


@job_app.command("create")
def create_job(
    name: str = typer.Option(..., help="Job name"),
    batch_id: List[str] = typer.Option(..., "--batch-id", help="Batch ID (can be repeated)"),  # NEW: List[str]
    openai_secret: str = typer.Option(..., help="OpenAI secret name"),
    keboola_secret: str = typer.Option(..., help="Keboola secret name"),
    keboola_stack_url: str = typer.Option(..., help="Keboola stack URL"),
    keboola_component_id: str = typer.Option(..., help="Keboola component ID"),
    keboola_config_id: str = typer.Option(..., help="Keboola configuration ID"),
    poll_interval: int = typer.Option(120, help="Poll interval in seconds"),
):
    """
    Create a new polling job with multiple batch IDs.

    Example:
        teckochecker job create \\
            --name "Multi-batch job" \\
            --batch-id "batch_abc123" \\
            --batch-id "batch_def456" \\
            --batch-id "batch_ghi789" \\
            --openai-secret "openai-prod" \\
            --keboola-secret "keboola-prod" \\
            ...
    """

    # Validation
    if not batch_id:
        console.print("[red]❌ Error: At least one --batch-id is required[/red]")
        raise typer.Exit(1)

    if len(batch_id) > 10:
        console.print("[red]❌ Error: Maximum 10 batch IDs allowed[/red]")
        raise typer.Exit(1)

    if len(batch_id) != len(set(batch_id)):
        console.print("[red]❌ Error: Duplicate batch IDs detected[/red]")
        raise typer.Exit(1)

    # Call API
    response = api_client.post("/jobs", json={
        "name": name,
        "batch_ids": batch_id,  # Send as array
        # ... other fields
    })

    if response.status_code == 201:
        job = response.json()
        console.print(f"[green]✓ Job created (ID: {job['id']}, {len(batch_id)} batches)[/green]")
    else:
        console.print(f"[red]❌ Error: {response.text}[/red]")


@job_app.command("list")
def list_jobs(
    status: Optional[str] = typer.Option(None, help="Filter by status"),
):
    """List all polling jobs with batch counts."""

    response = api_client.get("/jobs", params={"status": status} if status else {})
    jobs = response.json()["jobs"]

    # Display table
    table = Table(title="Polling Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Batches", style="yellow")  # NEW column
    table.add_column("Status", style="green")
    table.add_column("Next Check", style="magenta")

    for job in jobs:
        batch_info = f"{job['completed_count']}/{job['batch_count']}"  # "3/5"
        table.add_row(
            str(job["id"]),
            job["name"],
            batch_info,  # NEW
            job["status"],
            format_time(job["next_check_at"]),
        )

    console.print(table)
```

### 5. Web UI Layer: Form and Display Updates

**File**: `app/web/static/js/app.js`

```javascript
// Job creation form
function showCreateJobModal() {
    const html = `
        <div class="modal">
            <h2>Create Polling Job</h2>
            <form id="create-job-form">
                <label>Job Name:</label>
                <input type="text" name="name" required>

                <!-- NEW: Textarea for multiple batch IDs -->
                <label>Batch IDs (one per line):</label>
                <textarea name="batch_ids" rows="5" required
                          placeholder="batch_abc123&#10;batch_def456&#10;batch_ghi789"></textarea>
                <small>Enter up to 10 batch IDs, one per line</small>

                <label>OpenAI Secret:</label>
                <select name="openai_secret_id" required>
                    <!-- populated dynamically -->
                </select>

                <!-- ... other fields ... -->

                <button type="submit">Create Job</button>
            </form>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', html);

    document.getElementById('create-job-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);

        // Parse batch_ids textarea into array
        const batchIdsText = formData.get('batch_ids');
        const batchIds = batchIdsText
            .split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0);

        // Validation
        if (batchIds.length === 0) {
            alert('At least one batch ID is required');
            return;
        }
        if (batchIds.length > 10) {
            alert('Maximum 10 batch IDs allowed');
            return;
        }

        const payload = {
            name: formData.get('name'),
            batch_ids: batchIds,  // Array
            openai_secret_id: parseInt(formData.get('openai_secret_id')),
            // ... other fields
        };

        const response = await api.createJob(payload);
        if (response.ok) {
            alert(`Job created with ${batchIds.length} batch IDs`);
            closeModal();
            refreshJobs();
        }
    });
}


// Job list display
function renderJobsList(jobs) {
    const html = jobs.map(job => `
        <div class="job-card">
            <div class="job-header">
                <span class="job-id">#${job.id}</span>
                <span class="job-name">${job.name}</span>
                <span class="job-status status-${job.status}">${job.status}</span>
            </div>

            <!-- NEW: Batch summary -->
            <div class="job-batches">
                <span class="batch-badge">
                    ${job.completed_count}/${job.batch_count} batches completed
                </span>
                ${job.failed_count > 0 ? `<span class="batch-badge failed">${job.failed_count} failed</span>` : ''}
            </div>

            <div class="job-actions">
                <button onclick="showJobDetail(${job.id})">Details</button>
                <button onclick="pauseJob(${job.id})">Pause</button>
                <button onclick="deleteJob(${job.id})">Delete</button>
            </div>
        </div>
    `).join('');

    document.getElementById('jobs-list').innerHTML = html;
}


// Job detail modal
async function showJobDetail(jobId) {
    const job = await api.getJob(jobId);

    const batchesHtml = job.batches.map(batch => `
        <tr>
            <td>${batch.batch_id}</td>
            <td class="status-${batch.status}">${batch.status}</td>
            <td>${formatDate(batch.created_at)}</td>
            <td>${batch.completed_at ? formatDate(batch.completed_at) : '-'}</td>
        </tr>
    `).join('');

    const html = `
        <div class="modal">
            <h2>Job #${job.id}: ${job.name}</h2>

            <h3>Batch Status</h3>
            <table class="batches-table">
                <thead>
                    <tr>
                        <th>Batch ID</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Completed</th>
                    </tr>
                </thead>
                <tbody>
                    ${batchesHtml}
                </tbody>
            </table>

            <h3>Summary</h3>
            <ul>
                <li>Total batches: ${job.batch_count}</li>
                <li>Completed: ${job.completed_count}</li>
                <li>Failed: ${job.failed_count}</li>
                <li>In progress: ${job.batch_count - job.completed_count - job.failed_count}</li>
            </ul>

            <button onclick="closeModal()">Close</button>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', html);
}
```

**File**: `app/web/static/css/terminal.css`

```css
/* NEW: Batch status badges */
.job-batches {
    margin: 10px 0;
    display: flex;
    gap: 10px;
}

.batch-badge {
    display: inline-block;
    padding: 4px 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--text-dim);
    border-radius: 3px;
    font-size: 0.85em;
    color: var(--text-secondary);
}

.batch-badge.failed {
    border-color: var(--error);
    color: var(--error);
}

/* Batch status table */
.batches-table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}

.batches-table th {
    text-align: left;
    padding: 10px;
    border-bottom: 1px solid var(--border);
    color: var(--accent);
}

.batches-table td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--text-dim);
}

.status-completed { color: var(--text-primary); }
.status-failed { color: var(--error); }
.status-in_progress { color: var(--warning); }
```

---

## API Design and Integration

### Breaking Changes in v1.0

**Summary**: API v1.0 introduces breaking changes to job creation and responses.

| Endpoint | Change Type | v0.9.x | v1.0 |
|----------|------------|--------|------|
| `POST /jobs` | Request body | `batch_id: str` | `batch_ids: List[str]` |
| `GET /jobs/{id}` | Response | `batch_id: str` | `batches: List[JobBatch]` |
| `GET /jobs` | Response | `batch_id: str` per job | `batches` array per job |

### Validation Rules

**Pydantic Validators** for `batch_ids`:

1. **Array constraints**:
   - `min_items=1`: At least one batch ID required
   - `max_items=10`: Maximum 10 batch IDs (configurable)

2. **Format validation**:
   - Must start with `"batch_"` prefix
   - Character whitelist: `[a-zA-Z0-9_-]`
   - Max length: 255 characters per ID

3. **Uniqueness check**:
   - No duplicate batch IDs within same job
   - Enforced at both Pydantic and database level

4. **Example validation**:
```python
# Valid
batch_ids = ["batch_abc123", "batch_def456"]  # ✓

# Invalid
batch_ids = ["abc123"]  # ❌ Missing 'batch_' prefix
batch_ids = ["batch_123", "batch_123"]  # ❌ Duplicates
batch_ids = ["batch_abc@123"]  # ❌ Invalid character '@'
```

### API Response Examples

**Create Job (POST /jobs)**:
```json
{
  "name": "Multi-batch job",
  "batch_ids": ["batch_abc123", "batch_def456", "batch_ghi789"],
  "openai_secret_id": 1,
  "keboola_secret_id": 2,
  "keboola_stack_url": "https://connection.keboola.com",
  "keboola_component_id": "kds-team.app-custom-python",
  "keboola_configuration_id": "12345",
  "poll_interval_seconds": 120
}
```

**Response** (201 Created):
```json
{
  "id": 42,
  "name": "Multi-batch job",
  "batches": [
    {
      "id": 1,
      "batch_id": "batch_abc123",
      "status": "in_progress",
      "created_at": "2025-10-23T10:00:00Z",
      "completed_at": null
    },
    {
      "id": 2,
      "batch_id": "batch_def456",
      "status": "in_progress",
      "created_at": "2025-10-23T10:00:00Z",
      "completed_at": null
    },
    {
      "id": 3,
      "batch_id": "batch_ghi789",
      "status": "in_progress",
      "created_at": "2025-10-23T10:00:00Z",
      "completed_at": null
    }
  ],
  "batch_count": 3,
  "completed_count": 0,
  "failed_count": 0,
  "status": "active",
  "created_at": "2025-10-23T10:00:00Z",
  ...
}
```

**Get Job (GET /jobs/42)** - after some batches complete:
```json
{
  "id": 42,
  "name": "Multi-batch job",
  "batches": [
    {
      "id": 1,
      "batch_id": "batch_abc123",
      "status": "completed",
      "created_at": "2025-10-23T10:00:00Z",
      "completed_at": "2025-10-23T10:05:00Z"
    },
    {
      "id": 2,
      "batch_id": "batch_def456",
      "status": "failed",
      "created_at": "2025-10-23T10:00:00Z",
      "completed_at": "2025-10-23T10:06:00Z"
    },
    {
      "id": 3,
      "batch_id": "batch_ghi789",
      "status": "in_progress",
      "created_at": "2025-10-23T10:00:00Z",
      "completed_at": null
    }
  ],
  "batch_count": 3,
  "completed_count": 1,
  "failed_count": 1,
  "status": "active",
  ...
}
```

---

## Source Tree

### Files Modified

| File Path | Lines Changed | Change Type | Description |
|-----------|--------------|-------------|-------------|
| `app/models.py` | ~80 | **BREAKING** | Add `JobBatch` model, remove `PollingJob.batch_id`, add relationships |
| `app/schemas.py` | ~60 | **BREAKING** | Change `batch_id` → `batch_ids`, add validators |
| `app/services/polling.py` | ~150 | **BREAKING** | Refactor `_process_job()` for multi-batch loop |
| `app/integrations/keboola_client.py` | ~15 | Enhancement | Add `parameters` support to `trigger_job()` |
| `app/api/jobs.py` | ~40 | **BREAKING** | Update job creation to handle `batch_ids` array |
| `app/cli/commands.py` | ~50 | **BREAKING** | Change `--batch-id` to `List[str]` type |
| `app/web/static/js/app.js` | ~100 | Enhancement | Textarea input, batch status display |
| `app/web/static/css/terminal.css` | ~30 | Enhancement | Batch badge styles, status colors |
| `app/database.py` | ~5 | Minor | Import new `JobBatch` model |
| `docs/architecture/README.md` | ~20 | Documentation | Update data flow diagrams |

**Total Estimated Changes**: ~550 lines across 10 files

### New Files

| File Path | Lines | Purpose |
|-----------|-------|---------|
| `scripts/migrate_to_multibatch.py` | ~200 | Database migration script with --dry-run support |
| `tests/unit/test_job_batch_model.py` | ~80 | Unit tests for JobBatch model |
| `tests/unit/test_multi_batch_polling.py` | ~120 | Unit tests for multi-batch polling logic |
| `tests/integration/test_multi_batch_e2e.py` | ~100 | End-to-end integration tests |
| `docs/architecture/multi-batch-brownfield-architecture.md` | ~800 | This document |

**Total New Lines**: ~1,300 lines across 5 files

### File Tree After Changes

```
teckochecker/
├── app/
│   ├── models.py                  # MODIFIED: +JobBatch, -batch_id field
│   ├── schemas.py                 # MODIFIED: batch_ids array validation
│   ├── services/
│   │   └── polling.py             # MODIFIED: Multi-batch polling loop
│   ├── integrations/
│   │   └── keboola_client.py      # MODIFIED: Parameters support
│   ├── api/
│   │   └── jobs.py                # MODIFIED: batch_ids handling
│   ├── cli/
│   │   └── commands.py            # MODIFIED: Repeated --batch-id flag
│   └── web/
│       └── static/
│           ├── js/
│           │   └── app.js         # MODIFIED: Textarea input, batch display
│           └── css/
│               └── terminal.css   # MODIFIED: Batch badge styles
│
├── scripts/
│   └── migrate_to_multibatch.py   # NEW: Migration script
│
├── tests/
│   ├── unit/
│   │   ├── test_job_batch_model.py        # NEW
│   │   └── test_multi_batch_polling.py    # NEW
│   └── integration/
│       └── test_multi_batch_e2e.py        # NEW
│
└── docs/
    └── architecture/
        └── multi-batch-brownfield-architecture.md  # NEW: This document
```

---

## Infrastructure and Deployment Integration

### Deployment Impact

**Downtime Required**: Yes (5-10 minutes for migration)

**Deployment Steps**:

1. **Pre-deployment**:
   ```bash
   # Backup database
   cp teckochecker.db teckochecker.db.backup_$(date +%Y%m%d_%H%M%S)

   # Stop API server
   systemctl stop teckochecker  # or: pkill -f "uvicorn app.main"
   ```

2. **Migration**:
   ```bash
   # Dry-run first
   python scripts/migrate_to_multibatch.py --dry-run

   # Run migration
   python scripts/migrate_to_multibatch.py
   ```

3. **Code deployment**:
   ```bash
   git pull origin feature/multi-batch
   source venv/bin/activate
   pip install -r requirements.txt  # No new dependencies
   ```

4. **Verification**:
   ```bash
   # Verify database schema
   python teckochecker.py db schema

   # Test API server
   python teckochecker.py start &
   curl http://localhost:8000/health
   ```

5. **Post-deployment**:
   ```bash
   # Monitor logs
   journalctl -u teckochecker -f

   # Test job creation
   python teckochecker.py job create --name "Test" --batch-id "batch_test123" ...
   ```

### Rollback Strategy

**If migration fails**:

```bash
# Stop server
systemctl stop teckochecker

# Restore backup
mv teckochecker.db.backup_YYYYMMDD_HHMMSS teckochecker.db

# Revert code
git checkout v0.9.1

# Restart
systemctl start teckochecker
```

**Rollback considerations**:
- ✅ Database backup created before migration
- ✅ No data loss (migration preserves existing jobs)
- ✅ Git tag on v0.9.1 for easy revert
- ❌ Cannot rollback if Keboola jobs triggered with new parameters format (forward-only)

### Environment Variables

**No new environment variables required** - all existing vars remain unchanged:

```bash
# .env (unchanged)
SECRET_KEY=...                  # Fernet encryption key
DATABASE_URL=sqlite:///teckochecker.db
POLLING_INTERVAL=120
LOG_LEVEL=INFO
```

### Performance Monitoring

**Metrics to monitor post-deployment**:

| Metric | Expected Value | Alert Threshold |
|--------|---------------|-----------------|
| Job creation latency | <100ms | >500ms |
| Polling loop duration | <10s for 10 batches | >30s |
| Database query time | <50ms | >200ms |
| Memory usage | +5-10MB | >100MB increase |
| OpenAI API error rate | <1% | >5% |

**Monitoring commands**:
```bash
# Check active jobs
python teckochecker.py job list --status active

# View recent logs
python teckochecker.py logs --tail 50

# Database size
ls -lh teckochecker.db
```

---

## Coding Standards

### SQLAlchemy 2.0 Patterns

All database code **MUST** follow modern SQLAlchemy 2.0 syntax:

```python
# ✓ CORRECT: Modern Mapped type hints
from sqlalchemy.orm import Mapped, mapped_column

class JobBatch(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(255), nullable=False)

# ✗ WRONG: Old Column syntax
from sqlalchemy import Column

class JobBatch(Base):
    id = Column(Integer, primary_key=True)  # Don't use this!
```

**Raw SQL queries**:
```python
# ✓ CORRECT: Use text() wrapper
from sqlalchemy import text

result = db.execute(text("SELECT COUNT(*) FROM job_batches WHERE status = :status"), {"status": "completed"})

# ✗ WRONG: Direct string
result = db.execute("SELECT COUNT(*) FROM job_batches")  # Will raise error!
```

### Type Hints

**100% type coverage required** for all new code:

```python
# ✓ CORRECT: Full type annotations
async def _check_single_batch(
    self,
    openai_client: OpenAIBatchClient,
    job_batch: JobBatch
) -> None:
    """Check status of single batch."""
    ...

# ✗ WRONG: Missing types
async def _check_single_batch(self, openai_client, job_batch):
    ...
```

### Error Handling

**Structured error handling pattern**:

```python
try:
    status_result = await openai_client.check_batch_status(batch_id)

except httpx.HTTPStatusError as e:
    # Log with context
    await self._log(
        job,
        "error",
        f"OpenAI API error for batch {batch_id}: {e.response.status_code}"
    )
    # Don't crash - continue with other batches

except Exception as e:
    # Catch-all for unexpected errors
    await self._log(job, "error", f"Unexpected error: {str(e)}")
    # Log to stderr for debugging
    logger.exception(f"Unexpected error in _check_single_batch: {e}")
```

### Logging Standards

**Use structured logging** with proper levels:

```python
# Job-level events
await self._log(job, "checking", "Starting multi-batch check")  # INFO
await self._log(job, "triggered", "Keboola job triggered")      # INFO
await self._log(job, "error", "Failed to connect to OpenAI")    # ERROR

# Database persistence
logger.info(f"Created JobBatch records for job_id={job.id}, count={len(batch_ids)}")
logger.warning(f"Job {job.id} has {failed_count} failed batches")
logger.error(f"Database commit failed: {str(e)}")
```

### Docstrings

**Google-style docstrings** for all public methods:

```python
async def _process_job(self, job: PollingJob) -> None:
    """
    Process multi-batch polling check.

    Loops through all job.batches, checks OpenAI status for non-terminal
    batches, and triggers Keboola when all batches reach terminal state.

    Args:
        job: PollingJob instance with batches relationship loaded

    Returns:
        None

    Side Effects:
        - Updates JobBatch.status in database
        - May trigger Keboola job via KeboolaClient
        - Creates PollingLog entries
        - Updates PollingJob.status if all batches terminal

    Raises:
        No exceptions raised - errors logged and handled gracefully
    """
    ...
```

### Code Organization

**Single Responsibility Principle**:

```python
# ✓ GOOD: Small focused methods
async def _check_single_batch(self, client, batch) -> None:
    """Check one batch only."""
    ...

async def _trigger_keboola_with_results(self, job) -> None:
    """Trigger Keboola with metadata only."""
    ...

# ✗ BAD: God method doing everything
async def _process_job_and_trigger_everything(self, job):
    # 200 lines of mixed logic...
```

---

## Testing Strategy

### Test Coverage Requirements

**Minimum coverage**: **85%** for all modified files

| File | Current Coverage | Target Coverage | Priority |
|------|-----------------|----------------|----------|
| `app/models.py` | 95% | 95% | HIGH |
| `app/services/polling.py` | 82% | 90% | **CRITICAL** |
| `app/schemas.py` | 88% | 90% | HIGH |
| `app/integrations/keboola_client.py` | 75% | 85% | MEDIUM |
| `app/api/jobs.py` | 90% | 90% | HIGH |

### Unit Tests

#### 1. Model Tests (`tests/unit/test_job_batch_model.py`)

```python
import pytest
from datetime import datetime, timezone
from app.models import JobBatch, PollingJob


def test_job_batch_creation(db_session):
    """Test JobBatch model creation."""
    job = PollingJob(name="Test Job", ...)
    db_session.add(job)
    db_session.flush()

    batch = JobBatch(
        job_id=job.id,
        batch_id="batch_test123",
        status="in_progress"
    )
    db_session.add(batch)
    db_session.commit()

    assert batch.id is not None
    assert batch.job_id == job.id
    assert not batch.is_terminal


def test_batch_is_terminal_property():
    """Test is_terminal property for all statuses."""
    test_cases = [
        ("completed", True),
        ("failed", True),
        ("cancelled", True),
        ("expired", True),
        ("in_progress", False),
    ]

    for status, expected_terminal in test_cases:
        batch = JobBatch(batch_id="test", status=status)
        assert batch.is_terminal == expected_terminal


def test_job_all_batches_terminal(db_session):
    """Test PollingJob.all_batches_terminal property."""
    job = PollingJob(name="Test", ...)
    db_session.add(job)
    db_session.flush()

    # Add 3 batches
    for i, status in enumerate(["completed", "failed", "in_progress"]):
        batch = JobBatch(job_id=job.id, batch_id=f"batch_{i}", status=status)
        db_session.add(batch)

    db_session.commit()
    db_session.refresh(job)

    assert not job.all_batches_terminal  # One still in_progress

    # Mark last batch as completed
    job.batches[2].status = "completed"
    db_session.commit()

    assert job.all_batches_terminal  # All terminal now


def test_batch_unique_constraint(db_session):
    """Test unique constraint on (job_id, batch_id)."""
    job = PollingJob(name="Test", ...)
    db_session.add(job)
    db_session.flush()

    batch1 = JobBatch(job_id=job.id, batch_id="batch_123")
    db_session.add(batch1)
    db_session.commit()

    # Try to add duplicate
    batch2 = JobBatch(job_id=job.id, batch_id="batch_123")
    db_session.add(batch2)

    with pytest.raises(IntegrityError):
        db_session.commit()
```

#### 2. Polling Service Tests (`tests/unit/test_multi_batch_polling.py`)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.polling import PollingService
from app.models import PollingJob, JobBatch


@pytest.mark.asyncio
async def test_process_job_all_batches_completed(mock_db, mock_openai_client, mock_keboola_client):
    """Test triggering Keboola when all batches completed."""
    # Setup job with 3 batches
    job = PollingJob(id=1, name="Test", status="active")
    job.batches = [
        JobBatch(id=1, batch_id="batch_1", status="completed"),
        JobBatch(id=2, batch_id="batch_2", status="completed"),
        JobBatch(id=3, batch_id="batch_3", status="completed"),
    ]

    service = PollingService(db=mock_db)
    service._get_openai_client = MagicMock(return_value=mock_openai_client)
    service._get_keboola_client = MagicMock(return_value=mock_keboola_client)

    await service._process_job(job)

    # Should trigger Keboola
    assert mock_keboola_client.trigger_job.called
    call_args = mock_keboola_client.trigger_job.call_args
    assert "parameters" in call_args.kwargs
    assert call_args.kwargs["parameters"]["batch_count_completed"] == 3

    # Job should be marked completed
    assert job.status == "completed"


@pytest.mark.asyncio
async def test_process_job_partial_completion(mock_db, mock_openai_client):
    """Test job with some batches still in progress."""
    job = PollingJob(id=1, status="active")
    job.batches = [
        JobBatch(id=1, batch_id="batch_1", status="completed"),
        JobBatch(id=2, batch_id="batch_2", status="in_progress"),
        JobBatch(id=3, batch_id="batch_3", status="in_progress"),
    ]

    # Mock OpenAI to return still pending
    mock_openai_client.check_batch_status = AsyncMock(return_value={"status": "in_progress"})

    service = PollingService(db=mock_db)
    service._get_openai_client = MagicMock(return_value=mock_openai_client)

    await service._process_job(job)

    # Should NOT trigger Keboola
    assert job.status == "active"
    assert not job.all_batches_terminal


@pytest.mark.asyncio
async def test_process_job_with_failures(mock_db, mock_openai_client, mock_keboola_client):
    """Test triggering Keboola even with failed batches."""
    job = PollingJob(id=1, status="active")
    job.batches = [
        JobBatch(id=1, batch_id="batch_1", status="completed"),
        JobBatch(id=2, batch_id="batch_2", status="failed"),
        JobBatch(id=3, batch_id="batch_3", status="expired"),
    ]

    service = PollingService(db=mock_db)
    service._get_keboola_client = MagicMock(return_value=mock_keboola_client)

    await service._process_job(job)

    # Should trigger with failure metadata
    call_args = mock_keboola_client.trigger_job.call_args
    params = call_args.kwargs["parameters"]
    assert params["batch_count_completed"] == 1
    assert params["batch_count_failed"] == 2
    assert "batch_2" in params["batch_ids_failed"]
    assert "batch_3" in params["batch_ids_failed"]

    # Job marked as completed_with_failures
    assert job.status == "completed_with_failures"
```

#### 3. Schema Validation Tests (`tests/unit/test_schemas.py`)

```python
import pytest
from pydantic import ValidationError
from app.schemas import PollingJobCreate


def test_batch_ids_validation_success():
    """Test valid batch_ids array."""
    data = {
        "name": "Test Job",
        "batch_ids": ["batch_abc123", "batch_def456"],
        # ... other required fields
    }

    schema = PollingJobCreate(**data)
    assert len(schema.batch_ids) == 2


def test_batch_ids_duplicates_rejected():
    """Test duplicate batch_ids are rejected."""
    data = {
        "name": "Test",
        "batch_ids": ["batch_123", "batch_123"],  # Duplicate
        # ...
    }

    with pytest.raises(ValidationError) as exc_info:
        PollingJobCreate(**data)

    assert "Duplicate batch IDs" in str(exc_info.value)


def test_batch_ids_invalid_format():
    """Test invalid batch ID format is rejected."""
    test_cases = [
        ["abc123"],  # Missing 'batch_' prefix
        ["batch_abc@123"],  # Invalid character '@'
        ["batch_" + "x" * 300],  # Too long (>255)
    ]

    for invalid_ids in test_cases:
        with pytest.raises(ValidationError):
            PollingJobCreate(name="Test", batch_ids=invalid_ids, ...)


def test_batch_ids_empty_array_rejected():
    """Test empty batch_ids array is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        PollingJobCreate(name="Test", batch_ids=[], ...)

    assert "min_items" in str(exc_info.value)


def test_batch_ids_max_limit():
    """Test max 10 batch_ids enforced."""
    data = {
        "name": "Test",
        "batch_ids": [f"batch_{i}" for i in range(11)],  # 11 batches
        # ...
    }

    with pytest.raises(ValidationError) as exc_info:
        PollingJobCreate(**data)

    assert "max_items" in str(exc_info.value)
```

### Integration Tests

#### End-to-End Test (`tests/integration/test_multi_batch_e2e.py`)

```python
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_multi_batch_job_lifecycle(db_session, test_secrets):
    """
    Full lifecycle test:
    1. Create job with 3 batch_ids
    2. Simulate polling with OpenAI status updates
    3. Verify Keboola trigger when all terminal
    """

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: Create job
        response = await client.post("/api/jobs", json={
            "name": "E2E Test Job",
            "batch_ids": ["batch_e2e_1", "batch_e2e_2", "batch_e2e_3"],
            "openai_secret_id": test_secrets["openai"].id,
            "keboola_secret_id": test_secrets["keboola"].id,
            "keboola_stack_url": "https://connection.keboola.com",
            "keboola_component_id": "test-component",
            "keboola_configuration_id": "12345",
            "poll_interval_seconds": 60,
        })

        assert response.status_code == 201
        job_data = response.json()
        job_id = job_data["id"]

        assert job_data["batch_count"] == 3
        assert len(job_data["batches"]) == 3

        # Step 2: Verify job detail endpoint
        response = await client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job_data = response.json()
        assert all(b["status"] == "in_progress" for b in job_data["batches"])

        # Step 3: Simulate polling cycle (mock OpenAI responses)
        # ... (simulate status updates)

        # Step 4: Verify Keboola trigger
        # ... (check polling logs)
```

### Test Execution

```bash
# Run all tests with coverage
make test

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Coverage report
make test-coverage
open htmlcov/index.html  # View detailed coverage
```

**Coverage targets**:
- Unit tests: 85%+ coverage
- Integration tests: Key user flows covered
- Total project coverage: 85%+

---

## Security Integration

### Input Validation

**Multi-layer validation strategy** for `batch_ids`:

#### 1. Pydantic Schema Layer

```python
# app/schemas.py

class PollingJobCreate(BaseModel):
    batch_ids: List[str] = Field(..., min_items=1, max_items=10)

    @field_validator("batch_ids")
    @classmethod
    def validate_batch_ids(cls, v: List[str]) -> List[str]:
        """
        Defense-in-depth validation:
        1. Format check (batch_ prefix)
        2. Character whitelist (alphanumeric + underscore/hyphen only)
        3. Length limits (max 255 chars per ID)
        4. No duplicates
        """

        if len(v) != len(set(v)):
            raise ValueError("Duplicate batch IDs are not allowed")

        for batch_id in v:
            # Format validation
            if not batch_id.startswith("batch_"):
                raise ValueError(
                    f"Invalid batch ID format: '{batch_id}' "
                    f"(must start with 'batch_')"
                )

            # Character whitelist (prevents injection attacks)
            allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
            if not all(c in allowed_chars for c in batch_id):
                raise ValueError(
                    f"Batch ID '{batch_id}' contains invalid characters. "
                    f"Only alphanumeric, underscore, and hyphen allowed."
                )

            # Length limit (prevents buffer overflow / DOS)
            if len(batch_id) > 255:
                raise ValueError(
                    f"Batch ID '{batch_id}' exceeds 255 character limit"
                )

            # Minimum length (prevent empty string after prefix)
            if len(batch_id) <= 6:  # "batch_" is 6 chars
                raise ValueError(
                    f"Batch ID '{batch_id}' too short (must have content after 'batch_')"
                )

        return v
```

**Validation error responses**:

```json
// 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "batch_ids", 0],
      "msg": "Invalid batch ID format: 'abc123' (must start with 'batch_')",
      "input": "abc123"
    }
  ]
}
```

#### 2. Database Constraints Layer

```python
# app/models.py

class JobBatch(Base):
    __tablename__ = "job_batches"

    # Database-level constraints for defense-in-depth
    __table_args__ = (
        # Prevent duplicate batch_ids within same job
        Index("idx_batch_job_batch_unique", "job_id", "batch_id", unique=True),

        # Check constraint for format (SQLite 3.38+)
        CheckConstraint(
            "batch_id LIKE 'batch_%'",
            name="check_batch_id_format"
        ),

        # Length constraint
        CheckConstraint(
            "LENGTH(batch_id) <= 255",
            name="check_batch_id_length"
        ),
    )
```

**SQL Injection Prevention**:

```python
# ✓ SAFE: SQLAlchemy ORM with parameterized queries
job_batches = db.query(JobBatch).filter(
    JobBatch.batch_id.in_(batch_ids)  # Parameterized
).all()

# ✓ SAFE: text() with bound parameters
from sqlalchemy import text

result = db.execute(
    text("SELECT * FROM job_batches WHERE batch_id = :batch_id"),
    {"batch_id": user_input}  # Bound parameter
)

# ✗ UNSAFE: String concatenation (NEVER do this!)
query = f"SELECT * FROM job_batches WHERE batch_id = '{user_input}'"  # SQL injection!
```

### Rate Limiting

**Concurrency control** already in place via semaphore:

```python
# app/services/polling.py

class PollingService:
    def __init__(self):
        # Limit concurrent OpenAI API calls
        self.semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

    async def _check_single_batch(self, client, batch):
        async with self.semaphore:  # Acquire semaphore
            # Only 10 batches checked concurrently across ALL jobs
            status = await client.check_batch_status(batch.batch_id)
```

**API rate limiting** (future enhancement):

```python
# app/api/middleware.py (not yet implemented)

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/jobs")
@limiter.limit("10/minute")  # Max 10 job creations per minute
async def create_job(...):
    ...
```

### Secrets Management

**No changes to existing Fernet encryption**:

```python
# app/services/encryption.py (unchanged)

class EncryptionService:
    """
    AES-256 encryption via Fernet (unchanged by multi-batch feature).

    - Master key from SECRET_KEY env var
    - All secrets encrypted at rest
    - No plaintext secrets in logs or responses
    """

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

**Audit logging** for security events:

```python
# Log batch_id access (for compliance)
await self._log(
    job,
    "checking",
    f"Accessing batch_ids: {[b.batch_id for b in job.batches]}"
)
```

### Security Testing

**Security-focused test cases**:

```python
# tests/unit/test_security.py

def test_batch_id_sql_injection_attempt():
    """Ensure SQL injection attempts are blocked."""
    malicious_input = "batch_123'; DROP TABLE polling_jobs; --"

    with pytest.raises(ValidationError) as exc_info:
        PollingJobCreate(
            name="Test",
            batch_ids=[malicious_input],
            ...
        )

    assert "invalid characters" in str(exc_info.value).lower()


def test_batch_id_xss_attempt():
    """Ensure XSS attempts are blocked."""
    xss_input = "batch_<script>alert('xss')</script>"

    with pytest.raises(ValidationError):
        PollingJobCreate(batch_ids=[xss_input], ...)


def test_batch_id_path_traversal():
    """Ensure path traversal attempts are blocked."""
    path_traversal = "batch_../../etc/passwd"

    with pytest.raises(ValidationError):
        PollingJobCreate(batch_ids=[path_traversal], ...)


def test_batch_id_buffer_overflow():
    """Ensure extremely long batch_ids are rejected."""
    long_id = "batch_" + "x" * 10000  # 10k chars

    with pytest.raises(ValidationError) as exc_info:
        PollingJobCreate(batch_ids=[long_id], ...)

    assert "255 character limit" in str(exc_info.value)
```

**Security checklist**:

- ✅ Input validation (Pydantic + database constraints)
- ✅ SQL injection prevention (parameterized queries only)
- ✅ XSS prevention (character whitelist)
- ✅ Path traversal prevention (whitelist)
- ✅ Buffer overflow prevention (length limits)
- ✅ Rate limiting (semaphore for API calls)
- ✅ Secrets encryption (existing Fernet)
- ✅ Audit logging (polling logs table)
- ✅ Error message sanitization (no sensitive data in responses)

---

## Next Steps

### Story Manager Handoff

**For Story Manager Agent**:

This brownfield architecture document provides the complete technical specification for implementing the multi-batch enhancement. The Story Manager should:

1. **Create implementation stories** from the following phases:

#### Phase 1: Database Layer (Story 1)
- **Effort**: 4-6 hours
- **Deliverables**:
  - `JobBatch` model in `app/models.py`
  - Database migration script `scripts/migrate_to_multibatch.py`
  - Unit tests for `JobBatch` model
- **Acceptance Criteria**:
  - Migration runs successfully (dry-run + live)
  - All existing jobs migrated to new schema
  - Database constraints enforced (unique index, check constraints)
  - Test coverage: 90%+

#### Phase 2: Service Layer (Story 2)
- **Effort**: 8-10 hours
- **Deliverables**:
  - Refactor `PollingService._process_job()` for multi-batch
  - New `_check_single_batch()` method
  - New `_trigger_keboola_with_results()` with metadata
  - Update `KeboolaClient.trigger_job()` to accept parameters
- **Acceptance Criteria**:
  - Polling loop checks all batches per job
  - Triggers Keboola only when ALL batches terminal
  - Passes batch metadata (completed/failed lists)
  - Test coverage: 85%+

#### Phase 3: API Layer (Story 3)
- **Effort**: 6-8 hours
- **Deliverables**:
  - Update Pydantic schemas (`batch_ids` array validation)
  - Modify `POST /jobs` endpoint to accept array
  - Update `GET /jobs/{id}` response to include batches
  - Update API documentation
- **Acceptance Criteria**:
  - `batch_ids` validation works (min 1, max 10, format, no duplicates)
  - API responses include batch status arrays
  - OpenAPI docs updated
  - Test coverage: 90%+

#### Phase 4: CLI Layer (Story 4)
- **Effort**: 4-5 hours
- **Deliverables**:
  - Update `job create` command to accept repeated `--batch-id` flags
  - Update `job list` to show batch counts
  - Update `job show` to display all batches
- **Acceptance Criteria**:
  - CLI accepts multiple `--batch-id` flags
  - Output shows batch summary (X/Y completed)
  - Error messages for validation failures
  - Test coverage: 80%+

#### Phase 5: Web UI Layer (Story 5)
- **Effort**: 6-8 hours
- **Deliverables**:
  - Textarea input for batch IDs (one per line)
  - Job list shows batch count badges
  - Job detail modal displays all batches with statuses
  - CSS styles for batch badges
- **Acceptance Criteria**:
  - Form parses textarea into array correctly
  - Validation feedback for invalid input
  - Job list shows "3/5 batches completed"
  - Detail view shows table of all batch statuses

#### Phase 6: Testing & Documentation (Story 6)
- **Effort**: 4-6 hours
- **Deliverables**:
  - Integration tests for end-to-end flow
  - Update user documentation
  - Update architecture docs
  - Migration guide
- **Acceptance Criteria**:
  - E2E test covers full lifecycle
  - Total test coverage: 85%+
  - All docs updated
  - Migration tested on backup DB

2. **Dependencies**:
```
Story 1 (Database)
    ↓
Story 2 (Service Layer) + Story 3 (API Layer)
    ↓
Story 4 (CLI) + Story 5 (Web UI)
    ↓
Story 6 (Testing)
```

3. **Risk Assessment**:
   - **High Risk**: Service layer refactor (core polling logic)
   - **Medium Risk**: Database migration (SQLite column drop)
   - **Low Risk**: API/CLI/Web UI (straightforward changes)

4. **Total Estimated Effort**: **30-40 hours**

### Developer Handoff

**For Developer Agent**:

When you receive this architecture document, follow these steps:

#### Pre-Implementation Checklist

1. **Read this document completely** (800+ lines)
2. **Review referenced files**:
   - `app/models.py` (current state)
   - `app/services/polling.py` (current implementation)
   - `app/schemas.py` (current schemas)
   - `app/integrations/keboola_client.py`
3. **Set up test database**: `cp teckochecker.db teckochecker.db.backup`
4. **Create feature branch**: Already created (`feature/multi-batch`)

#### Implementation Order

**Follow story order exactly**:
1. Database Layer → Service Layer → API Layer → CLI Layer → Web UI → Testing

**Do NOT**:
- Skip database migration step
- Change API before updating service layer
- Deploy without running migration dry-run first

#### Critical Implementation Notes

**SQLAlchemy 2.0**:
- Use `Mapped[Type]` type hints
- Use `mapped_column()` not `Column()`
- Wrap raw SQL in `text()`

**Polling Logic**:
- Loop through `job.batches`, skip already-terminal
- Use `asyncio.gather()` for concurrent batch checks
- Update `JobBatch.status` individually
- Check `job.all_batches_terminal` before triggering

**Keboola Parameters**:
```python
parameters = {
    "batch_ids_completed": [...],
    "batch_ids_failed": [...],
    "batch_count_total": N,
    "batch_count_completed": X,
    "batch_count_failed": Y,
}
```

**Testing**:
- Write tests BEFORE implementation (TDD recommended)
- Use mocks for OpenAI/Keboola clients
- Target 85%+ coverage

#### Files to Modify (Priority Order)

| Priority | File | Lines Changed | Complexity |
|----------|------|--------------|------------|
| 1 | `app/models.py` | ~80 | Medium |
| 2 | `scripts/migrate_to_multibatch.py` | ~200 (new) | High |
| 3 | `app/schemas.py` | ~60 | Low |
| 4 | `app/services/polling.py` | ~150 | **High** |
| 5 | `app/integrations/keboola_client.py` | ~15 | Low |
| 6 | `app/api/jobs.py` | ~40 | Medium |
| 7 | `app/cli/commands.py` | ~50 | Low |
| 8 | `app/web/static/js/app.js` | ~100 | Medium |
| 9 | `app/web/static/css/terminal.css` | ~30 | Low |
| 10 | `tests/` (multiple files) | ~300 (new) | Medium |

**Total**: ~960 lines modified + ~700 lines new = **~1,660 lines**

#### Deployment Checklist

Before deploying to production:

- [ ] All tests pass (`make test`)
- [ ] Coverage ≥85% (`make coverage-report`)
- [ ] Migration tested with `--dry-run`
- [ ] Database backup created
- [ ] Code reviewed by second developer
- [ ] API documentation updated (`/docs`)
- [ ] User guide updated
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured

#### Support Contacts

- **Architecture questions**: Reference this document (sections 1-14)
- **Business logic questions**: Review `docs/prd.md`
- **Deployment questions**: Review `docs/SETUP.md`
- **Database questions**: Reference section 5 (Data Models)
- **Testing questions**: Reference section 11 (Testing Strategy)

---

## Implementation Summary

### Executive Overview

**Feature**: Multi-Batch Polling Enhancement
**Type**: Core feature extension (breaking changes acceptable)
**Impact Level**: HIGH (all 4 architecture layers)
**Effort Estimate**: 30-40 hours
**Risk Level**: Medium (core polling logic refactor)

### What Changes

**Before** (v0.9.x):
```
1 PollingJob = 1 batch_id = 1 OpenAI status check = 1 Keboola trigger
```

**After** (v1.0):
```
1 PollingJob = N batch_ids = N OpenAI status checks = 1 Keboola trigger (when ALL terminal)
```

### Key Decisions

| Decision Point | Choice | Rationale |
|---------------|--------|-----------|
| **Data Model** | Junction table (`job_batches`) | Normalization, scalability, per-batch tracking |
| **Trigger Logic** | ALL batches terminal | User requirement: wait for complete batch set |
| **Failed Batches** | Treated as "done" (terminal) | User requirement: failures don't block trigger |
| **Metadata Passing** | Keboola `parameters` field | User requirement: distinguish completed vs failed |
| **Migration Strategy** | Manual SQL script (no Alembic) | Project constraint: no migration framework |
| **Breaking Changes** | Accepted (v0.9 → v1.0) | User requirement: no backward compatibility needed |
| **Batch Limit** | 10 batches (configurable) | Balance: usability vs OpenAI rate limits |

### Files Modified Summary

- **10 files modified** (~550 lines)
- **5 new files** (~1,300 lines)
- **Total code changes**: ~1,850 lines

**Core refactors**:
- `app/models.py`: New `JobBatch` model
- `app/services/polling.py`: Multi-batch polling loop
- `app/schemas.py`: Array validation

### Testing Requirements

- **Unit tests**: 10 new test files (~300 lines)
- **Integration tests**: E2E multi-batch flow
- **Coverage target**: 85%+ (all modified files)
- **Security tests**: Injection prevention, input validation

### Deployment Impact

- **Downtime**: 5-10 minutes (for migration)
- **Database migration**: Required (manual script)
- **Rollback**: Supported (database backup + git revert)
- **Performance**: Minimal impact (<10MB memory, <50ms latency)

### Success Criteria

**Functional**:
- ✅ Jobs can monitor 1-10 batch_ids
- ✅ Keboola triggers only when ALL batches terminal
- ✅ Failed batches don't block trigger
- ✅ Keboola receives metadata (completed vs failed lists)

**Technical**:
- ✅ Test coverage ≥85%
- ✅ Migration runs successfully on existing DB
- ✅ API latency <100ms for job creation
- ✅ No breaking changes to existing non-batch code

**Operational**:
- ✅ Documentation updated (user guide, API docs, architecture)
- ✅ Migration tested with `--dry-run`
- ✅ Rollback plan documented and tested
- ✅ Monitoring metrics defined

### Next Action

**Story Manager**: Create 6 implementation stories (see Next Steps section)
**Developer**: Begin with Story 1 (Database Layer) after story creation

---

**Document Status**: ✅ **READY FOR IMPLEMENTATION**

**Handoff**: Story Manager → create stories → Developer → implement → QA → deploy

**Questions?** Reference section numbers in this document or consult source files in `app/` directory.

