"""
New Security Context and Decorators

This module provides security decorators and context management that use the new
modular bootstrap system instead of the deprecated consolidated manager.
"""

import functools
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from ..core.di_container import get_service, has_service, register_instance
from ..security_core.api import User
from ..security_core.canonical import (
    authenticate_credentials,
    authorize_principal,
    get_security_bootstrap,
)
from ..security_core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    PermissionDeniedError,
    RoleRequiredError,
    handle_security_exception,
)

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])


class SecurityContext:
    """Enhanced security context for decorated functions."""

    def __init__(
        self,
        user: User,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ):
        self.user = user
        self.session_id = session_id
        self.correlation_id = correlation_id
        self.authenticated_at = datetime.now(timezone.utc)

    @property
    def principal_id(self) -> str:
        """Get principal ID from user."""
        return self.user.id

    @property
    def principal(self) -> dict[str, Any]:
        """Get principal data as dict."""
        return {
            "id": self.user.id,
            "username": self.user.username,
            "roles": self.user.roles,
            "attributes": self.user.attributes,
            "metadata": self.user.metadata,
            "email": self.user.email,
        }

    @property
    def roles(self) -> set[str]:
        """Get user roles as set."""
        return set(self.user.roles)

    @property
    def permissions(self) -> set[str]:
        """Get user permissions from bootstrap."""
        try:
            bootstrap = get_security_bootstrap()
            authorizer = bootstrap.get_authorizer()
            return authorizer.get_user_permissions(self.user)
        except Exception as e:
            logger.error("Failed to get permissions: %s", e)
            return set()

    @property
    def token_claims(self) -> dict[str, Any]:
        """Get token claims from user metadata."""
        return self.user.metadata.get('token_claims', {})

    def has_role(self, role: str) -> bool:
        """Check if context has role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if context has permission."""
        return permission in self.permissions


# User context service for dependency injection


class CurrentUserService:
    """Thread-safe service to manage current user context without global variables."""

    def __init__(self):
        self._lock = threading.RLock()
        self._current_user: User | None = None

    def get_user(self) -> User | None:
        """Get the current authenticated user."""
        with self._lock:
            return self._current_user

    def set_user(self, user: User | None) -> None:
        """Set the current authenticated user."""
        with self._lock:
            self._current_user = user


def _get_user_service() -> CurrentUserService:
    """Get or create the current user service from DI container."""
    if not has_service(CurrentUserService):
        service = CurrentUserService()
        register_instance(CurrentUserService, service)
    return get_service(CurrentUserService)


def get_current_user() -> User | None:
    """Get the current authenticated user."""
    return _get_user_service().get_user()


def _set_current_user(user: User | None) -> None:
    """Set the current authenticated user (internal use)."""
    _get_user_service().set_user(user)


def requires_auth(func: F) -> F:
    """
    Decorator that requires authentication.

    Args:
        func: Function to decorate

    Returns:
        Decorated function that checks authentication
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Try to get credentials from request if available
            credentials = {}

            # Look for request object in args
            request = None
            for arg in args:
                if hasattr(arg, 'headers'):  # Likely a request object
                    request = arg
                    break

            if request and hasattr(request, 'headers'):
                auth_header = request.headers.get('authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    credentials['token'] = auth_header[7:]
                elif request.headers.get('x-api-key'):
                    credentials['api_key'] = request.headers.get('x-api-key')

            # If no credentials found, check if user is already authenticated
            current_user = get_current_user()
            if not current_user and not credentials:
                raise AuthenticationError("Authentication required")

            # Authenticate if we have credentials
            if credentials and not current_user:
                current_user = authenticate_credentials(credentials)
                if not current_user:
                    raise AuthenticationError("Invalid credentials")
                _set_current_user(current_user)

            return func(*args, **kwargs)

        except Exception as e:
            return handle_security_exception(e)

    return wrapper


def requires_role(role: str) -> Callable[[F], F]:
    """
    Decorator that requires a specific role.

    Args:
        role: Required role name

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                if role not in current_user.roles:
                    raise RoleRequiredError(f"Role '{role}' required", required_role=role)

                return func(*args, **kwargs)

            except Exception as e:
                return handle_security_exception(e)

        return wrapper
    return decorator


def requires_permission(permission: str) -> Callable[[F], F]:
    """
    Decorator that requires a specific permission.

    Args:
        permission: Required permission

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                bootstrap = get_security_bootstrap()
                authorizer = bootstrap.get_authorizer()
                permissions = authorizer.get_user_permissions(current_user)

                if permission not in permissions:
                    raise PermissionDeniedError(f"Permission '{permission}' required", permission=permission)

                return func(*args, **kwargs)

            except Exception as e:
                return handle_security_exception(e)

        return wrapper
    return decorator


def requires_any_role(*roles: str) -> Callable[[F], F]:
    """
    Decorator that requires any of the specified roles.

    Args:
        roles: Required role names (any one of them)

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                user_roles = set(current_user.roles)
                required_roles = set(roles)

                if not user_roles.intersection(required_roles):
                    raise RoleRequiredError(f"One of roles {roles} required", required_role=str(roles))

                return func(*args, **kwargs)

            except Exception as e:
                return handle_security_exception(e)

        return wrapper
    return decorator


def requires_rbac(resource: str, action: str) -> Callable[[F], F]:
    """
    Decorator that requires RBAC authorization.

    Args:
        resource: Resource being accessed
        action: Action being performed

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                if not authorize_principal(current_user, resource, action):
                    raise AuthorizationError(f"Access denied to {resource}:{action}")

                return func(*args, **kwargs)

            except Exception as e:
                return handle_security_exception(e)

        return wrapper
    return decorator


def requires_abac(
    resource: str,
    action: str
) -> Callable[[F], F]:
    """
    Decorator that requires ABAC authorization.

    Args:
        resource: Resource being accessed
        action: Action being performed
        attributes: Additional attributes for authorization

    Returns:
        Decorator function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                # For now, use the same authorization as RBAC
                # In the future, this could use more complex attribute-based logic
                if not authorize_principal(current_user, resource, action):
                    raise AuthorizationError(f"Access denied to {resource}:{action}")

                return func(*args, **kwargs)

            except Exception as e:
                return handle_security_exception(e)

        return wrapper
    return decorator


def verify_jwt_token(token: str) -> User | None:
    """
    Verify a JWT token and return the user.

    Args:
        token: JWT token to verify

    Returns:
        User if token is valid, None otherwise
    """
    try:
        credentials = {'token': token}
        return authenticate_credentials(credentials)
    except Exception as e:
        logger.error("JWT token verification failed: %s", e)
        return None
