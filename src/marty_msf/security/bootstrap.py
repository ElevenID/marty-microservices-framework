"""
Security Bootstrap Module

This module serves as the composition root for the security system.
It wires together all the security components according to the level contract architecture.

Following the Dependency Inversion Principle:
- Creates concrete implementations
- Injects dependencies through interfaces
- Provides configured security components to the application
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..core.di_container import (
    configure_service,
    get_service,
    has_service,
    register_factory,
    register_instance,
)
from .api import (
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    IComplianceScanner,
    IPolicyEngine,
    ISecretManager,
    ISessionManager,
)
from .audit_impl import create_default_auditor
from .auth_impl import BasicAuthenticator, EnvironmentAuthenticator, JwtAuthenticator
from .authz_impl import (
    AttributeBasedAuthorizer,
    PermissionBasedAuthorizer,
    RoleBasedAuthorizer,
)
from .caching import InMemoryCacheManager, SecurityCacheManager
from .secrets_impl import (
    CompositeSecretManager,
    EnvironmentSecretManager,
    FileSecretManager,
    InMemorySecretManager,
)
from .sessions import InMemorySessionManager, NoOpSessionManager

logger = logging.getLogger(__name__)


class SecurityBootstrap:
    """
    Security system bootstrap and configuration.

    This class is responsible for registering security components in the DI container
    based on configuration. It serves as the composition root for the security system.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the security bootstrap.

        Args:
            config: Configuration dictionary for security components
        """
        self.config = config or self._get_default_config()
        self._registered = False

    def register_security_services(self) -> None:
        """
        Register all security services in the DI container.
        """
        if self._registered:
            return

        # Register concrete implementations in dependency order
        self._register_secret_manager()
        self._register_authenticator()
        self._register_authorizer()
        self._register_auditor()
        self._register_cache_manager()
        self._register_session_manager()

        # Register this bootstrap instance
        register_instance(SecurityBootstrap, self)

        self._registered = True
        logger.info("Security services registered in DI container")

    def get_secret_manager(self) -> ISecretManager:
        """
        Get the secret manager from DI container.

        Returns:
            Configured secret manager instance
        """
        return get_service(ISecretManager)

    def get_authenticator(self) -> IAuthenticator:
        """
        Get the authenticator from DI container.

        Returns:
            Configured authenticator instance
        """
        return get_service(IAuthenticator)

    def get_authorizer(self) -> IAuthorizer:
        """
        Get the authorizer from DI container.

        Returns:
            Configured authorizer instance
        """
        return get_service(IAuthorizer)

    def get_auditor(self) -> IAuditor:
        """
        Get the auditor from DI container.

        Returns:
            Configured auditor instance
        """
        return get_service(IAuditor)

    def get_cache_manager(self) -> ICacheManager:
        """
        Get the cache manager from DI container.

        Returns:
            Configured cache manager instance
        """
        return get_service(ICacheManager)

    def get_session_manager(self) -> ISessionManager:
        """
        Get the session manager from DI container.

        Returns:
            Configured session manager instance
        """
        return get_service(ISessionManager)

    def initialize_security_system(self) -> dict[str, Any]:
        """
        Initialize security system by registering all components in DI container.

        Returns:
            Dictionary containing all security components from DI container
        """
        self.register_security_services()

        components = {
            "secret_manager": self.get_secret_manager(),
            "authenticator": self.get_authenticator(),
            "authorizer": self.get_authorizer(),
            "auditor": self.get_auditor(),
            "cache_manager": self.get_cache_manager(),
            "session_manager": self.get_session_manager(),
        }

        logger.info("Security system initialized with components: %s",
                   ", ".join(f"{k}: {type(v).__name__}" for k, v in components.items()))

        return components

    def initialize_core_security_system(self) -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
        """
        Initialize core security components.

        Returns:
            Tuple of (authenticator, authorizer, secret_manager) from DI container
        """
        self.register_security_services()

        secret_manager = self.get_secret_manager()
        authenticator = self.get_authenticator()
        authorizer = self.get_authorizer()

        logger.info("Core security system initialized with %s, %s, %s",
                   type(authenticator).__name__,
                   type(authorizer).__name__,
                   type(secret_manager).__name__)

        return authenticator, authorizer, secret_manager

    def _register_secret_manager(self) -> None:
        """Register the secret manager in DI container."""
        manager_type = self.config.get("secret_manager", {}).get("type", "environment")

        if manager_type == "environment":
            prefix = self.config.get("secret_manager", {}).get("prefix", "SECRET_")
            manager = EnvironmentSecretManager(prefix=prefix)

        elif manager_type == "file":
            secrets_file = self.config.get("secret_manager", {}).get("file", "secrets.json")
            manager = FileSecretManager(secrets_file=secrets_file)

        elif manager_type == "memory":
            manager = InMemorySecretManager()

        elif manager_type == "composite":
            # Create multiple managers based on configuration
            managers = []
            manager_configs = self.config.get("secret_manager", {}).get("managers", [])

            for manager_config in manager_configs:
                if manager_config.get("type") == "environment":
                    managers.append(EnvironmentSecretManager(
                        prefix=manager_config.get("prefix", "SECRET_")
                    ))
                elif manager_config.get("type") == "file":
                    managers.append(FileSecretManager(
                        secrets_file=manager_config.get("file", "secrets.json")
                    ))
                elif manager_config.get("type") == "memory":
                    managers.append(InMemorySecretManager())

            if not managers:
                # Fallback to default composite setup
                managers = [
                    EnvironmentSecretManager(),
                    FileSecretManager()
                ]

            manager = CompositeSecretManager(managers)
        else:
            logger.warning("Unknown secret manager type %s, using environment", manager_type)
            manager = EnvironmentSecretManager()

        register_instance(ISecretManager, manager)

    def _register_authenticator(self) -> None:
        """Register the authenticator in DI container."""
        auth_type = self.config.get("authenticator", {}).get("type", "basic")
        secret_manager = get_service(ISecretManager)

        if auth_type == "basic":
            authenticator = BasicAuthenticator(secret_manager=secret_manager)
        elif auth_type == "jwt":
            authenticator = JwtAuthenticator(secret_manager=secret_manager)
        elif auth_type == "environment":
            authenticator = EnvironmentAuthenticator(secret_manager=secret_manager)
        else:
            logger.warning("Unknown authenticator type %s, using basic", auth_type)
            authenticator = BasicAuthenticator(secret_manager=secret_manager)

        register_instance(IAuthenticator, authenticator)

    def _register_authorizer(self) -> None:
        """Register the authorizer in DI container."""
        authz_type = self.config.get("authorizer", {}).get("type", "role_based")

        if authz_type == "role_based":
            role_permissions = self.config.get("authorizer", {}).get("role_permissions")
            authorizer = RoleBasedAuthorizer(role_permissions=role_permissions)
        elif authz_type == "permission_based":
            authorizer = PermissionBasedAuthorizer()
        elif authz_type == "attribute_based":
            policies = self.config.get("authorizer", {}).get("policies")
            authorizer = AttributeBasedAuthorizer(policies=policies)
        else:
            logger.warning("Unknown authorizer type %s, using role_based", authz_type)
            authorizer = RoleBasedAuthorizer()

        register_instance(IAuthorizer, authorizer)

    def _register_auditor(self) -> None:
        """Register the auditor in DI container."""
        auditor = create_default_auditor(self.config)
        register_instance(IAuditor, auditor)

    def _register_cache_manager(self) -> None:
        """Register the cache manager in DI container."""
        cache_config = self.config.get("cache", {})
        cache_type = cache_config.get("type", "advanced")

        if cache_type == "advanced":
            cache_manager = SecurityCacheManager(self.config)
        elif cache_type == "memory":
            cache_manager = InMemoryCacheManager()
        else:
            logger.warning("Unknown cache type %s, using advanced", cache_type)
            cache_manager = SecurityCacheManager(self.config)

        register_instance(ICacheManager, cache_manager)

    def _register_session_manager(self) -> None:
        """Register the session manager in DI container."""
        # For now, return a placeholder. This will be implemented in a separate module.
        session_manager = InMemorySessionManager()
        register_instance(ISessionManager, session_manager)

    def _get_default_config(self) -> dict[str, Any]:
        """
        Get default security configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "secret_manager": {
                "type": os.getenv("SECURITY_SECRET_MANAGER_TYPE", "environment"),
                "prefix": os.getenv("SECURITY_SECRET_PREFIX", "SECRET_"),
                "file": os.getenv("SECURITY_SECRETS_FILE", "secrets.json")
            },
            "authenticator": {
                "type": os.getenv("SECURITY_AUTHENTICATOR_TYPE", "basic")
            },
            "authorizer": {
                "type": os.getenv("SECURITY_AUTHORIZER_TYPE", "role_based")
            }
        }


# Convenience functions for common use cases

def create_default_security_system() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Create a default security system with standard configuration.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    bootstrap = SecurityBootstrap()
    return bootstrap.initialize_core_security_system()


def create_development_security_system() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Create a security system optimized for development.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    config = {
        "secret_manager": {"type": "composite", "managers": [
            {"type": "environment"},
            {"type": "file", "file": "dev_secrets.json"},
            {"type": "memory"}
        ]},
        "authenticator": {"type": "environment"},
        "authorizer": {"type": "role_based"}
    }

    bootstrap = SecurityBootstrap(config)
    return bootstrap.initialize_core_security_system()


def create_testing_security_system() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Create a security system optimized for testing.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    config = {
        "secret_manager": {"type": "memory"},
        "authenticator": {"type": "environment"},
        "authorizer": {"type": "role_based"}
    }

    bootstrap = SecurityBootstrap(config)
    return bootstrap.initialize_core_security_system()


def create_production_security_system() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Create a security system optimized for production.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    config = {
        "secret_manager": {"type": "environment"},
        "authenticator": {"type": "jwt"},
        "authorizer": {"type": "attribute_based"}
    }

    bootstrap = SecurityBootstrap(config)
    return bootstrap.initialize_core_security_system()


def configure_security_in_container(config: dict[str, Any]) -> None:
    """
    Configure security services in the dependency injection container.

    Args:
        config: Security configuration dictionary
    """
    bootstrap = SecurityBootstrap(config)
    bootstrap.register_security_services()
    logger.info("Security services configured in DI container")


def get_security_components_from_container() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Get security components from the dependency injection container.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    if not has_service(IAuthenticator):
        # Auto-configure with defaults if not already configured
        configure_security_in_container({})

    return (
        get_service(IAuthenticator),
        get_service(IAuthorizer),
        get_service(ISecretManager)
    )


# Example usage function for demonstration
def example_usage():
    """Example of how to use the security bootstrap."""
    logger.info("=== Security Bootstrap Example ===")

    # Method 1: Create default system
    auth, authz, secrets = create_default_security_system()
    logger.info("Created default security system")

    # Method 2: Create system with custom configuration
    custom_config = {
        "secret_manager": {"type": "memory"},
        "authenticator": {"type": "environment"},
        "authorizer": {"type": "role_based"}
    }

    bootstrap = SecurityBootstrap(custom_config)
    auth2, authz2, secrets2 = bootstrap.initialize_security_system()
    logger.info("Created custom security system")

    # Method 3: Use DI container
    configure_security_in_container(custom_config)
    auth3, authz3, secrets3 = get_security_components_from_container()
    logger.info("Used DI container for security bootstrap")


if __name__ == "__main__":
    example_usage()
