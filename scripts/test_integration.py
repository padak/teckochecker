#!/usr/bin/env python
"""
Simple integration test for TeckoChecker
Tests the basic flow of the application
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.config import get_settings
from app.database import init_db, SessionLocal
from app.models import Secret, PollingJob
from app.services.encryption import init_encryption_service
from app.services.secrets import SecretManager

def test_basic_flow():
    """Test basic application flow"""
    print("🧪 Running TeckoChecker Integration Test...")
    print("-" * 50)

    # 1. Test configuration
    print("✓ Testing configuration...")
    settings = get_settings()
    assert settings.secret_key, "SECRET_KEY not configured"
    print(f"  Database: {settings.database_url}")
    print(f"  API Port: {settings.api_port}")
    print(f"  Log Level: {settings.log_level}")

    # 2. Test database connection
    print("\n✓ Testing database connection...")
    init_db()
    with SessionLocal() as session:
        # Test connection
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1, "Database connection failed"
        print("  Database connected successfully")

        # Count tables
        tables = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        print(f"  Found {len(tables)} tables: {[t[0] for t in tables]}")

    # 3. Test encryption service
    print("\n✓ Testing encryption service...")
    init_encryption_service(settings.secret_key)
    from app.services.encryption import get_encryption_service
    enc_service = get_encryption_service()

    test_data = "Hello, TeckoChecker!"
    encrypted = enc_service.encrypt(test_data)
    decrypted = enc_service.decrypt(encrypted)
    assert decrypted == test_data, "Encryption/decryption failed"
    print(f"  Encrypted: {encrypted[:50]}...")
    print(f"  Decrypted: {decrypted}")

    # 4. Test secret management
    print("\n✓ Testing secret management...")
    with SessionLocal() as session:
        secret_manager = SecretManager(session)

        # Create a test secret
        from app.schemas import SecretCreate
        secret_data = SecretCreate(
            name="test-openai",
            type="openai",
            value="sk-test-key-123456"
        )

        # Check if secret already exists and delete it
        existing = secret_manager.get_secret_by_name("test-openai")
        if existing:
            secret_manager.delete_secret(existing.id, force=True)
            print("  Cleaned up existing test secret")

        # Create new secret
        created_secret = secret_manager.create_secret(secret_data)
        print(f"  Created secret: ID={created_secret.id}, Name={created_secret.name}")

        # Retrieve and decrypt
        retrieved = secret_manager.get_secret_by_id(created_secret.id, decrypt=True)
        assert retrieved.value == "sk-test-key-123456", "Secret decryption failed"
        print("  Secret encryption/decryption working correctly")

        # List secrets
        secrets_response = secret_manager.list_secrets()
        # Try to get the count properly
        if hasattr(secrets_response, 'secrets'):
            secret_count = len(secrets_response.secrets)
        elif hasattr(secrets_response, 'items'):
            secret_count = len(secrets_response.items)
        else:
            secret_count = secrets_response.total if hasattr(secrets_response, 'total') else 0
        print(f"  Total secrets in database: {secret_count}")

        # Cleanup
        secret_manager.delete_secret(created_secret.id, force=True)
        print("  Test secret cleaned up")

    # 5. Test models
    print("\n✓ Testing database models...")
    with SessionLocal() as session:
        # Count records
        secret_count = session.query(Secret).count()
        job_count = session.query(PollingJob).count()
        print(f"  Secrets in DB: {secret_count}")
        print(f"  Polling jobs in DB: {job_count}")

    print("\n" + "=" * 50)
    print("✅ All integration tests passed!")
    print("=" * 50)
    print("\n📋 System Status:")
    print(f"  • Configuration: OK")
    print(f"  • Database: OK")
    print(f"  • Encryption: OK")
    print(f"  • Secret Management: OK")
    print(f"  • Models: OK")
    print("\n🚀 TeckoChecker is ready to use!")

if __name__ == "__main__":
    try:
        test_basic_flow()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)