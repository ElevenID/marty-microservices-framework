"""
Authentication Adapter

Adapter for Identity Service AuthenticationManager.
"""

from __future__ import annotations

import logging
from typing import Any

from mmf_new.core.security.domain.models.result import AuthenticationResult
from mmf_new.core.security.domain.models.user import AuthenticatedUser
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.services.identity.application.ports_out import (
    AuthenticationCredentials,
    AuthenticationMethod,
)
from mmf_new.services.identity.application.ports_out import (
    AuthenticationResult as IdentityAuthenticationResult,
)
from mmf_new.services.identity.application.services.authentication_manager import (
    AuthenticationManager,
)

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

            auth_credentials = AuthenticationCredentials(method=method, credentials=credentials)

            result: IdentityAuthenticationResult = await self.auth_manager.authenticate(
                auth_credentials
            )

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
                    metadata=result.user.metadata,
                )

            return AuthenticationResult(
                success=result.success,
                user=user,
                error=result.error_message,
                metadata=result.metadata or {},
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
