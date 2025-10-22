#!/usr/bin/env python3
"""
Verification script to test TeckoChecker setup.
Checks configuration, database connection, and models.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def check_environment():
    """Check if .env file exists and is configured."""
    print_header("Checking Environment Configuration")

    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if not env_example_path.exists():
        print("ERROR: .env.example file not found!")
        return False

    print("✓ .env.example file exists")

    if not env_path.exists():
        print("WARNING: .env file not found!")
        print("  Run: cp .env.example .env")
        print("  Then generate a SECRET_KEY with:")
        print(
            '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
        return False

    print("✓ .env file exists")

    # Try to load settings
    try:
        from app.config import get_settings

        settings = get_settings()
        print("✓ Configuration loaded successfully")
        print(f"  - Database URL: {settings.database_url}")
        print(f"  - Log Level: {settings.log_level}")
        print(f"  - API Port: {settings.api_port}")

        # Check if SECRET_KEY is properly set
        if "change-this" in settings.secret_key.lower():
            print("WARNING: SECRET_KEY is still set to default value!")
            print("  Generate a new key and update .env file")
            return False

        print("✓ SECRET_KEY is configured")
        return True

    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        return False


def check_database():
    """Check database connection and tables."""
    print_header("Checking Database")

    try:
        from app.database import get_db_manager
        from app.config import get_settings

        settings = get_settings()
        db_manager = get_db_manager()

        # Check connection
        print("Testing database connection...")
        if not db_manager.check_connection():
            print("ERROR: Cannot connect to database!")
            return False

        print("✓ Database connection successful")

        # Check if tables exist
        tables = db_manager.get_table_names()
        print(f"✓ Found {len(tables)} tables in database:")

        expected_tables = ["secrets", "polling_jobs", "polling_logs"]
        for table in expected_tables:
            if table in tables:
                print(f"  ✓ {table}")
            else:
                print(f"  ✗ {table} (missing)")

        if len(tables) == 0:
            print("\nWARNING: No tables found!")
            print("  Run: python scripts/init_db.py")
            return False

        return len(tables) >= 3

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_models():
    """Check if models are properly defined."""
    print_header("Checking Models")

    try:
        from app.models import SECRET_TYPES, JOB_STATUSES, LOG_STATUSES

        print("✓ Secret model imported")
        print("✓ PollingJob model imported")
        print("✓ PollingLog model imported")

        print(f"\nValid secret types: {', '.join(SECRET_TYPES)}")
        print(f"Valid job statuses: {', '.join(JOB_STATUSES)}")
        print(f"Valid log statuses: {', '.join(LOG_STATUSES)}")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_dependencies():
    """Check if all required packages are installed."""
    print_header("Checking Dependencies")

    required_packages = [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("cryptography", "Cryptography"),
        ("typer", "Typer"),
        ("rich", "Rich"),
        ("httpx", "HTTPX"),
        ("openai", "OpenAI"),
    ]

    all_installed = True
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✓ {name}")
        except ImportError:
            print(f"✗ {name} (not installed)")
            all_installed = False

    if not all_installed:
        print("\nInstall missing packages with:")
        print("  pip install -r requirements.txt")

    return all_installed


def test_encryption():
    """Test encryption/decryption functionality."""
    print_header("Testing Encryption")

    try:
        from cryptography.fernet import Fernet

        # Generate a test key
        key = Fernet.generate_key()
        print("✓ Generated test encryption key")

        # Test encryption
        f = Fernet(key)
        test_data = b"test secret value"
        encrypted = f.encrypt(test_data)
        print("✓ Encryption successful")

        # Test decryption
        decrypted = f.decrypt(encrypted)
        print("✓ Decryption successful")

        # Verify
        if decrypted == test_data:
            print("✓ Data integrity verified")
            return True
        else:
            print("ERROR: Decrypted data does not match!")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("  TeckoChecker Setup Verification")
    print("=" * 60)

    results = {
        "Dependencies": check_dependencies(),
        "Environment": check_environment(),
        "Encryption": test_encryption(),
        "Models": check_models(),
        "Database": check_database(),
    }

    # Summary
    print_header("Summary")

    all_passed = True
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{check:20s} {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("  All checks passed! Setup is complete.")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Start the API: python teckochecker.py start --reload")
        print("     (Note: polling service starts automatically)")
        print("  2. Add secrets: teckochecker secret add ...")
        print("  3. Create jobs: teckochecker job create ...")
        return 0
    else:
        print("  Some checks failed. Please fix the issues above.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
