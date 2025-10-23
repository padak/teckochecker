"""
Database migration script: Single batch_id → Multi-batch junction table

Migrates TeckoChecker database from v0.9.x (single batch_id) to v1.0 (multi-batch).

Usage:
    # Preview migration
    python scripts/migrate_to_multibatch.py --dry-run

    # Execute migration
    python scripts/migrate_to_multibatch.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings


def migrate(dry_run: bool = False) -> bool:
    """
    Migrate database from single batch_id to multi-batch schema.

    Steps:
    1. Create new job_batches table
    2. Migrate existing polling_jobs.batch_id → JobBatch records
    3. Recreate polling_jobs table without batch_id column (SQLite limitation)
    4. Create indexes

    Args:
        dry_run: If True, only preview changes without executing

    Returns:
        True if migration successful, False otherwise
    """
    settings = get_settings()
    db_url = settings.database_url

    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
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

        # Check if batch_id column exists
        columns = [col['name'] for col in inspector.get_columns('polling_jobs')]
        if 'batch_id' not in columns:
            print("⚠️  WARNING: batch_id column not found in polling_jobs. Schema may already be migrated.")
            print("Existing columns:", columns)
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
            print("\n[DRY RUN] No changes made to database.")
            return True

        # Step 3: Create job_batches table
        print("\nStep 3: Creating job_batches table...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS job_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                batch_id VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'in_progress',
                created_at DATETIME NOT NULL,
                completed_at DATETIME,
                FOREIGN KEY (job_id) REFERENCES polling_jobs(id) ON DELETE CASCADE
            )
        """))
        session.commit()
        print("✓ job_batches table created")

        # Step 4: Migrate data
        print("\nStep 4: Migrating batch_id data to job_batches...")
        migrated_count = 0
        for job_id, batch_id in existing_jobs:
            session.execute(text("""
                INSERT INTO job_batches (job_id, batch_id, status, created_at)
                VALUES (:job_id, :batch_id, 'in_progress', :created_at)
            """), {
                "job_id": job_id,
                "batch_id": batch_id,
                "status": "in_progress",
                "created_at": datetime.now(timezone.utc)
            })
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
        session.execute(text("""
            CREATE TABLE polling_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                openai_secret_id INTEGER,
                keboola_secret_id INTEGER,
                keboola_stack_url VARCHAR(500) NOT NULL,
                keboola_component_id VARCHAR(255) NOT NULL,
                keboola_configuration_id VARCHAR(255) NOT NULL,
                poll_interval_seconds INTEGER NOT NULL DEFAULT 120,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                last_check_at DATETIME,
                next_check_at DATETIME,
                created_at DATETIME NOT NULL,
                completed_at DATETIME,
                FOREIGN KEY (openai_secret_id) REFERENCES secrets(id) ON DELETE SET NULL,
                FOREIGN KEY (keboola_secret_id) REFERENCES secrets(id) ON DELETE SET NULL
            )
        """))

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
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_job_status_next_check ON polling_jobs (status, next_check_at)"))
        session.commit()
        print("✓ Indexes created")

        # Verify
        print("\nStep 7: Verifying migration...")
        result = session.execute(text("SELECT COUNT(*) FROM job_batches"))
        batch_count = result.scalar()
        print(f"✓ job_batches table has {batch_count} records")

        result = session.execute(text("SELECT COUNT(*) FROM polling_jobs"))
        job_count = result.scalar()
        print(f"✓ polling_jobs table has {job_count} records")

        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
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
