#!/usr/bin/env python3
"""
Test script to validate the security module refactoring is complete and working.
"""

import asyncio
import hashlib
import logging

from marty_msf.authentication import (
    BasicAuthenticator,
    EnvironmentSecretManager,
    IAuthenticator,
    InMemorySecretManager,
    ISecretManager,
    JwtAuthenticator,
)
from marty_msf.authorization import (
    IAuthorizer,
    PermissionAction,
    PermissionBasedAuthorizer,
    RoleBasedAuthorizer,
)

# Import from new modular security structure
from marty_msf.security_core import (
    AuthenticationMethod,
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationResult,
    User,
    create_default_security_system,
    create_development_security_system,
    create_production_security_system,
    create_testing_security_system,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_security_bootstrap():
    """Test the security bootstrap system."""
    logger.info("Testing security bootstrap system...")

    # Test default system
    auth, authz, secrets = create_default_security_system()
    assert isinstance(auth, IAuthenticator)
    assert isinstance(authz, IAuthorizer)
    assert isinstance(secrets, ISecretManager)
    logger.info("✓ Default security system works")

    # Test development system
    auth_dev, authz_dev, secrets_dev = create_development_security_system()
    assert isinstance(auth_dev, IAuthenticator)
    assert isinstance(authz_dev, IAuthorizer)
    assert isinstance(secrets_dev, ISecretManager)
    logger.info("✓ Development security system works")

    # Test testing system
    auth_test, authz_test, secrets_test = create_testing_security_system()
    assert isinstance(auth_test, IAuthenticator)
    assert isinstance(authz_test, IAuthorizer)
    assert isinstance(secrets_test, ISecretManager)
    logger.info("✓ Testing security system works")

    # Test production system
    auth_prod, authz_prod, secrets_prod = create_production_security_system()
    assert isinstance(auth_prod, IAuthenticator)
    assert isinstance(authz_prod, IAuthorizer)
    assert isinstance(secrets_prod, ISecretManager)
    logger.info("✓ Production security system works")


async def test_authentication():
    """Test authentication functionality."""
    logger.info("Testing authentication...")

    # Create secret manager with test credentials


    secrets = InMemorySecretManager()
    # Store password hash as expected by BasicAuthenticator
    password_hash = hashlib.sha256(b"test_password").hexdigest()
    secrets.store_secret("user.test_user.password_hash", password_hash)

    # Create authenticator
    auth = BasicAuthenticator(secret_manager=secrets)

    # Test successful authentication
    result = auth.authenticate({"username": "test_user", "password": "test_password"})
    assert result.success
    assert result.user.username == "test_user"
    logger.info("✓ Authentication success case works")

    # Test failed authentication
    result = auth.authenticate({"username": "test_user", "password": "wrong_password"})
    assert not result.success
    logger.info("✓ Authentication failure case works")


async def test_authorization():
    """Test authorization functionality."""
    logger.info("Testing authorization...")

    # Create role-based authorizer with test permissions
    role_permissions = {
        "admin": {"document:read", "document:write", "document:delete"},
        "user": {"document:read"}
    }
    authz = RoleBasedAuthorizer(role_permissions=role_permissions)

    # Create test user
    user = User(
        id="test_user_id",
        username="test_user",
        roles=["user"]
    )

    # Test authorization success
    context = AuthorizationContext(
        user=user,
        resource="document",
        action="read"
    )
    result = authz.authorize(context)
    assert result.allowed
    logger.info("✓ Authorization success case works")

    # Test authorization failure
    context = AuthorizationContext(
        user=user,
        resource="document",
        action="delete"
    )
    result = authz.authorize(context)
    assert not result.allowed
    logger.info("✓ Authorization failure case works")
async def test_secret_management():
    """Test secret management functionality."""
    logger.info("Testing secret management...")

    secrets = InMemorySecretManager()

    # Test storing and retrieving secrets
    secrets.store_secret("test_secret", "secret_value")
    value = secrets.get_secret("test_secret")
    assert value == "secret_value"
    logger.info("✓ Secret storage and retrieval works")

    # Test non-existent secret
    value = secrets.get_secret("non_existent")
    assert value is None
    logger.info("✓ Non-existent secret handling works")


async def main():
    """Main test runner."""
    logger.info("=== Security Module Refactoring Validation ===")

    try:
        await test_security_bootstrap()
        await test_authentication()
        await test_authorization()
        await test_secret_management()

        logger.info("=== ALL TESTS PASSED ===")
        logger.info("Security module refactoring is complete and working correctly!")
        return True

    except Exception as e:
        logger.error("Test failed: %s", e)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
