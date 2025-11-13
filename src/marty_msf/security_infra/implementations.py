"""
Security Infrastructure Implementations

Service mesh, middleware, and platform integration implementations.
"""

import builtins
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from ..security_core.api import (
    AbstractServiceMeshSecurityManager,
    ISessionManager,
    SecurityContext,
    SecurityPrincipal,
)

logger = logging.getLogger(__name__)


class BasicSessionManager(ISessionManager):
    """Basic in-memory session manager."""

    def __init__(self, session_timeout_minutes: int = 30):
        """
        Initialize session manager.

        Args:
            session_timeout_minutes: Session timeout in minutes
        """
        self.session_timeout_minutes = session_timeout_minutes
        self._sessions: builtins.dict[str, builtins.dict[str, Any]] = {}

    def create_session(
        self, principal: SecurityPrincipal, metadata: builtins.dict[str, Any] | None = None
    ) -> str:
        """Create a new session for a principal."""
        session_id = str(uuid.uuid4())

        self._sessions[session_id] = {
            "principal": principal,
            "created_at": datetime.now(timezone.utc),
            "last_accessed": datetime.now(timezone.utc),
            "metadata": metadata or {},
        }

        return session_id

    def get_session(self, session_id: str) -> SecurityPrincipal | None:
        """Retrieve a session by ID."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check if session has expired
        last_accessed = session["last_accessed"]
        now = datetime.now(timezone.utc)
        timeout_delta = timedelta(minutes=self.session_timeout_minutes)

        if now - last_accessed > timeout_delta:
            # Session expired, remove it
            del self._sessions[session_id]
            return None

        # Update last accessed time
        session["last_accessed"] = now

        return session["principal"]

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count removed."""
        now = datetime.now(timezone.utc)
        timeout_delta = timedelta(minutes=self.session_timeout_minutes)
        expired_sessions = []

        for session_id, session in self._sessions.items():
            last_accessed = session["last_accessed"]
            if now - last_accessed > timeout_delta:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self._sessions[session_id]

        return len(expired_sessions)


class SecurityMiddleware:
    """Security middleware for request processing."""

    def __init__(
        self, session_manager: ISessionManager, security_context_key: str = "security_context"
    ):
        """
        Initialize security middleware.

        Args:
            session_manager: Session manager instance
            security_context_key: Key for storing security context in request
        """
        self.session_manager = session_manager
        self.security_context_key = security_context_key

    def process_request(self, request: Any) -> SecurityContext | None:
        """
        Process incoming request and establish security context.

        Args:
            request: HTTP request object

        Returns:
            SecurityContext if authentication successful, None otherwise
        """
        # Extract session ID from request (e.g., from cookie or header)
        session_id = self._extract_session_id(request)

        if not session_id:
            return None

        # Get principal from session
        principal = self.session_manager.get_session(session_id)

        if not principal:
            return None

        # Create security context
        context = SecurityContext(
            principal=principal,
            resource=getattr(request, "path", "/"),
            action=getattr(request, "method", "GET"),
            request_metadata=self._extract_request_metadata(request),
            request_id=getattr(request, "id", None),
        )

        # Store context in request for later use
        setattr(request, self.security_context_key, context)

        return context

    def _extract_session_id(self, request: Any) -> str | None:
        """Extract session ID from request."""
        # Try to get from Authorization header
        auth_header = getattr(request, "headers", {}).get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove 'Bearer ' prefix

        # Try to get from cookie
        cookies = getattr(request, "cookies", {})
        return cookies.get("session_id")

    def _extract_request_metadata(self, request: Any) -> builtins.dict[str, Any]:
        """Extract metadata from request."""
        return {
            "user_agent": getattr(request, "headers", {}).get("User-Agent"),
            "remote_addr": getattr(request, "remote_addr", None),
            "method": getattr(request, "method", None),
            "path": getattr(request, "path", None),
            "query_string": getattr(request, "query_string", None),
        }


class ServiceMeshSecurityManager(AbstractServiceMeshSecurityManager):
    """Basic service mesh security manager."""

    def __init__(self):
        """Initialize service mesh security manager."""
        self._traffic_policies: builtins.list[builtins.dict[str, Any]] = []
        self._mtls_services: set[str] = set()

    async def apply_traffic_policies(
        self, policies: builtins.list[builtins.dict[str, Any]]
    ) -> bool:
        """Apply security policies to service mesh traffic."""
        try:
            for policy in policies:
                if self._validate_policy(policy):
                    self._traffic_policies.append(policy)
                    logger.info(f"Applied traffic policy: {policy.get('name', 'unnamed')}")
                else:
                    logger.warning(f"Invalid traffic policy: {policy}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Failed to apply traffic policies: {e}")
            return False

    async def get_mesh_status(self) -> builtins.dict[str, Any]:
        """Get current service mesh security status."""
        return {
            "status": "active",
            "policies_count": len(self._traffic_policies),
            "mtls_services_count": len(self._mtls_services),
            "mtls_services": list(self._mtls_services),
            "policies": [
                {
                    "name": policy.get("name", "unnamed"),
                    "type": policy.get("type", "unknown"),
                    "enabled": policy.get("enabled", True),
                }
                for policy in self._traffic_policies
            ],
        }

    async def enforce_mTLS(self, services: builtins.list[str]) -> bool:
        """Enforce mutual TLS for specified services."""
        try:
            for service in services:
                self._mtls_services.add(service)
                logger.info(f"Enforced mTLS for service: {service}")

            return True
        except Exception as e:
            logger.error(f"Failed to enforce mTLS: {e}")
            return False

    def _validate_policy(self, policy: builtins.dict[str, Any]) -> bool:
        """Validate a traffic policy."""
        required_fields = ["name", "type", "rules"]

        for field in required_fields:
            if field not in policy:
                return False

        # Validate policy type
        valid_types = ["rate_limit", "access_control", "encryption", "authentication"]
        if policy["type"] not in valid_types:
            return False

        # Validate rules structure
        rules = policy.get("rules", [])
        if not isinstance(rules, list):
            return False

        return True


class SecurityDecorator:
    """Decorator for securing functions and methods."""

    def __init__(
        self,
        required_permissions: builtins.list[str] | None = None,
        required_roles: builtins.list[str] | None = None,
    ):
        """
        Initialize security decorator.

        Args:
            required_permissions: List of required permissions
            required_roles: List of required roles
        """
        self.required_permissions = required_permissions or []
        self.required_roles = required_roles or []

    def __call__(self, func: Callable) -> Callable:
        """Apply security decorator to function."""

        def wrapper(*args, **kwargs):
            # Get security context (this would be injected in a real implementation)
            context = kwargs.get("security_context")

            if not context:
                raise PermissionError("No security context provided")

            # Check permissions
            if self.required_permissions:
                user_permissions = context.principal.permissions
                for permission in self.required_permissions:
                    if permission not in user_permissions:
                        raise PermissionError(f"Missing permission: {permission}")

            # Check roles
            if self.required_roles:
                user_roles = context.principal.roles
                for role in self.required_roles:
                    if role not in user_roles:
                        raise PermissionError(f"Missing role: {role}")

            # Execute function if all checks pass
            return func(*args, **kwargs)

        return wrapper


def require_permission(permission: str) -> Callable:
    """Decorator to require a specific permission."""
    return SecurityDecorator(required_permissions=[permission])


def require_role(role: str) -> Callable:
    """Decorator to require a specific role."""
    return SecurityDecorator(required_roles=[role])


def require_authentication(func: Callable) -> Callable:
    """Decorator to require authentication."""

    def wrapper(*args, **kwargs):
        context = kwargs.get("security_context")

        if not context or not context.principal:
            raise PermissionError("Authentication required")

        return func(*args, **kwargs)

    return wrapper


class SecurityContextManager:
    """Manager for security context lifecycle."""

    def __init__(self):
        """Initialize security context manager."""
        self._context_stack: builtins.list[SecurityContext] = []

    def push_context(self, context: SecurityContext) -> None:
        """Push a security context onto the stack."""
        self._context_stack.append(context)

    def pop_context(self) -> SecurityContext | None:
        """Pop a security context from the stack."""
        if self._context_stack:
            return self._context_stack.pop()
        return None

    def current_context(self) -> SecurityContext | None:
        """Get the current security context."""
        if self._context_stack:
            return self._context_stack[-1]
        return None

    def clear_context(self) -> None:
        """Clear all security contexts."""
        self._context_stack.clear()
