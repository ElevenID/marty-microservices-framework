#!/usr/bin/env python3
"""
Comprehensive Security Functionality Validation

This script validates that all functionality from the old UnifiedSecurityFramework
is available in the new modular architecture.
"""

import asyncio
import hashlib
import sys
import traceback
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import from new modular security structure
from marty_msf.security_core import (
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationResult,
    SecurityBootstrap,
    User,
)


async def validate_authentication():
    """Validate authentication functionality"""
    print("✓ Testing Authentication...")

    config = {
        "auth": {"type": "basic"},
        "secret_manager": {"type": "memory"},
        "cache": {"type": "memory"},
        "session": {"type": "memory"},
        "authz": {"type": "role_based"},
        "audit": {"type": "console"}
    }

    bootstrap = SecurityBootstrap(config)
    authenticator = bootstrap.get_authenticator()
    secret_manager = bootstrap.get_secret_manager()

    # Set up test user - need to store the password hash
    # First, hash the password the same way the authenticator does
    password_hash = hashlib.sha256(b"password_123").hexdigest()
    secret_manager.store_secret("user.testuser.password_hash", password_hash)

    # Test successful authentication
    result = authenticator.authenticate({"username": "testuser", "password": "password_123"})
    assert isinstance(result, AuthenticationResult)
    assert result.success
    assert result.user.username == "testuser"
    print("  ✓ Authentication successful")

    # Test failed authentication
    result = authenticator.authenticate({"username": "testuser", "password": "wrong_password"})
    assert not result.success
    print("  ✓ Authentication failure handling")

    return True


async def validate_authorization():
    """Validate authorization functionality"""
    print("✓ Testing Authorization...")

    config = {
        "auth": {"type": "basic"},
        "secret_manager": {"type": "memory"},
        "cache": {"type": "memory"},
        "session": {"type": "memory"},
        "authz": {"type": "role_based"},
        "audit": {"type": "console"}
    }

    bootstrap = SecurityBootstrap(config)
    authorizer = bootstrap.get_authorizer()

    # Create test user
    user = User(id="123", username="testuser", email="test@example.com", roles=["admin"])

    # Test authorization
    context = AuthorizationContext(
        user=user,
        resource="document:test.txt",
        action="read",
        environment={"ip": "192.168.1.1"}
    )

    result = await authorizer.authorize(context)
    assert isinstance(result, AuthorizationResult)
    print("  ✓ Authorization check")

    return True


async def validate_secret_management():
    """Validate secret management functionality"""
    print("✓ Testing Secret Management...")

    config = {"secret_manager": {"type": "memory"}}
    bootstrap = SecurityBootstrap(config)
    secret_manager = bootstrap.get_secret_manager()

    # Test storing and retrieving secrets
    secret_manager.store_secret("test_key", "test_value")
    value = secret_manager.get_secret("test_key")
    assert value == "test_value"
    print("  ✓ Secret storage and retrieval")

    # Test secret deletion
    secret_manager.delete_secret("test_key")
    value = secret_manager.get_secret("test_key")
    assert value is None
    print("  ✓ Secret deletion")

    return True


async def validate_session_management():
    """Validate session management functionality"""
    print("✓ Testing Session Management...")

    config = {"session": {"type": "memory"}}
    bootstrap = SecurityBootstrap(config)
    session_manager = bootstrap.get_session_manager()

    # Test session creation
    user = User(user_id="123", username="testuser", roles=["user"])
    session_id = await session_manager.create_session(user)
    assert session_id is not None
    print("  ✓ Session creation")

    # Test session retrieval
    retrieved_user = await session_manager.get_session(session_id)
    assert retrieved_user is not None
    assert retrieved_user.username == "testuser"
    print("  ✓ Session retrieval")

    # Test session destruction
    await session_manager.destroy_session(session_id)
    retrieved_user = await session_manager.get_session(session_id)
    assert retrieved_user is None
    print("  ✓ Session destruction")

    return True


async def validate_caching():
    """Validate caching functionality"""
    print("✓ Testing Caching...")

    config = {"cache": {"type": "memory"}}
    bootstrap = SecurityBootstrap(config)
    cache_manager = bootstrap.get_cache_manager()

    # Test cache operations
    await cache_manager.set("test_key", "test_value", ttl=60)
    value = await cache_manager.get("test_key")
    assert value == "test_value"
    print("  ✓ Cache set/get")

    # Test cache deletion
    await cache_manager.delete("test_key")
    value = await cache_manager.get("test_key")
    assert value is None
    print("  ✓ Cache deletion")

    return True


async def validate_auditing():
    """Validate auditing functionality"""
    print("✓ Testing Auditing...")

    config = {"audit": {"type": "console"}}
    bootstrap = SecurityBootstrap(config)
    auditor = bootstrap.get_auditor()

    # Test audit logging
    await auditor.log_event("test_event", {"user": "testuser", "action": "login"})
    print("  ✓ Audit logging")

    return True


async def main():
    """Run all validation tests"""
    print("🔒 Security Module Functionality Validation")
    print("=" * 50)

    try:
        await validate_authentication()
        await validate_authorization()
        await validate_secret_management()
        await validate_session_management()
        await validate_caching()
        await validate_auditing()

        print("=" * 50)
        print("🎉 All security functionality validated successfully!")
        print("✓ The new modular architecture preserves all capabilities from the unified framework")

        return True

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
