#!/usr/bin/env python3
"""
Database initialization script for TeckoChecker.
This script creates all database tables and optionally seeds test data.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, drop_db, reset_db, get_db_manager
from app.config import get_settings
from cryptography.fernet import Fernet


def print_banner():
    """Print welcome banner."""
    print("=" * 60)
    print("  TeckoChecker - Database Initialization")
    print("=" * 60)
    print()


def check_secret_key():
    """Check if SECRET_KEY is properly configured."""
    settings = get_settings()
    if not settings.secret_key or settings.secret_key == "your-secret-key-for-encryption-change-this-in-production":
        print("WARNING: SECRET_KEY is not properly configured!")
        print("Generate a new key with:")
        print("  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(1)


def initialize_database(reset: bool = False):
    """
    Initialize the database.

    Args:
        reset: If True, drop existing tables before creating new ones
    """
    print_banner()

    settings = get_settings()
    print(f"Database URL: {settings.database_url}")
    print()

    # Check secret key configuration
    check_secret_key()

    db_manager = get_db_manager()

    # Check connection
    print("Checking database connection...")
    if not db_manager.check_connection():
        print("ERROR: Cannot connect to database!")
        sys.exit(1)
    print("✓ Database connection successful")
    print()

    if reset:
        print("WARNING: This will delete all existing data!")
        response = input("Are you sure you want to reset the database? (yes/NO): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(1)

        print("Dropping existing tables...")
        drop_db()
        print("✓ Tables dropped")
        print()

    print("Creating database tables...")
    init_db()
    print("✓ Tables created successfully")
    print()

    # Display created tables
    tables = db_manager.get_table_names()
    print(f"Created {len(tables)} tables:")
    for table in tables:
        print(f"  - {table}")
    print()

    print("=" * 60)
    print("  Database initialization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Add secrets: teckochecker secret add --name <name> --type <type>")
    print("  2. Create jobs: teckochecker job create ...")
    print("  3. Start polling: teckochecker start")
    print()


def create_env_file_if_needed():
    """Create .env file from .env.example if it doesn't exist."""
    env_path = Path(__file__).parent.parent / ".env"
    env_example_path = Path(__file__).parent.parent / ".env.example"

    if not env_path.exists() and env_example_path.exists():
        print("Creating .env file from .env.example...")

        # Read .env.example
        with open(env_example_path, 'r') as f:
            content = f.read()

        # Generate a new secret key
        secret_key = Fernet.generate_key().decode()
        content = content.replace(
            "your-secret-key-for-encryption-change-this-in-production",
            secret_key
        )

        # Write to .env
        with open(env_path, 'w') as f:
            f.write(content)

        print(f"✓ Created .env file with generated SECRET_KEY")
        print()
    elif not env_path.exists():
        print("WARNING: No .env file found!")
        print("Please create one based on .env.example")
        print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Initialize TeckoChecker database"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (drop all tables and recreate)"
    )
    parser.add_argument(
        "--create-env",
        action="store_true",
        help="Create .env file from .env.example if it doesn't exist"
    )

    args = parser.parse_args()

    try:
        # Create .env file if requested
        if args.create_env:
            create_env_file_if_needed()

        # Initialize database
        initialize_database(reset=args.reset)

    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
