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
from .bootstrap import SecurityBootstrap
from .exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


def get_security_bootstrap() -> SecurityBootstrap:
    """Get the security bootstrap instance from the service container."""

    # Auto-initialize if not already configured
    if not has_service(SecurityBootstrap):
        bootstrap = SecurityBootstrap()
        bootstrap.initialize_security_system()
        register_instance(SecurityBootstrap, bootstrap)

    return get_service(SecurityBootstrap)


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
        bootstrap = get_security_bootstrap()
        authenticator = bootstrap.get_authenticator()

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
        bootstrap = get_security_bootstrap()
        authorizer = bootstrap.get_authorizer()

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

    This is the single source of truth for audit logging.
    All modules should use this function instead of implementing their own.

    Args:
        event: Event dictionary to audit
    """
    try:
        bootstrap = get_security_bootstrap()
        auditor = bootstrap.get_auditor()

        # Extract event type from the event dict
        event_type = event.get('event_type', 'security_event')
        auditor.audit_event(event_type, event)
    except Exception as e:
        logger.error(f"Audit failed: {e}")


def configure_security_system(config: dict[str, Any]) -> SecurityBootstrap:
    """
    Configure and return a security bootstrap instance.

    Args:
        config: Security configuration dictionary

    Returns:
        Configured SecurityBootstrap instance
    """
    bootstrap = SecurityBootstrap(config)
    bootstrap.initialize_security_system()

    # Register in service container for global access
    register_instance(SecurityBootstrap, bootstrap)

    return bootstrap

    return bootstrap
