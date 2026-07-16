"""
Gateway Security Services

This module provides services for handling security-related tasks in the gateway,
such as credential extraction.
"""

from typing import Any

from mmf.core.gateway import (
    AuthenticationError,
    AuthenticationType,
    GatewayRequest,
    ICredentialExtractor,
    IGatewaySecurityHandler,
    RouteConfig,
)
from mmf.core.security.ports.authentication import IAuthenticator


class GatewaySecurityHandler(IGatewaySecurityHandler):
    """
    Handles security validation for gateway requests.
    """

    def __init__(self, authenticator: IAuthenticator | None = None):
        self.authenticator = authenticator

    async def validate_security(self, route: RouteConfig, request: GatewayRequest) -> None:
        """
        Validate security for request.

        Args:
            route: The matched route configuration.
            request: The incoming gateway request.

        Raises:
            AuthenticationError: If authentication fails or is required but missing.
        """
        if route.authentication_type != AuthenticationType.NONE:
            user_context = await self._authenticate_request(route.authentication_type, request)
            if user_context:
                request.context["user"] = user_context

        if route.auth_required and not request.context.get("user"):
            raise AuthenticationError("Authentication required")

    async def _authenticate_request(
        self, auth_type: AuthenticationType, request: GatewayRequest
    ) -> dict[str, Any] | None:
        """Authenticate request based on authentication type."""
        if not self.authenticator:
            # If no authenticator is configured but auth is required, we must fail secure
            # or return None if auth is optional (handled by caller)
            return None

        extractor = CredentialExtractorFactory.get_extractor(auth_type)
        if not extractor:
            return None

        credentials = extractor.extract(request)

        if auth_type == AuthenticationType.BEARER_TOKEN:
            # Use validate_token for Bearer tokens
            result = await self.authenticator.validate_token(credentials["token"])
            if not result.success:
                raise AuthenticationError(result.error or "Invalid bearer token")

            # Map user to dict context
            if result.user:
                return {
                    "user_id": result.user.user_id,
                    "username": result.user.username,
                    "roles": list(result.user.roles),
                    "permissions": list(result.user.permissions),
                }
            return {}

        # For other types, use authenticate method
        if credentials:
            result = await self.authenticator.authenticate(credentials)
            if not result.success:
                raise AuthenticationError(result.error or "Authentication failed")

            if result.user:
                return {
                    "user_id": result.user.user_id,
                    "username": result.user.username,
                    "roles": list(result.user.roles),
                    "permissions": list(result.user.permissions),
                }
            return {}

        return None


class ApiKeyExtractor(ICredentialExtractor):
    """Extracts API Key from headers."""

    def extract(self, request: GatewayRequest) -> dict[str, Any]:
        auth_header = request.get_header("Authorization") or ""
        # Check X-API-Key header first, then Authorization header
        api_key = request.get_header("X-API-Key")

        if not api_key and auth_header.startswith("ApiKey "):
            api_key = auth_header[7:]

        if not api_key:
            raise AuthenticationError("API key required")

        return {"method": "api_key", "api_key": api_key}


class BearerTokenExtractor(ICredentialExtractor):
    """Extracts Bearer Token from Authorization header."""

    def extract(self, request: GatewayRequest) -> dict[str, Any]:
        auth_header = request.get_header("Authorization") or ""
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Bearer token required")

        token = auth_header[7:]
        return {"method": "bearer", "token": token}


class CredentialExtractorFactory:
    """Factory for creating credential extractors."""

    _extractors = {
        AuthenticationType.API_KEY: ApiKeyExtractor(),
        AuthenticationType.BEARER_TOKEN: BearerTokenExtractor(),
    }

    @classmethod
    def get_extractor(cls, auth_type: AuthenticationType) -> ICredentialExtractor | None:
        """Get the appropriate extractor for the auth type."""
        return cls._extractors.get(auth_type)
