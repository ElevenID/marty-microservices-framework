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

from ..core.di_container import get_service, has_service, register_instance
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

    This class is responsible for creating and wiring together all security components
    based on configuration. It serves as the composition root for the security system.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the security bootstrap.

        Args:
            config: Configuration dictionary for security components
        """
        self.config = config or self._get_default_config()

        # Core security components
        self._secret_manager: ISecretManager | None = None
        self._authenticator: IAuthenticator | None = None
        self._authorizer: IAuthorizer | None = None

        # Extended security components
        self._auditor: IAuditor | None = None
        self._cache_manager: ICacheManager | None = None
        self._session_manager: ISessionManager | None = None

        # Policy and compliance (will be implemented in separate modules)
        self._policy_engines: dict[str, IPolicyEngine] = {}
        self._compliance_scanner: IComplianceScanner | None = None

    def get_secret_manager(self) -> ISecretManager:
        """
        Get or create the configured secret manager.

        Returns:
            Configured secret manager instance
        """
        if self._secret_manager is None:
            self._secret_manager = self._create_secret_manager()
        return self._secret_manager

    def get_authenticator(self) -> IAuthenticator:
        """
        Get or create the configured authenticator.

        Returns:
            Configured authenticator instance
        """
        if self._authenticator is None:
            self._authenticator = self._create_authenticator()
        return self._authenticator

    def get_authorizer(self) -> IAuthorizer:
        """
        Get or create the configured authorizer.

        Returns:
            Configured authorizer instance
        """
        if self._authorizer is None:
            self._authorizer = self._create_authorizer()
        return self._authorizer

    def get_auditor(self) -> IAuditor:
        """
        Get or create the configured auditor.

        Returns:
            Configured auditor instance
        """
        if self._auditor is None:
            self._auditor = self._create_auditor()
        return self._auditor

    def get_cache_manager(self) -> ICacheManager:
        """
        Get or create the configured cache manager.

        Returns:
            Configured cache manager instance
        """
        if self._cache_manager is None:
            self._cache_manager = self._create_cache_manager()
        return self._cache_manager

    def get_session_manager(self) -> ISessionManager:
        """
        Get or create the configured session manager.

        Returns:
            Configured session manager instance
        """
        if self._session_manager is None:
            self._session_manager = self._create_session_manager()
        return self._session_manager

    def initialize_security_system(self) -> dict[str, Any]:
        """
        Initialize and return all security components.

        Returns:
            Dictionary containing all security components
        """
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
        Initialize and return core security components (backward compatibility).

        Returns:
            Tuple of (authenticator, authorizer, secret_manager)
        """
        secret_manager = self.get_secret_manager()
        authenticator = self.get_authenticator()
        authorizer = self.get_authorizer()

        logger.info("Core security system initialized with %s, %s, %s",
                   type(authenticator).__name__,
                   type(authorizer).__name__,
                   type(secret_manager).__name__)

        return authenticator, authorizer, secret_manager

    def _create_secret_manager(self) -> ISecretManager:
        """Create and configure the secret manager."""
        manager_type = self.config.get("secret_manager", {}).get("type", "environment")

        if manager_type == "environment":
            prefix = self.config.get("secret_manager", {}).get("prefix", "SECRET_")
            return EnvironmentSecretManager(prefix=prefix)

        elif manager_type == "file":
            secrets_file = self.config.get("secret_manager", {}).get("file", "secrets.json")
            return FileSecretManager(secrets_file=secrets_file)

        elif manager_type == "memory":
            return InMemorySecretManager()

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

            return CompositeSecretManager(managers)

        else:
            logger.warning("Unknown secret manager type %s, using environment", manager_type)
            return EnvironmentSecretManager()

    def _create_authenticator(self) -> IAuthenticator:
        """Create and configure the authenticator."""
        auth_type = self.config.get("authenticator", {}).get("type", "basic")
        secret_manager = self.get_secret_manager()

        if auth_type == "basic":
            return BasicAuthenticator(secret_manager=secret_manager)

        elif auth_type == "jwt":
            return JwtAuthenticator(secret_manager=secret_manager)

        elif auth_type == "environment":
            return EnvironmentAuthenticator(secret_manager=secret_manager)

        else:
            logger.warning("Unknown authenticator type %s, using basic", auth_type)
            return BasicAuthenticator(secret_manager=secret_manager)

    def _create_authorizer(self) -> IAuthorizer:
        """Create and configure the authorizer."""
        authz_type = self.config.get("authorizer", {}).get("type", "role_based")

        if authz_type == "role_based":
            role_permissions = self.config.get("authorizer", {}).get("role_permissions")
            return RoleBasedAuthorizer(role_permissions=role_permissions)

        elif authz_type == "permission_based":
            return PermissionBasedAuthorizer()

        elif authz_type == "attribute_based":
            policies = self.config.get("authorizer", {}).get("policies")
            return AttributeBasedAuthorizer(policies=policies)

        else:
            logger.warning("Unknown authorizer type %s, using role_based", authz_type)
            return RoleBasedAuthorizer()

    def _create_auditor(self) -> IAuditor:
        """Create and configure the auditor."""
        return create_default_auditor(self.config)

    def _create_cache_manager(self) -> ICacheManager:
        """Create and configure the cache manager."""
        cache_config = self.config.get("cache", {})
        cache_type = cache_config.get("type", "advanced")

        if cache_type == "advanced":
            return SecurityCacheManager(self.config)
        elif cache_type == "memory":
            return InMemoryCacheManager()
        else:
            logger.warning("Unknown cache type %s, using advanced", cache_type)
            return SecurityCacheManager(self.config)

    def _create_session_manager(self) -> ISessionManager:
        """Create and configure the session manager."""
        # For now, return a placeholder. This will be implemented in a separate module.
        return InMemorySessionManager()

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
    return bootstrap.initialize_security_system()


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
    return bootstrap.initialize_security_system()


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
    return bootstrap.initialize_security_system()


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
    return bootstrap.initialize_security_system()


def configure_security_in_container(config: dict[str, Any]) -> None:
    """
    Configure security bootstrap in the dependency injection container.

    Args:
        config: Security configuration dictionary
    """
    bootstrap = SecurityBootstrap(config)
    register_instance(SecurityBootstrap, bootstrap)
    logger.info("Security bootstrap registered in DI container")


def get_security_components_from_container() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Get security components from the dependency injection container.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    if not has_service(SecurityBootstrap):
        # Auto-configure with defaults if not already configured
        configure_security_in_container({})

    bootstrap = get_service(SecurityBootstrap)
    components = bootstrap.initialize_security_system()

    # Extract the core components from the full component dict
    return (
        components["authenticator"],
        components["authorizer"],
        components["secret_manager"]
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
