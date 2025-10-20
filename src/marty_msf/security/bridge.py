"""
Security Module Migration Bridge

This module provides a compatibility bridge during the transition from the monolithic
unified_framework to the new modular level contract architecture.

IMPORTANT: This is a temporary bridge to support existing code during migration.
New code should use the modular components directly:

- marty_msf.security.bootstrap for initialization
- marty_msf.security.api for interfaces
- marty_msf.security.auth_impl for authentication
- marty_msf.security.authz_impl for authorization
- marty_msf.security.secrets_impl for secret management

TODO: Gradually migrate dependent code and remove this bridge
"""

from __future__ import annotations

import time
import warnings
from typing import Any

from .api import (
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationResult,
    ComplianceFramework,
    ComplianceResult,
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    ISecretManager,
    ISessionManager,
    SecurityContext,
    SecurityDecision,
    SecurityPrincipal,
    User,
)
from .bootstrap import SecurityBootstrap
from .interfaces import SecurityContext as LegacySecurityContext
from .interfaces import SecurityDecision as LegacySecurityDecision
from .interfaces import SecurityPrincipal as LegacySecurityPrincipal


class UnifiedSecurityFrameworkBridge:
    """
    Compatibility bridge for UnifiedSecurityFramework.

    This provides a simplified interface that delegates to the new modular components.
    Use this temporarily during migration, then switch to direct component usage.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        warnings.warn(
            "UnifiedSecurityFrameworkBridge is deprecated. "
            "Use marty_msf.security.bootstrap.SecurityBootstrap instead.",
            DeprecationWarning,
            stacklevel=2
        )

        self.config = config or {}
        self.bootstrap = SecurityBootstrap(config)

        # Cached components
        self._authenticator = None
        self._authorizer = None
        self._secret_manager = None
        self._auditor = None
        self._cache_manager = None
        self._session_manager = None

        # Legacy state for compatibility
        self.active_sessions: dict[str, SecurityPrincipal] = {}
        self.audit_log: list[dict[str, Any]] = []
        self.metrics = {
            "authentication_attempts": 0,
            "authorization_checks": 0,
            "policy_evaluations": 0,
            "compliance_scans": 0
        }

    @property
    def authenticator(self) -> IAuthenticator:
        if self._authenticator is None:
            self._authenticator = self.bootstrap.get_authenticator()
        return self._authenticator

    @property
    def authorizer(self) -> IAuthorizer:
        if self._authorizer is None:
            self._authorizer = self.bootstrap.get_authorizer()
        return self._authorizer

    @property
    def secret_manager(self) -> ISecretManager:
        if self._secret_manager is None:
            self._secret_manager = self.bootstrap.get_secret_manager()
        return self._secret_manager

    @property
    def auditor(self) -> IAuditor:
        if self._auditor is None:
            self._auditor = self.bootstrap.get_auditor()
        return self._auditor

    @property
    def cache_manager(self) -> ICacheManager:
        if self._cache_manager is None:
            self._cache_manager = self.bootstrap.get_cache_manager()
        return self._cache_manager

    @property
    def session_manager(self) -> ISessionManager:
        if self._session_manager is None:
            self._session_manager = self.bootstrap.get_session_manager()
        return self._session_manager

    # Core compatibility methods
    async def authenticate(
        self,
        credentials: dict[str, Any],
        provider: str | None = None
    ) -> SecurityPrincipal | None:
        """Delegate to modular authenticator with compatibility layer."""
        self.metrics["authentication_attempts"] += 1

        # Call the synchronous authenticator
        auth_result = self.authenticator.authenticate(credentials)

        if auth_result.success and auth_result.user:
            # Convert User to SecurityPrincipal for backward compatibility
            principal = SecurityPrincipal(
                id=auth_result.user.id,
                type="user",
                roles=set(auth_result.user.roles),
                attributes=auth_result.user.attributes,
                identity_provider=provider or "local"
            )

            # Create session
            session_id = self.session_manager.create_session(principal)
            principal.session_id = session_id
            self.active_sessions[session_id] = principal

            return principal

        return None

    async def authorize(
        self,
        principal: SecurityPrincipal,
        resource: str,
        action: str,
        context: dict[str, Any] | None = None
    ) -> SecurityDecision:
        """Delegate to modular authorizer with compatibility layer."""
        self.metrics["authorization_checks"] += 1

        # Convert SecurityPrincipal to User for new API
        user = User(
            id=principal.id,
            username=principal.id,  # Use id as username fallback
            roles=list(principal.roles),
            attributes=principal.attributes
        )

        # Create authorization context
        auth_context = AuthorizationContext(
            user=user,
            resource=resource,
            action=action,
            environment=context or {}
        )

        # Call the synchronous authorizer
        auth_result = self.authorizer.authorize(auth_context)

        # Convert AuthorizationResult to SecurityDecision
        return SecurityDecision(
            allowed=auth_result.allowed,
            reason=auth_result.reason,
            policies_evaluated=auth_result.policies_evaluated,
            metadata=auth_result.metadata
        )

    # Legacy methods for backward compatibility
    async def initialize(self) -> bool:
        """Initialize the security framework (compatibility method)."""
        try:
            self.bootstrap.initialize_security_system()
            return True
        except Exception:
            return False

    def get_cache_metrics(self) -> dict[str, dict[str, Any]]:
        """Get cache metrics."""
        if hasattr(self.cache_manager, 'get_cache_metrics'):
            return self.cache_manager.get_cache_metrics()
        return {}

    def clear_caches(self, cache_type: str | None = None) -> None:
        """Clear caches."""
        if hasattr(self.cache_manager, 'clear_all_caches'):
            self.cache_manager.clear_all_caches()

    def invalidate_principal_cache(self, principal_id: str) -> int:
        """Invalidate principal cache."""
        if hasattr(self.cache_manager, 'invalidate_principal_cache'):
            return self.cache_manager.invalidate_principal_cache(principal_id)
        return 0

    def invalidate_resource_cache(self, resource: str) -> int:
        """Invalidate resource cache."""
        if hasattr(self.cache_manager, 'invalidate_resource_cache'):
            return self.cache_manager.invalidate_resource_cache(resource)
        return 0

    # Role management (delegate to authorizer if it supports it)
    def create_role(self, role_name: str, permissions: set[str] | None = None, inherited_roles: set[str] | None = None) -> bool:
        """Create a role (if supported by authorizer)."""
        if hasattr(self.authorizer, 'create_role'):
            return self.authorizer.create_role(role_name, permissions, inherited_roles)
        return False

    def delete_role(self, role_name: str) -> bool:
        """Delete a role (if supported by authorizer)."""
        if hasattr(self.authorizer, 'delete_role'):
            return self.authorizer.delete_role(role_name)
        return False

    def get_role_info(self, role_name: str) -> dict[str, Any] | None:
        """Get role information (if supported by authorizer)."""
        if hasattr(self.authorizer, 'get_role_info'):
            return self.authorizer.get_role_info(role_name)
        return None

    def list_roles(self) -> dict[str, dict[str, Any]]:
        """List all roles (if supported by authorizer)."""
        if hasattr(self.authorizer, 'list_roles'):
            return self.authorizer.list_roles()
        return {}

    def validate_role_hierarchy(self) -> list[str]:
        """Validate role hierarchy (if supported by authorizer)."""
        if hasattr(self.authorizer, 'validate_role_hierarchy'):
            return self.authorizer.validate_role_hierarchy()
        return []

    # Audit methods
    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log an audit event."""
        self.auditor.audit_event(event_type, details)
        # Also store in legacy audit_log for compatibility
        self.audit_log.append({
            "event_type": event_type,
            "details": details,
            "timestamp": time.time()
        })

    # Session management
    def create_session(self, principal: SecurityPrincipal, metadata: dict[str, Any] | None = None) -> str:
        """Create a session."""
        session_id = self.session_manager.create_session(principal, metadata)
        self.active_sessions[session_id] = principal
        return session_id

    def get_session(self, session_id: str) -> SecurityPrincipal | None:
        """Get a session."""
        return self.session_manager.get_session(session_id)

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        result = self.session_manager.invalidate_session(session_id)
        self.active_sessions.pop(session_id, None)
        return result

    # Compliance methods (placeholder - will be implemented when compliance module is added)
    async def scan_compliance(self, framework: ComplianceFramework, context: dict[str, Any] | None = None) -> ComplianceResult:
        """Scan for compliance (placeholder)."""
        self.metrics["compliance_scans"] += 1
        return ComplianceResult(
            framework=framework.value,
            passed=True,
            score=1.0,
            findings=[],
            recommendations=[],
            metadata={"note": "Compliance scanning not yet implemented in modular architecture"}
        )

    # Status and metrics
    async def get_security_status(self) -> dict[str, Any]:
        """Get security system status."""
        return {
            "initialized": True,
            "components": {
                "authenticator": type(self.authenticator).__name__,
                "authorizer": type(self.authorizer).__name__,
                "secret_manager": type(self.secret_manager).__name__,
                "auditor": type(self.auditor).__name__,
                "cache_manager": type(self.cache_manager).__name__,
                "session_manager": type(self.session_manager).__name__,
            },
            "metrics": self.metrics,
            "active_sessions": len(self.active_sessions)
        }


# Compatibility exports for easier migration
__all__ = [
    'UnifiedSecurityFrameworkBridge',
    'SecurityPrincipal',
    'SecurityContext',
    'SecurityDecision',
    'User',
    'AuthenticationResult',
    'AuthorizationContext',
    'AuthorizationResult',
]
