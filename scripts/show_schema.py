#!/usr/bin/env python3
"""
Display database schema information.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Secret, PollingJob, PollingLog
from sqlalchemy import inspect


def print_table_schema(model):
    """Print schema for a single table."""
    inspector = inspect(model)
    table_name = model.__tablename__

    print(f"\n{'=' * 70}")
    print(f"Table: {table_name}")
    print("=" * 70)

    # Print columns
    print("\nColumns:")
    print(f"{'Name':<30} {'Type':<20} {'Nullable':<10} {'Default'}")
    print("-" * 70)

    for column in inspector.columns:
        col_name = column.name
        col_type = str(column.type)
        nullable = "Yes" if column.nullable else "No"
        default = str(column.default) if column.default else "-"

        print(f"{col_name:<30} {col_type:<20} {nullable:<10} {default}")

    # Print relationships
    if inspector.relationships:
        print("\nRelationships:")
        for rel in inspector.relationships:
            print(f"  - {rel.key} -> {rel.mapper.class_.__name__}")

    # Print indexes
    if hasattr(model, "__table_args__"):
        table_args = model.__table_args__
        if table_args:
            print("\nIndexes:")
            for arg in table_args:
                if hasattr(arg, "name"):
                    columns = [col.name for col in arg.columns]
                    print(f"  - {arg.name}: {', '.join(columns)}")

    # Print documentation
    if model.__doc__:
        print("\nDescription:")
        doc_lines = [line.strip() for line in model.__doc__.strip().split("\n") if line.strip()]
        for line in doc_lines[:3]:  # First 3 lines only
            print(f"  {line}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("TeckoChecker Database Schema")
    print("=" * 70)

    models = [Secret, PollingJob, PollingLog]

    for model in models:
        print_table_schema(model)

    print("\n" + "=" * 70)
    print("SQL Schema (SQLite)")
    print("=" * 70)
    print(
        """
CREATE TABLE secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE polling_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    openai_secret_id INTEGER,
    keboola_secret_id INTEGER,
    keboola_stack_url TEXT NOT NULL,
    keboola_configuration_id TEXT NOT NULL,
    poll_interval_seconds INTEGER DEFAULT 120,
    status TEXT DEFAULT 'active',
    last_check_at TIMESTAMP,
    next_check_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (openai_secret_id) REFERENCES secrets(id) ON DELETE SET NULL,
    FOREIGN KEY (keboola_secret_id) REFERENCES secrets(id) ON DELETE SET NULL
);

CREATE TABLE polling_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES polling_jobs(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_secrets_name ON secrets(name);
CREATE INDEX idx_polling_jobs_batch_id ON polling_jobs(batch_id);
CREATE INDEX idx_polling_jobs_status ON polling_jobs(status);
CREATE INDEX idx_polling_jobs_next_check ON polling_jobs(next_check_at);
CREATE INDEX idx_polling_jobs_status_next_check ON polling_jobs(status, next_check_at);
CREATE INDEX idx_polling_logs_job_id ON polling_logs(job_id);
CREATE INDEX idx_polling_logs_created_at ON polling_logs(created_at);
CREATE INDEX idx_polling_logs_job_created ON polling_logs(job_id, created_at);
CREATE INDEX idx_polling_logs_status ON polling_logs(status);
"""
    )

    print("\n" + "=" * 70)
    print("Valid Values")
    print("=" * 70)
    print("\nSecret Types:")
    print("  - openai")
    print("  - keboola")

    print("\nJob Statuses:")
    print("  - active   : Job is actively being polled")
    print("  - paused   : Job is temporarily paused")
    print("  - completed: Job has completed successfully")
    print("  - failed   : Job has failed")

    print("\nLog Statuses:")
    print("  - checking : Currently checking status")
    print("  - pending  : OpenAI batch is still pending")
    print("  - completed: OpenAI batch completed")
    print("  - failed   : Check or batch failed")
    print("  - error    : Error during polling")
    print("  - triggered: Keboola job was triggered")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
