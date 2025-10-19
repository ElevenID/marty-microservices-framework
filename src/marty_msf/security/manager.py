"""
Consolidated Security Manager for Marty Microservices Framework

This module provides a single, unified security manager that consolidates all
authentication, authorization, and policy management capabilities. It replaces
the multiple duplicate SecurityManager implementations with a single, comprehensive
solution.

Key Features:
- Unified security operations through UnifiedSecurityFramework
- Robust error handling for all security operations
- Comprehensive audit logging
- RBAC and ABAC policy enforcement
- OPA policy engine integration
- External identity provider support
- Zero-trust security model
"""

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Optional, TypeVar, Union, cast

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.di_container import configure_service, get_service, get_service_optional
from ..core.services import SecurityService
from .audit import (
    AuditLevel,
    SecurityAuditEvent,
    SecurityEventType,
    get_security_auditor,
)
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
from .factories import register_security_services
from .unified_framework import SecurityPrincipal, UnifiedSecurityFramework

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])

# Security bearer scheme for FastAPI
security_bearer = HTTPBearer(auto_error=False)


class SecurityContext:
    """Enhanced security context for decorated functions."""

    def __init__(
        self,
        principal_id: str,
        principal: dict[str, Any],
        roles: set[str],
        permissions: set[str],
        token_claims: dict[str, Any],
        session_id: str | None = None,
        correlation_id: str | None = None,
        security_framework: UnifiedSecurityFramework | None = None
    ):
        self.principal_id = principal_id
        self.principal = principal
        self.roles = roles
        self.permissions = permissions
        self.token_claims = token_claims
        self.session_id = session_id
        self.correlation_id = correlation_id
        self.security_framework = security_framework
        self.authenticated_at = datetime.now(timezone.utc)

    def has_role(self, role: str) -> bool:
        """Check if context has role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if context has permission."""
        return permission in self.permissions

    def has_any_role(self, roles: list[str]) -> bool:
        """Check if context has any of the specified roles."""
        return any(role in self.roles for role in roles)

    def has_all_roles(self, roles: list[str]) -> bool:
        """Check if context has all specified roles."""
        return all(role in self.roles for role in roles)

    async def evaluate_abac_policy(
        self,
        resource: str,
        action: str,
        context: dict[str, Any] | None = None
    ) -> bool:
        """Evaluate ABAC policy for resource and action."""
        if not self.security_framework:
            logger.warning("No security framework available for ABAC evaluation")
            return False

        try:
            # Create a SecurityPrincipal object for the unified framework
            principal = SecurityPrincipal(
                id=self.principal_id,
                type="user",  # Default type
                roles=self.roles,
                permissions=self.permissions
            )

            decision = await self.security_framework.authorize(
                principal,
                resource,
                action,
                context or {}
            )
            return decision.allowed
        except Exception as e:
            logger.error(f"ABAC policy evaluation failed: {e}")
            return False


class ConsolidatedSecurityManager:
    """
    Consolidated security manager that unifies all security operations.

    This class replaces the multiple SecurityManager implementations with a single,
    comprehensive solution based on the UnifiedSecurityFramework.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the consolidated security manager."""
        self.config = config or self._get_default_config()
        self.security_framework: UnifiedSecurityFramework | None = None
        self.auditor = get_security_auditor()
        self._initialized = False

        # Configuration
        self.jwt_secret = self.config.get("jwt_secret", "your-secret-key")
        self.jwt_algorithm = self.config.get("jwt_algorithm", "HS256")
        self.jwt_issuer = self.config.get("jwt_issuer", "marty-msf")
        self.jwt_audience = self.config.get("jwt_audience", "marty-microservices")

        # Token validation settings
        self.validate_expiry = self.config.get("validate_expiry", True)
        self.validate_issuer = self.config.get("validate_issuer", True)
        self.validate_audience = self.config.get("validate_audience", True)
        self.clock_skew_seconds = self.config.get("clock_skew_seconds", 30)

        # Custom claim validators
        self.custom_claim_validators: list[Callable[[dict[str, Any]], None]] = []

    def _get_default_config(self) -> dict[str, Any]:
        """Get default security configuration."""
        return {
            "jwt_secret": "your-secret-key",  # Should be configured properly in production
            "jwt_algorithm": "HS256",
            "jwt_issuer": "marty-msf",
            "jwt_audience": "marty-microservices",
            "validate_expiry": True,
            "validate_issuer": True,
            "validate_audience": True,
            "clock_skew_seconds": 30,
            "enable_audit_logging": True,
            "enable_rbac": True,
            "enable_abac": True,
            "policy_engines": {
                "opa": {
                    "enabled": False,
                    "url": "http://localhost:8181"
                }
            },
            "identity_providers": {
                "local": {
                    "type": "local",
                    "enabled": True
                }
            },
            "cache": {
                "enabled": True,
                "ttl_seconds": 300,
                "max_size": 10000
            }
        }

    async def initialize(self) -> bool:
        """Initialize the security framework asynchronously."""
        if self._initialized:
            return True

        try:
            self.security_framework = UnifiedSecurityFramework(self.config)
            success = await self.security_framework.initialize()

            if success:
                self._initialized = True
                # Audit successful initialization
                self.auditor.audit(
                    SecurityEventType.AUTHENTICATION_SUCCESS,
                    result="success",
                    framework_version="consolidated"
                )
                logger.info("Consolidated security manager initialized successfully")

            return success

        except Exception as e:
            logger.error(f"Failed to initialize security framework: {e}")
            return False

    async def ensure_initialized(self):
        """Ensure the security framework is initialized."""
        if not self._initialized:
            await self.initialize()

    def configure_jwt(
        self,
        secret: str,
        algorithm: str = "HS256",
        issuer: str | None = None,
        audience: str | None = None
    ):
        """Configure JWT validation settings."""
        self.jwt_secret = secret
        self.jwt_algorithm = algorithm
        if issuer:
            self.jwt_issuer = issuer
        if audience:
            self.jwt_audience = audience

    @handle_security_exception
    def extract_token_from_request(self, request: Request) -> str | None:
        """Extract JWT token from request headers."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        # Check X-Auth-Token header
        x_auth_token = request.headers.get("X-Auth-Token")
        if x_auth_token:
            return x_auth_token

        # Check query parameter (less secure, but sometimes needed)
        token_param = request.query_params.get("token")
        if token_param:
            return token_param

        return None

    @handle_security_exception
    def validate_jwt_token(self, token: str) -> dict[str, Any]:
        """Validate JWT token and return claims with comprehensive error handling."""
        if not token:
            raise TokenInvalidError("Token is required")

        try:
            # Configure JWT validation options
            options = {
                "verify_signature": True,
                "verify_exp": self.validate_expiry,
                "verify_iss": self.validate_issuer,
                "verify_aud": self.validate_audience,
                "require_exp": True,
                "require_iat": True,
                "require_sub": True
            }

            # Decode and validate token
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
                issuer=self.jwt_issuer if self.validate_issuer else None,
                audience=self.jwt_audience if self.validate_audience else None,
                options=options,
                leeway=self.clock_skew_seconds
            )

            # Additional claims validation
            self._validate_token_claims(claims)

            # Audit successful token validation
            self.auditor.audit(
                SecurityEventType.TOKEN_VALIDATED,
                result="success",
                subject=claims.get("sub"),
                issuer=claims.get("iss"),
                algorithm=self.jwt_algorithm
            )

            return claims

        except jwt.ExpiredSignatureError:
            # Extract expiry time for better error reporting
            try:
                unverified_claims = jwt.decode(token, options={"verify_signature": False})
                expiry_time = datetime.fromtimestamp(
                    unverified_claims.get("exp", 0), timezone.utc
                )
            except Exception:
                expiry_time = None

            # Audit failed validation
            self.auditor.audit(
                SecurityEventType.TOKEN_EXPIRED,
                result="failure",
                expiry_time=expiry_time.isoformat() if expiry_time else "unknown"
            )

            raise TokenExpiredError(
                "Token has expired",
                token_type="JWT",
                expiry_time=expiry_time
            )

        except jwt.InvalidTokenError as e:
            error_msg = str(e)

            # Categorize the error for better handling
            if "Signature" in error_msg:
                # Audit security incident
                self.auditor.audit(
                    SecurityEventType.SECURITY_VIOLATION,
                    result="failure",
                    error=error_msg,
                    token_prefix=token[:20] + "..."
                )
                raise TokenInvalidError(f"Token signature is invalid: {e}")

            elif "decode" in error_msg.lower() or "format" in error_msg.lower():
                # Audit malformed token - use AUTHENTICATION_FAILURE since TOKEN_MALFORMED doesn't exist
                self.auditor.audit(
                    SecurityEventType.AUTHENTICATION_FAILURE,
                    result="failure",
                    error=error_msg
                )
                raise TokenMalformedError(f"Token is malformed: {e}")

            else:
                # General token validation error
                self.auditor.audit(
                    SecurityEventType.AUTHENTICATION_FAILURE,
                    result="failure",
                    error=error_msg
                )
                raise TokenInvalidError(f"Token validation failed: {e}")

        except Exception as e:
            # Unexpected error during token validation
            logger.error("Unexpected error during token validation: %s", e)
            self.auditor.audit(
                SecurityEventType.SYSTEM_ERROR,
                result="error",
                error=str(e)
            )
            raise TokenInvalidError(f"Token validation error: {e}")

    def _validate_token_claims(self, claims: dict[str, Any]):
        """Validate additional token claims."""
        # Required claims validation
        required_claims = ["sub", "iat", "exp"]
        for claim in required_claims:
            if claim not in claims:
                raise ClaimsVerificationError(f"Required claim '{claim}' missing from token")

        # Subject validation
        subject = claims.get("sub")
        if not subject or not isinstance(subject, str):
            raise ClaimsVerificationError("Invalid or missing subject claim")

        # Custom claims validation
        for validator in self.custom_claim_validators:
            try:
                validator(claims)
            except Exception as e:
                raise ClaimsVerificationError(f"Custom claim validation failed: {e}")

    def add_claim_validator(self, validator: Callable[[dict[str, Any]], None]):
        """Add a custom claim validator function."""
        self.custom_claim_validators.append(validator)

    async def authenticate_token(self, token: str) -> SecurityContext:
        """Authenticate token and return security context."""
        await self.ensure_initialized()

        # Validate JWT token
        claims = self.validate_jwt_token(token)

        # Get principal information
        principal_id = claims["sub"]

        # For now, use claims-based approach until we clarify unified framework interface
        roles = set(claims.get("roles", []))
        permissions = set(claims.get("permissions", []))
        principal = {"id": principal_id, "claims": claims}

        # Create security context
        return SecurityContext(
            principal_id=principal_id,
            principal=principal,
            roles=roles,
            permissions=permissions,
            token_claims=claims,
            session_id=claims.get("session_id"),
            correlation_id=claims.get("correlation_id"),
            security_framework=self.security_framework
        )

    async def authorize_rbac(
        self,
        context: SecurityContext,
        required_roles: str | list[str],
        require_all: bool = False
    ) -> bool:
        """Authorize using RBAC."""
        if isinstance(required_roles, str):
            required_roles = [required_roles]

        try:
            if require_all:
                authorized = context.has_all_roles(required_roles)
            else:
                authorized = context.has_any_role(required_roles)

            # Audit authorization decision
            self.auditor.audit(
                SecurityEventType.AUTHORIZATION_GRANTED if authorized else SecurityEventType.AUTHORIZATION_DENIED,
                principal_id=context.principal_id,
                result="granted" if authorized else "denied",
                required_roles=required_roles,
                user_roles=list(context.roles),
                require_all=require_all
            )

            return authorized

        except Exception as e:
            logger.error(f"RBAC authorization error: {e}")
            self.auditor.audit(
                SecurityEventType.SYSTEM_ERROR,
                principal_id=context.principal_id,
                result="error",
                error=str(e)
            )
            return False

    async def authorize_abac(
        self,
        context: SecurityContext,
        resource: str,
        action: str,
        additional_context: dict[str, Any] | None = None
    ) -> bool:
        """Authorize using ABAC."""
        await self.ensure_initialized()

        if not self.security_framework:
            logger.warning("No security framework available for ABAC authorization")
            return False

        try:
            # Create a SecurityPrincipal object for the unified framework
            principal = SecurityPrincipal(
                id=context.principal_id,
                type="user",  # Default type
                roles=context.roles,
                permissions=context.permissions
            )

            # Use the unified security framework for ABAC
            decision = await self.security_framework.authorize(
                principal,
                resource,
                action,
                additional_context or {}
            )

            # Audit authorization decision
            self.auditor.audit(
                SecurityEventType.AUTHORIZATION_GRANTED if decision.allowed else SecurityEventType.AUTHORIZATION_DENIED,
                principal_id=context.principal_id,
                resource=resource,
                action=action,
                result="granted" if decision.allowed else "denied",
                decision_reason=decision.reason,
                policies_evaluated=decision.policies_evaluated
            )

            return decision.allowed

        except Exception as e:
            logger.error(f"ABAC authorization error: {e}")
            self.auditor.audit(
                SecurityEventType.SYSTEM_ERROR,
                principal_id=context.principal_id,
                result="error",
                error=str(e)
            )
            return False


class ConsolidatedSecurityManagerService(SecurityService):
    """
    Typed service for consolidated security manager.

    Replaces global security manager variables with proper dependency injection.
    """

    def __init__(self) -> None:
        super().__init__()
        self._security_manager: ConsolidatedSecurityManager | None = None

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the security service."""
        self._security_manager = ConsolidatedSecurityManager(config)
        self._mark_configured()

    def is_authenticated(self, token: str) -> bool:
        """Check if a token is authenticated."""
        if not self._security_manager:
            raise RuntimeError("Security manager not configured")
        # Implementation depends on the actual ConsolidatedSecurityManager methods
        return True  # Placeholder

    def is_authorized(self, user_id: str, resource: str, action: str) -> bool:
        """Check if a user is authorized for an action."""
        if not self._security_manager:
            raise RuntimeError("Security manager not configured")
        # Implementation depends on the actual ConsolidatedSecurityManager methods
        return True  # Placeholder

    def get_security_manager(self) -> ConsolidatedSecurityManager:
        """Get the security manager instance."""
        if self._security_manager is None:
            # Create with default configuration
            self._security_manager = ConsolidatedSecurityManager()
            self._mark_configured()
        return self._security_manager


def get_security_manager_service() -> ConsolidatedSecurityManagerService:
    """
    Get the security manager service instance using dependency injection.

    Returns:
        ConsolidatedSecurityManagerService instance

    Raises:
        ValueError: If service is not registered in the DI container
    """
    try:
        return get_service(ConsolidatedSecurityManagerService)
    except ValueError:
        # Auto-register if not found (for backward compatibility)
        register_security_services()
        return get_service(ConsolidatedSecurityManagerService)


def get_security_manager() -> ConsolidatedSecurityManager:
    """
    Get the security manager instance using dependency injection.

    Returns:
        ConsolidatedSecurityManager instance
    """
    try:
        return get_service(ConsolidatedSecurityManager)
    except ValueError:
        # Auto-register if not found (for backward compatibility)
        register_security_services()
        return get_service(ConsolidatedSecurityManager)


def configure_security_manager(config: dict[str, Any]) -> ConsolidatedSecurityManager:
    """
    Configure and get the security manager instance using dependency injection.

    Args:
        config: Configuration dictionary for the security manager

    Returns:
        ConsolidatedSecurityManager instance
    """

    # Ensure services are registered
    try:
        get_service(ConsolidatedSecurityManagerService)
    except ValueError:
        register_security_services()

    # Configure the service
    configure_service(ConsolidatedSecurityManagerService, config)
    return get_service(ConsolidatedSecurityManager)
