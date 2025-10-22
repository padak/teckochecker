#!/usr/bin/env python3
"""
Simple test script to verify the API setup is correct.
Run this to check if all imports work and the app can be created.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from app import models
        print("✓ Models imported successfully")
    except Exception as e:
        print(f"✗ Failed to import models: {e}")
        return False
    
    try:
        from app import schemas
        print("✓ Schemas imported successfully")
    except Exception as e:
        print(f"✗ Failed to import schemas: {e}")
        return False
    
    try:
        from app import database
        print("✓ Database module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import database: {e}")
        return False
    
    try:
        from app import config
        print("✓ Config module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config: {e}")
        return False
    
    try:
        from app.services import encryption
        print("✓ Encryption service imported successfully")
    except Exception as e:
        print(f"✗ Failed to import encryption: {e}")
        return False
    
    try:
        from app.api import admin, jobs, system
        print("✓ API modules imported successfully")
    except Exception as e:
        print(f"✗ Failed to import API modules: {e}")
        return False
    
    return True


def test_app_creation():
    """Test that the FastAPI app can be created."""
    print("\nTesting app creation...")
    
    # Set required environment variables
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing-only')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///./test.db')
    
    try:
        from app.main import app
        print("✓ FastAPI app created successfully")
        print(f"  - Title: {app.title}")
        print(f"  - Version: {app.version}")
        print(f"  - Routes: {len(app.routes)} routes registered")
        return True
    except Exception as e:
        print(f"✗ Failed to create app: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schemas():
    """Test that Pydantic schemas work correctly."""
    print("\nTesting Pydantic schemas...")
    
    try:
        from app.schemas import SecretCreate, PollingJobCreate
        
        # Test SecretCreate
        secret = SecretCreate(
            name="test-secret",
            type="openai",
            value="test-value"
        )
        print("✓ SecretCreate schema works")
        
        # Test PollingJobCreate
        job = PollingJobCreate(
            name="test-job",
            batch_id="batch_123",
            openai_secret_id=1,
            keboola_secret_id=2,
            keboola_stack_url="https://connection.keboola.com",
            keboola_configuration_id="123456",
            poll_interval_seconds=120
        )
        print("✓ PollingJobCreate schema works")
        
        return True
    except Exception as e:
        print(f"✗ Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TeckoChecker API Setup Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Schemas", test_schemas()))
    results.append(("App Creation", test_app_creation()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All tests passed! The API setup is correct.")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
