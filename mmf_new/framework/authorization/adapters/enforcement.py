"""
Authorization Decorators Module

This module provides security decorators and context management for authorization
in the MMF framework. It includes decorators for authentication, role-based access
control (RBAC), and attribute-based access control (ABAC).

Key Components:
- SecurityContext: Enhanced security context for decorated functions
- CurrentUserService: Thread-safe service for managing current user context
- Authentication decorators: @require_authenticated
- Role decorators: @require_role, @require_any_role
- Permission decorators: @require_permission
- Authorization decorators: @require_rbac, @require_abac
"""

import asyncio
import functools
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from mmf_new.core.security.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    PermissionDeniedError,
    RoleRequiredError,
)
from mmf_new.core.security.domain.models.context import AuthorizationContext
from mmf_new.core.security.domain.models.user import User
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.framework.infrastructure.dependency_injection import (
    get_service,
    has_service,
    register_instance,
)

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class SecurityContext:
    """
    Enhanced security context for decorated functions.

    Provides access to user information, roles, permissions, and token claims
    within the context of a secured function call.

    Attributes:
        user: The authenticated user
        session_id: Optional session identifier
        correlation_id: Optional correlation identifier for tracking
        authenticated_at: Timestamp when authentication occurred
    """

    def __init__(
        self,
        user: User,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ):
        """
        Initialize security context.

        Args:
            user: The authenticated user
            session_id: Optional session identifier
            correlation_id: Optional correlation identifier
        """
        self.user = user
        self.session_id = session_id
        self.correlation_id = correlation_id
        self.authenticated_at = datetime.now(timezone.utc)

    @property
    def principal_id(self) -> str:
        """
        Get the principal ID from the user.

        Returns:
            User's unique identifier
        """
        return self.user.id

    @property
    def principal(self) -> dict[str, Any]:
        """
        Get principal data as dictionary.

        Returns:
            Dictionary containing user's identity information
        """
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
        """
        Get user roles as set.

        Returns:
            Set of role names assigned to the user
        """
        return set(self.user.roles)

    @property
    def permissions(self) -> set[str]:
        """
        Get user permissions from the authorization service.

        Returns:
            Set of permission strings granted to the user
        """
        try:
            authorizer = get_service(IAuthorizer)
            return authorizer.get_user_permissions(self.user)
        except Exception as e:
            logger.error("Failed to get permissions: %s", e)
            return set()

    @property
    def token_claims(self) -> dict[str, Any]:
        """
        Get token claims from user metadata.

        Returns:
            Dictionary of JWT token claims
        """
        return self.user.metadata.get("token_claims", {})

    def has_role(self, role: str) -> bool:
        """
        Check if context has a specific role.

        Args:
            role: Role name to check

        Returns:
            True if user has the role, False otherwise
        """
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """
        Check if context has a specific permission.

        Args:
            permission: Permission string to check

        Returns:
            True if user has the permission, False otherwise
        """
        return permission in self.permissions


class CurrentUserService:
    """
    Thread-safe service to manage current user context.

    This service provides a thread-safe way to store and retrieve the current
    authenticated user without using global variables. It's designed to work
    with the dependency injection container.
    """

    def __init__(self):
        """Initialize the current user service with thread-safe storage."""
        self._lock = threading.RLock()
        self._current_user: User | None = None

    def get_user(self) -> User | None:
        """
        Get the current authenticated user.

        Returns:
            Current user if authenticated, None otherwise
        """
        with self._lock:
            return self._current_user

    def set_user(self, user: User | None) -> None:
        """
        Set the current authenticated user.

        Args:
            user: User to set as current, or None to clear
        """
        with self._lock:
            self._current_user = user


def _get_user_service() -> CurrentUserService:
    """
    Get or create the current user service from DI container.

    Returns:
        CurrentUserService instance
    """
    if not has_service(CurrentUserService):
        service = CurrentUserService()
        register_instance(CurrentUserService, service)
    return get_service(CurrentUserService)


def get_current_user() -> User | None:
    """
    Get the current authenticated user.

    Returns:
        Current user if authenticated, None otherwise
    """
    return _get_user_service().get_user()


def _set_current_user(user: User | None) -> None:
    """
    Set the current authenticated user (internal use only).

    Args:
        user: User to set as current
    """
    _get_user_service().set_user(user)


def require_authenticated(func: F) -> F:
    """
    Decorator that requires authentication.

    This decorator checks if the user is authenticated before allowing access
    to the decorated function. It attempts to extract credentials from the
    request headers (Bearer token or API key) and authenticate the user.

    Args:
        func: Function to decorate

    Returns:
        Decorated function that checks authentication

    Raises:
        AuthenticationError: If authentication is required but not provided

    Example:
        @require_authenticated
        def protected_endpoint(request):
            return {"message": "Access granted"}
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # Try to get credentials from request if available
            credentials = {}

            # Look for request object in args
            request = None
            for arg in args:
                if hasattr(arg, "headers"):  # Likely a request object
                    request = arg
                    break

            if request and hasattr(request, "headers"):
                auth_header = request.headers.get("authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    credentials["token"] = auth_header[7:]
                    credentials["method"] = "JWT"
                elif request.headers.get("x-api-key"):
                    credentials["api_key"] = request.headers.get("x-api-key")
                    credentials["method"] = "API_KEY"

            # If no credentials found, check if user is already authenticated
            current_user = get_current_user()
            if not current_user and not credentials:
                raise AuthenticationError("Authentication required")

            # Authenticate if we have credentials
            if credentials and not current_user:
                authenticator = get_service(IAuthenticator)
                result = await authenticator.authenticate(credentials)
                if not result.success or not result.user:
                    raise AuthenticationError(result.error or "Invalid credentials")
                current_user = result.user
                _set_current_user(current_user)

            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except Exception as e:
            # Simple error handling since handle_security_exception is removed
            if isinstance(
                e,
                AuthenticationError
                | AuthorizationError
                | PermissionDeniedError
                | RoleRequiredError,
            ):
                raise
            logger.error(f"Security error: {e}")
            raise AuthenticationError(str(e)) from e

    return wrapper


def require_role(role: str) -> Callable[[F], F]:
    """
    Decorator that requires a specific role.

    This decorator verifies that the authenticated user has the specified
    role before allowing access to the decorated function.

    Args:
        role: Required role name

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        RoleRequiredError: If user doesn't have the required role

    Example:
        @require_role("admin")
        def admin_endpoint(request):
            return {"message": "Admin access granted"}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                if role not in current_user.roles:
                    raise RoleRequiredError(f"Role '{role}' required", required_role=role)

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                if isinstance(
                    e,
                    AuthenticationError
                    | AuthorizationError
                    | PermissionDeniedError
                    | RoleRequiredError,
                ):
                    raise
                logger.error(f"Security error: {e}")
                raise AuthorizationError(str(e)) from e

        return wrapper

    return decorator


def require_permission(permission: str) -> Callable[[F], F]:
    """
    Decorator that requires a specific permission.

    This decorator verifies that the authenticated user has the specified
    permission before allowing access to the decorated function.

    Args:
        permission: Required permission string

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        PermissionDeniedError: If user doesn't have the required permission

    Example:
        @require_permission("users.delete")
        def delete_user_endpoint(request, user_id):
            return {"message": f"User {user_id} deleted"}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                authorizer = get_service(IAuthorizer)
                permissions = authorizer.get_user_permissions(current_user)

                if permission not in permissions:
                    raise PermissionDeniedError(
                        f"Permission '{permission}' required", permission=permission
                    )

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                if isinstance(
                    e,
                    AuthenticationError
                    | AuthorizationError
                    | PermissionDeniedError
                    | RoleRequiredError,
                ):
                    raise
                logger.error(f"Security error: {e}")
                raise AuthorizationError(str(e)) from e

        return wrapper

    return decorator


def require_any_role(*roles: str) -> Callable[[F], F]:
    """
    Decorator that requires any of the specified roles.

    This decorator verifies that the authenticated user has at least one
    of the specified roles before allowing access to the decorated function.

    Args:
        roles: Required role names (any one of them)

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        RoleRequiredError: If user doesn't have any of the required roles

    Example:
        @require_any_role("admin", "moderator")
        def moderation_endpoint(request):
            return {"message": "Moderation access granted"}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                user_roles = set(current_user.roles)
                required_roles = set(roles)

                if not user_roles.intersection(required_roles):
                    raise RoleRequiredError(
                        f"One of roles {roles} required", required_role=str(roles)
                    )

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                if isinstance(
                    e,
                    AuthenticationError
                    | AuthorizationError
                    | PermissionDeniedError
                    | RoleRequiredError,
                ):
                    raise
                logger.error(f"Security error: {e}")
                raise AuthorizationError(str(e)) from e

        return wrapper

    return decorator


def require_rbac(resource: str, action: str) -> Callable[[F], F]:
    """
    Decorator that requires RBAC authorization.

    This decorator verifies that the authenticated user is authorized to
    perform the specified action on the specified resource using role-based
    access control.

    Args:
        resource: Resource being accessed
        action: Action being performed

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        AuthorizationError: If user is not authorized

    Example:
        @require_rbac("documents", "delete")
        def delete_document_endpoint(request, doc_id):
            return {"message": f"Document {doc_id} deleted"}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                authorizer = get_service(IAuthorizer)
                context = AuthorizationContext(
                    user=current_user,
                    resource=resource,
                    action=action,
                    environment={},  # TODO: Extract environment from request if possible
                )

                result = authorizer.authorize(context)
                if not result.allowed:
                    raise AuthorizationError(
                        f"Access denied to {resource}:{action}: {result.reason}"
                    )

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                if isinstance(
                    e,
                    AuthenticationError
                    | AuthorizationError
                    | PermissionDeniedError
                    | RoleRequiredError,
                ):
                    raise
                logger.error(f"Security error: {e}")
                raise AuthorizationError(str(e)) from e

        return wrapper

    return decorator


def require_abac(resource: str, action: str) -> Callable[[F], F]:
    """
    Decorator that requires ABAC authorization.

    This decorator verifies that the authenticated user is authorized to
    perform the specified action on the specified resource using attribute-based
    access control. Currently uses the same authorization logic as RBAC but
    is designed to support more complex attribute-based policies in the future.

    Args:
        resource: Resource being accessed
        action: Action being performed

    Returns:
        Decorator function

    Raises:
        AuthenticationError: If user is not authenticated
        AuthorizationError: If user is not authorized

    Example:
        @require_abac("documents", "read")
        def read_document_endpoint(request, doc_id):
            return {"content": "Document content"}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                current_user = get_current_user()
                if not current_user:
                    raise AuthenticationError("Authentication required")

                # For now, use the same authorization as RBAC
                # In the future, this could use more complex attribute-based logic
                authorizer = get_service(IAuthorizer)
                context = AuthorizationContext(
                    user=current_user, resource=resource, action=action, environment={}
                )

                result = authorizer.authorize(context)
                if not result.allowed:
                    raise AuthorizationError(
                        f"Access denied to {resource}:{action}: {result.reason}"
                    )

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                if isinstance(
                    e,
                    AuthenticationError
                    | AuthorizationError
                    | PermissionDeniedError
                    | RoleRequiredError,
                ):
                    raise
                logger.error(f"Security error: {e}")
                raise AuthorizationError(str(e)) from e

        return wrapper

    return decorator


async def verify_jwt_token(token: str) -> User | None:
    """
    Verify a JWT token and return the authenticated user.

    Args:
        token: JWT token string to verify

    Returns:
        User if token is valid, None otherwise

    Example:
        user = await verify_jwt_token("eyJhbGciOiJIUzI1...")
        if user:
            print(f"Authenticated as {user.username}")
    """
    try:
        credentials = {"token": token, "method": "JWT"}
        authenticator = get_service(IAuthenticator)
        result = await authenticator.authenticate(credentials)
        return result.user if result.success else None
    except Exception as e:
        logger.error("JWT token verification failed: %s", e)
        return None


# Alias for backward compatibility with old naming convention
requires_auth = require_authenticated
requires_role = require_role
requires_permission = require_permission
requires_any_role = require_any_role
requires_rbac = require_rbac
requires_abac = require_abac
