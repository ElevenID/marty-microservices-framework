"""
Canonical Security Functions

This module provides the canonical security functions that serve as the single source of truth
for authentication, authorization, and auditing operations across the framework.

These functions replace the deprecated consolidated security manager and use the new
modular bootstrap system.
"""

import logging
from typing import Any

from ..core.di_container import get_service, has_service, register_instance
from .api import (
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationResult,
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    User,
)
from .bootstrap import SecurityHardeningFramework, create_security_framework
from .exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


def get_security_bootstrap() -> SecurityHardeningFramework:
    """Get the security bootstrap instance from the service container."""
    # Auto-initialize if not already configured
    if not has_service(SecurityHardeningFramework):
        framework = create_security_framework("default_service", {})
        register_instance(SecurityHardeningFramework, framework)

    return get_service(SecurityHardeningFramework)


def authenticate_credentials(credentials: dict[str, Any]) -> User | None:
    """
    Canonical authentication function for use by other modules.

    This is the single source of truth for authentication logic.
    All modules should use this function instead of implementing their own.

    Args:
        credentials: Authentication credentials dictionary

    Returns:
        User if authentication succeeds, None otherwise
    """
    try:
        # Ensure security services are registered
        if not has_service(IAuthenticator):
            get_security_bootstrap()

        authenticator = get_service(IAuthenticator)
        result = authenticator.authenticate(credentials)

        if result.success and result.user:
            return result.user
        return None
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return None


def authorize_principal(user: User, resource: str, action: str) -> bool:
    """
    Canonical authorization function for use by other modules.

    This is the single source of truth for authorization logic.
    All modules should use this function instead of implementing their own.

    Args:
        user: User to authorize
        resource: Resource being accessed
        action: Action being performed

    Returns:
        True if authorized, False otherwise
    """
    try:
        # Ensure security services are registered
        if not has_service(IAuthorizer):
            get_security_bootstrap()

        authorizer = get_service(IAuthorizer)

        context = AuthorizationContext(
            user=user,
            resource=resource,
            action=action
        )

        result = authorizer.authorize(context)
        return result.allowed
    except Exception as e:
        logger.error(f"Authorization failed: {e}")
        return False


def audit_security_event(event: dict[str, Any]) -> None:
    """
    Canonical audit function for use by other modules.

    This is the single source of truth for security auditing.
    All modules should use this function instead of implementing their own.

    Args:
        event: Security event data to audit
    """
    try:
        # Ensure security services are registered
        if not has_service(IAuditor):
            get_security_bootstrap()

        auditor = get_service(IAuditor)
        event_type = event.get("event_type", "UNKNOWN")
        auditor.audit_event(event_type, event)
    except Exception as e:
        logger.error(f"Audit failed: {e}")


def configure_security_system(config: dict[str, Any]) -> SecurityHardeningFramework:
    """
    Configure the security system with the given configuration.

    Args:
        config: Security configuration dictionary

    Returns:
        Configured SecurityHardeningFramework instance
    """

    # Configure security services in DI container
    service_name = config.get("service_name", "default_service")
    framework = create_security_framework(service_name, config)
    register_instance(SecurityHardeningFramework, framework)

    # Return the framework instance
    return get_service(SecurityHardeningFramework)
