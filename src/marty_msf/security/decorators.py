from __future__ import annotations

"""
Enhanced Security Decorators with RBAC/ABAC Integration

Comprehensive decorators for authentication and authorization with:
- JWT token validation and claims verification
- RBAC and ABAC policy enforcement
- Comprehensive audit logging
- Robust error handling for all edge cases
- Context injection and security manager integration

This module now uses the ConsolidatedSecurityManager for all security operations.
"""

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union, cast

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    ClaimsVerificationError,
    PermissionDeniedError,
    RoleRequiredError,
    SecurityError,
    TokenExpiredError,
    TokenInvalidError,
    TokenMalformedError,
    handle_security_exception,
)
from .manager import ConsolidatedSecurityManager, SecurityContext, get_security_manager

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])

# Security bearer scheme for FastAPI
security_bearer = HTTPBearer(auto_error=False)



class _SecurityManagerProxy:
    """Lazy proxy to access the consolidated security manager when needed."""

    def __init__(self) -> None:
        self._instance: ConsolidatedSecurityManager | None = None

    def _resolve(self) -> ConsolidatedSecurityManager:
        manager = get_security_manager()
        self._instance = manager
        return manager

    def __getattr__(self, item):
        manager = self._instance or self._resolve()
        return getattr(manager, item)


security_manager = _SecurityManagerProxy()


async def get_current_user(
    request: Request,
    token: str | None = None
) -> SecurityContext:
    """
    FastAPI dependency to get current authenticated user context.

    Args:
        request: FastAPI request object
        token: Optional token (extracted from request if not provided)

    Returns:
        SecurityContext: Current user's security context

    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Extract token if not provided
        if not token:
            token = security_manager.extract_token_from_request(request)

        if not token:
            raise HTTPException(
                status_code=401,
                detail="No authentication token provided",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Authenticate and get security context
        return await security_manager.authenticate_token(token)

    except (TokenExpiredError, TokenInvalidError, TokenMalformedError) as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal authentication error"
        )


def requires_auth(
    optional: bool = False,
    extract_context: bool = True
) -> Callable[[F], F]:
    """
    Decorator that requires authentication for a function or endpoint.

    Args:
        optional: If True, allows unauthenticated access but populates context if token present
        extract_context: If True, injects SecurityContext into function parameters

    Returns:
        Decorated function with authentication enforcement
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get request object from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # Check kwargs for request
                request = kwargs.get('request')

            if not request:
                if not optional:
                    raise AuthenticationError("No request object found for authentication")
                return await func(*args, **kwargs)

            try:
                # Extract token
                token = security_manager.extract_token_from_request(request)

                if not token:
                    if optional:
                        return await func(*args, **kwargs)
                    raise AuthenticationError("No authentication token provided")

                # Get security context
                context = await security_manager.authenticate_token(token)

                # Inject context if requested
                if extract_context:
                    kwargs['security_context'] = context

                return await func(*args, **kwargs)

            except (TokenExpiredError, TokenInvalidError, TokenMalformedError):
                if optional:
                    return await func(*args, **kwargs)
                raise
            except Exception as e:
                logger.error(f"Authentication decorator error: {e}")
                if optional:
                    return await func(*args, **kwargs)
                raise AuthenticationError(f"Authentication failed: {e}")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, run the async logic in an event loop
            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


def requires_role(
    roles: str | list[str],
    require_all: bool = False
) -> Callable[[F], F]:
    """
    Decorator that requires specific roles for access.

    Args:
        roles: Required role(s) - string for single role, list for multiple
        require_all: If True, requires all roles; if False, requires any role

    Returns:
        Decorated function with role-based authorization
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get security context from kwargs or authenticate
            context = kwargs.get('security_context')

            if not context:
                # Try to authenticate first
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if not request:
                    request = kwargs.get('request')

                if not request:
                    raise AuthorizationError("No request object found for role authorization")

                token = security_manager.extract_token_from_request(request)
                if not token:
                    raise AuthorizationError("No authentication token for role check")

                context = await security_manager.authenticate_token(token)
                kwargs['security_context'] = context

            # Perform RBAC authorization
            authorized = await security_manager.authorize_rbac(
                context, roles, require_all
            )

            if not authorized:
                role_list = roles if isinstance(roles, list) else [roles]
                raise RoleRequiredError(
                    f"Access denied. Required role(s): {role_list}",
                    required_role=role_list[0] if role_list else "unknown"
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


def requires_permission(
    permissions: str | list[str],
    require_all: bool = True
) -> Callable[[F], F]:
    """
    Decorator that requires specific permissions for access.

    Args:
        permissions: Required permission(s)
        require_all: If True, requires all permissions; if False, requires any permission

    Returns:
        Decorated function with permission-based authorization
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get security context
            context = kwargs.get('security_context')

            if not context:
                # Try to authenticate first
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if not request:
                    request = kwargs.get('request')

                if not request:
                    raise AuthorizationError("No request object found for permission authorization")

                token = security_manager.extract_token_from_request(request)
                if not token:
                    raise AuthorizationError("No authentication token for permission check")

                context = await security_manager.authenticate_token(token)
                kwargs['security_context'] = context

            # Check permissions
            perm_list = permissions if isinstance(permissions, list) else [permissions]

            if require_all:
                authorized = all(context.has_permission(perm) for perm in perm_list)
            else:
                authorized = any(context.has_permission(perm) for perm in perm_list)

            if not authorized:
                raise PermissionDeniedError(
                    f"Access denied. Required permission(s): {perm_list}",
                    permission=perm_list[0] if perm_list else "unknown"
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


def requires_rbac(
    roles: str | list[str] | None = None,
    permissions: str | list[str] | None = None,
    require_all_roles: bool = False,
    require_all_permissions: bool = True
) -> Callable[[F], F]:
    """
    Comprehensive RBAC decorator supporting both roles and permissions.

    Args:
        roles: Required roles
        permissions: Required permissions
        require_all_roles: If True, requires all roles
        require_all_permissions: If True, requires all permissions

    Returns:
        Decorated function with comprehensive RBAC authorization
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get security context
            context = kwargs.get('security_context')

            if not context:
                # Try to authenticate first
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if not request:
                    request = kwargs.get('request')

                if not request:
                    raise AuthorizationError("No request object found for RBAC authorization")

                token = security_manager.extract_token_from_request(request)
                if not token:
                    raise AuthorizationError("No authentication token for RBAC check")

                context = await security_manager.authenticate_token(token)
                kwargs['security_context'] = context

            # Check roles if specified
            if roles:
                role_authorized = await security_manager.authorize_rbac(
                    context, roles, require_all_roles
                )
                if not role_authorized:
                    role_list = roles if isinstance(roles, list) else [roles]
                    raise AuthorizationError(f"Insufficient roles. Required: {role_list}")

            # Check permissions if specified
            if permissions:
                perm_list = permissions if isinstance(permissions, list) else [permissions]

                if require_all_permissions:
                    perm_authorized = all(context.has_permission(perm) for perm in perm_list)
                else:
                    perm_authorized = any(context.has_permission(perm) for perm in perm_list)

                if not perm_authorized:
                    raise AuthorizationError(f"Insufficient permissions. Required: {perm_list}")

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


def requires_abac(
    resource: str,
    action: str,
    context_extractor: Callable | None = None
) -> Callable[[F], F]:
    """
    ABAC (Attribute-Based Access Control) decorator.

    Args:
        resource: Resource being accessed
        action: Action being performed
        context_extractor: Optional function to extract additional context from request

    Returns:
        Decorated function with ABAC authorization
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get security context
            context = kwargs.get('security_context')

            if not context:
                # Try to authenticate first
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if not request:
                    request = kwargs.get('request')

                if not request:
                    raise AuthorizationError("No request object found for ABAC authorization")

                token = security_manager.extract_token_from_request(request)
                if not token:
                    raise AuthorizationError("No authentication token for ABAC check")

                context = await security_manager.authenticate_token(token)
                kwargs['security_context'] = context

            # Extract additional context if extractor provided
            additional_context = {}
            if context_extractor:
                try:
                    if asyncio.iscoroutinefunction(context_extractor):
                        additional_context = await context_extractor(*args, **kwargs)
                    else:
                        additional_context = context_extractor(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Context extractor failed: {e}")

            # Perform ABAC authorization
            authorized = await security_manager.authorize_abac(
                context, resource, action, additional_context
            )

            if not authorized:
                raise AuthorizationError(
                    f"Access denied for action '{action}' on resource '{resource}'"
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


def requires_any_role(roles: list[str]) -> Callable[[F], F]:
    """Convenience decorator that requires any of the specified roles."""
    return requires_role(roles, require_all=False)


# JWT verification helper function
async def verify_jwt_token(token: str) -> dict[str, Any]:
    """
    Verify and decode JWT token.

    Args:
        token: JWT token string

    Returns:
        Dict containing token claims

    Raises:
        TokenError: If token is invalid, expired, or malformed
    """
    return security_manager.validate_jwt_token(token)


# Export all decorators and utilities
__all__ = [
    'requires_auth',
    'requires_role',
    'requires_permission',
    'requires_rbac',
    'requires_abac',
    'requires_any_role',
    'get_current_user',
    'verify_jwt_token',
    'SecurityContext',
    'security_bearer',
    'security_manager'
]
