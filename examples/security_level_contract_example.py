"""
Example: Using the New Level Contract Security Architecture

This example demonstrates how to use the new modular security system
that follows the level contract principle.
"""

import logging

from mmf.framework.security import (  # Bootstrap for wiring components; Core interfaces; Data models; Implementations (if you want to create custom configurations)
    AuthorizationContext,
    BasicAuthenticator,
    EnvironmentSecretManager,
    IAuthenticator,
    IAuthorizer,
    ISecretManager,
    RoleBasedAuthorizer,
    User,
    create_default_security_system,
    create_development_security_system,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_basic_usage():
    """Example: Basic usage with default system."""
    logger.info("=== Basic Usage Example ===")

    # Create a default security system (uses environment variables)
    authenticator, authorizer, secret_manager = create_default_security_system()

    # Example authentication
    credentials = {"username": "alice", "password": "secret123"}
    auth_result = authenticator.authenticate(credentials)

    if auth_result.success:
        logger.info("Authentication successful for user: %s", auth_result.user.username)

        # Example authorization
        context = AuthorizationContext(
            user=auth_result.user,
            resource="data",
            action="read"
        )

        authz_result = authorizer.authorize(context)
        if authz_result.allowed:
            logger.info("Authorization granted: %s", authz_result.reason)
        else:
            logger.warning("Authorization denied: %s", authz_result.reason)
    else:
        logger.warning("Authentication failed: %s", auth_result.error_message)


def example_development_setup():
    """Example: Development setup with file-based secrets."""
    logger.info("=== Development Setup Example ===")

    # Create a development security system
    authenticator, authorizer, secret_manager = create_development_security_system()

    # Store some test secrets for development
    secret_manager.store_secret("user.alice.password_hash",
                              "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3")  # "hello"
    secret_manager.store_secret("user.alice.roles", "admin,user")

    # Test authentication
    credentials = {"username": "alice", "password": "hello"}
    auth_result = authenticator.authenticate(credentials)

    if auth_result.success:
        logger.info("Development auth successful for: %s", auth_result.user.username)
        logger.info("User roles: %s", auth_result.user.roles)


def example_custom_configuration():
    """Example: Custom configuration with specific implementations."""
    logger.info("=== Custom Configuration Example ===")

    # Create specific implementations
    secret_manager = EnvironmentSecretManager(prefix="MYAPP_")
    authenticator = BasicAuthenticator(secret_manager=secret_manager)
    authorizer = RoleBasedAuthorizer()

    logger.info("Created custom security configuration")
    logger.info("- Secret Manager: %s", type(secret_manager).__name__)
    logger.info("- Authenticator: %s", type(authenticator).__name__)
    logger.info("- Authorizer: %s", type(authorizer).__name__)


def example_interface_usage():
    """Example: Using interfaces for dependency injection."""
    logger.info("=== Interface Usage Example ===")

    def secure_service(auth: IAuthenticator, authz: IAuthorizer, secrets: ISecretManager):
        """A service that depends on security interfaces."""
        logger.info("Service received security components:")
        logger.info("- Authenticator: %s", type(auth).__name__)
        logger.info("- Authorizer: %s", type(authz).__name__)
        logger.info("- Secret Manager: %s", type(secrets).__name__)

        # The service can use any implementation that matches the interface
        # This demonstrates the power of the level contract architecture
        api_key = secrets.get_secret("api_key")
        if api_key:
            logger.info("Successfully retrieved API key from secrets")
        else:
            logger.info("No API key found in secrets")

    # Get components and inject them into the service
    auth, authz, secrets = create_default_security_system()
    secure_service(auth, authz, secrets)


def example_authorization_scenarios():
    """Example: Different authorization scenarios."""
    logger.info("=== Authorization Scenarios Example ===")

    # Create test users with different roles
    admin_user = User(
        id="admin1",
        username="admin",
        roles=["admin"]
    )

    regular_user = User(
        id="user1",
        username="john",
        roles=["user"]
    )

    viewer_user = User(
        id="viewer1",
        username="jane",
        roles=["viewer"]
    )

    # Create authorizer
    _, authorizer, _ = create_default_security_system()

    # Test different scenarios
    test_cases = [
        (admin_user, "data", "delete", "Admin should be able to delete data"),
        (regular_user, "profile", "read", "User should be able to read their profile"),
        (viewer_user, "data", "write", "Viewer should NOT be able to write data"),
        (regular_user, "admin", "access", "Regular user should NOT access admin area"),
    ]

    for user, resource, action, description in test_cases:
        context = AuthorizationContext(user=user, resource=resource, action=action)
        result = authorizer.authorize(context)

        status = "✓ ALLOWED" if result.allowed else "✗ DENIED"
        logger.info("%s - %s: %s", status, description, result.reason)


if __name__ == "__main__":
    logger.info("Security Level Contract Architecture Examples")
    logger.info("=" * 50)

    example_basic_usage()
    print()

    example_development_setup()
    print()

    example_custom_configuration()
    print()

    example_interface_usage()
    print()

    example_authorization_scenarios()

    logger.info("=" * 50)
    logger.info("Examples completed successfully!")
