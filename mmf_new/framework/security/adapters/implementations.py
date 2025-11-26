"""
Security Service Adapters

This module provides adapters to integrate various services with the security ports.
"""

from __future__ import annotations

import logging
from typing import Any

from mmf_new.core.security.domain.models.result import AuthenticationResult, AuthorizationResult
from mmf_new.core.security.domain.models.user import AuthenticatedUser, User
from mmf_new.core.security.domain.models.context import AuthorizationContext
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.core.security.ports.common import IAuditor

# Import service implementations
from mmf_new.services.identity.application.services.authentication_manager import AuthenticationManager
from mmf_new.services.identity.application.ports_out import (
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationResult as IdentityAuthenticationResult
)
from mmf_new.framework.authorization.api import IAuthorizer as CoreIAuthorizer
from mmf_new.services.audit_compliance.service_factory import AuditComplianceService
from mmf_new.core.domain.audit_types import SecurityEventType, SecurityEventSeverity

logger = logging.getLogger(__name__)


class IdentityServiceAuthenticator(IAuthenticator):
    """Adapter for Identity Service AuthenticationManager."""

    def __init__(self, auth_manager: AuthenticationManager):
        self.auth_manager = auth_manager

    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate using Identity Service."""
        try:
            # Map credentials dict to AuthenticationCredentials
            # We assume the dict contains 'method' or we default to BASIC
            method_str = credentials.get("method", "basic").upper()
            try:
                method = AuthenticationMethod[method_str]
            except KeyError:
                method = AuthenticationMethod.BASIC

            auth_credentials = AuthenticationCredentials(
                method=method,
                credentials=credentials
            )

            result: IdentityAuthenticationResult = await self.auth_manager.authenticate(auth_credentials)

            # Map IdentityAuthenticationResult to domain AuthenticationResult
            user = None
            if result.user:
                # Map Identity AuthenticatedUser to domain AuthenticatedUser
                user = AuthenticatedUser(
                    user_id=result.user.user_id,
                    username=result.user.username or "",
                    email=result.user.email,
                    roles=set(result.user.roles),
                    permissions=set(result.user.permissions),
                    metadata=result.user.metadata
                )

            return AuthenticationResult(
                success=result.success,
                user=user,
                error=result.error_message,
                metadata=result.metadata or {}
            )
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return AuthenticationResult(success=False, error=str(e))

    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate token using Identity Service."""
        try:
            # TODO: Implement token validation using auth manager
            # For now, return not implemented
            return AuthenticationResult(success=False, error="Not implemented")
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return AuthenticationResult(success=False, error=str(e))


class CoreAuthorizerAdapter(IAuthorizer):
    """Adapter for Core Authorization Service."""

    def __init__(self, authorizer: CoreIAuthorizer):
        self.authorizer = authorizer

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Authorize using Core Authorization Service."""
        try:
            result = self.authorizer.authorize(context)

            return AuthorizationResult(
                allowed=result.allowed,
                reason=result.reason,
                policies_evaluated=result.policies_evaluated,
                metadata=result.metadata
            )
        except Exception as e:
            logger.error(f"Authorization failed: {e}")
            return AuthorizationResult(allowed=False, reason=str(e))

    def get_user_permissions(self, user: User) -> set[str]:
        """Get permissions using Core Authorization Service."""
        try:
            permissions = self.authorizer.get_user_permissions(user)
            return set(permissions)
        except Exception as e:
            logger.error(f"Get permissions failed: {e}")
            return set()


class AuditServiceAdapter(IAuditor):
    """Adapter for Audit Compliance Service."""

    def __init__(self, audit_service: AuditComplianceService):
        self.audit_service = audit_service

    async def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log audit event using Audit Compliance Service."""
        try:
            # Map string event type to enum if possible, or use generic
            try:
                security_event_type = SecurityEventType(event_type)
            except ValueError:
                security_event_type = SecurityEventType.SECURITY_VIOLATION

            await self.audit_service.log_audit_event(
                event_type=security_event_type,
                severity=SecurityEventSeverity.INFO, # Default severity
                source="security_framework",
                description=details.get("description", f"Security event: {event_type}"),
                user_id=details.get("user_id"),
                metadata=details
            )
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")
