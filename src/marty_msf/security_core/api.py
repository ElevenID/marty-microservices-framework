"""
Security API - Core Interfaces and Contracts

This module defines the foundational interfaces and data contracts for the security system.
It serves as the lowest level in our security architecture, containing only abstract
contracts that other security components depend on.

Following the Level Contract principle:
- This module imports only from standard library
- All other security modules depend on this API layer
- No circular dependencies are possible by design
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

# --- Core Data Models ---


@dataclass
class User:
    """Represents a user in the security system."""

    id: str
    username: str
    roles: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    email: str | None = None


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user with enhanced session information."""

    user_id: str
    username: str | None = None
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    session_id: str | None = None
    auth_method: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def is_expired(self) -> bool:
        """Check if the authentication has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class AuthenticationResult:
    """Result of an authentication attempt."""

    success: bool
    user: AuthenticatedUser | None = None
    error: str | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationContext:
    """Context for authorization decisions."""

    user: User
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuthorizationResult:
    """Result of an authorization decision."""

    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Core Interfaces ---


@runtime_checkable
class IAuthenticator(Protocol):
    """Interface for authentication providers."""

    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """
        Authenticate user credentials.

        Args:
            credentials: Dictionary containing authentication credentials

        Returns:
            AuthenticationResult indicating success/failure and user details
        """
        ...

    def validate_token(self, token: str) -> AuthenticationResult:
        """
        Validate an authentication token.

        Args:
            token: Authentication token to validate

        Returns:
            AuthenticationResult indicating validity and user details
        """
        ...


@runtime_checkable
class IAuthorizer(Protocol):
    """Interface for authorization providers."""

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Check if a user is authorized for a specific action on a resource.

        Args:
            context: Authorization context containing user, resource, and action

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        ...

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get all permissions for a user.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings
        """
        ...


@runtime_checkable
class ISecretManager(Protocol):
    """Interface for secret management."""

    def get_secret(self, key: str) -> str | None:
        """
        Retrieve a secret value by key.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        ...

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Store a secret value.

        Args:
            key: Secret identifier
            value: Secret value to store
            metadata: Optional metadata for the secret

        Returns:
            True if successfully stored, False otherwise
        """
        ...

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret.

        Args:
            key: Secret identifier

        Returns:
            True if successfully deleted, False otherwise
        """
        ...


@runtime_checkable
class IAuditor(Protocol):
    """Interface for security audit logging."""

    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Log a security event for auditing.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        ...


# --- Security Exceptions ---


class SecurityError(Exception):
    """Base exception for security-related errors."""


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""


class SecretManagerError(SecurityError):
    """Raised when secret management operations fail."""


# --- Enums ---


class AuthenticationMethod(Enum):
    """Supported authentication methods."""

    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    SAML = "saml"


class PermissionAction(Enum):
    """Standard permission actions."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


# --- Abstract Base Classes (Alternative to Protocols) ---


class BaseAuthenticator(ABC):
    """Base class for authentication providers compatible with legacy code."""

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate a user with provided credentials."""

    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an authentication token."""


class AbstractAuthenticator(ABC):
    """Abstract base class for authenticators."""

    @abstractmethod
    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate user credentials."""

    @abstractmethod
    def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an authentication token."""


class AbstractAuthorizer(ABC):
    """Abstract base class for authorizers."""

    @abstractmethod
    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Check authorization for user action on resource."""

    @abstractmethod
    def get_user_permissions(self, user: User) -> set[str]:
        """Get all permissions for a user."""


class AbstractSecretManager(ABC):
    """Abstract base class for secret managers."""

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret value."""

    @abstractmethod
    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """Store a secret value."""

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        """Delete a secret."""


class AbstractPolicyEngine(ABC):
    """Abstract base class for policy engines."""

    @abstractmethod
    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """Evaluate security policy against context."""

    @abstractmethod
    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Load security policies."""

    @abstractmethod
    async def validate_policies(self) -> list[str]:
        """Validate loaded policies and return any errors."""


class AbstractServiceMeshSecurityManager(ABC):
    """Abstract base class for service mesh security integration."""

    @abstractmethod
    async def apply_traffic_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Apply security policies to service mesh traffic."""

    @abstractmethod
    async def get_mesh_status(self) -> dict[str, Any]:
        """Get current service mesh security status."""

    @abstractmethod
    async def enforce_mTLS(self, services: list[str]) -> bool:
        """Enforce mutual TLS for specified services."""


# --- Additional Core Data Models ---


@dataclass
@dataclass
class SecurityPrincipal:
    """Represents a security principal (user, service, device)."""

    id: str
    type: str  # user, service, device
    roles: set[str] = field(default_factory=set)
    attributes: dict[str, Any] = field(default_factory=dict)
    permissions: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    identity_provider: str | None = None
    session_id: str | None = None
    expires_at: datetime | None = None


@dataclass
class SecurityContext:
    """Context for security decisions."""

    principal: SecurityPrincipal
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SecurityDecision:
    """Result of a security policy evaluation."""

    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    required_attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time_ms: float = 0.0
    cache_key: str | None = None


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""

    decision: bool
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time: float = 0.0


@dataclass
class ComplianceResult:
    """Result of a compliance scan."""

    framework: str
    passed: bool
    score: float
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    """Security audit event."""

    event_type: str
    principal_id: str | None
    resource: str | None
    action: str | None
    result: str  # success, failure, error
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str | None = None


# --- Additional Enums ---


class PolicyEngineType(Enum):
    """Types of policy engines."""

    BUILTIN = "builtin"
    OPA = "opa"
    OSO = "oso"
    ACL = "acl"
    CUSTOM = "custom"


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    NIST = "nist"


class IdentityProviderType(Enum):
    """Supported identity provider types."""

    OIDC = "oidc"
    OAUTH2 = "oauth2"
    SAML = "saml"
    LDAP = "ldap"
    LOCAL = "local"


class SecurityPolicyType(Enum):
    """Types of security policies."""

    RBAC = "rbac"
    ABAC = "abac"
    ACL = "acl"
    CUSTOM = "custom"


# --- Additional Interfaces ---


@runtime_checkable
class IPolicyEngine(Protocol):
    """Interface for policy engines."""

    def evaluate_policy(self, context: SecurityContext) -> PolicyResult:
        """
        Evaluate a policy for the given context.

        Args:
            context: Security context for evaluation

        Returns:
            PolicyResult indicating the decision
        """
        ...

    def load_policies(self, policies: dict[str, Any]) -> bool:
        """
        Load policies into the engine.

        Args:
            policies: Policy definitions to load

        Returns:
            True if successfully loaded
        """
        ...

    def validate_policies(self) -> list[str]:
        """
        Validate loaded policies.

        Returns:
            List of validation errors (empty if valid)
        """
        ...


@runtime_checkable
class IComplianceScanner(Protocol):
    """Interface for compliance scanners."""

    def scan_compliance(
        self, framework: ComplianceFramework, context: dict[str, Any]
    ) -> ComplianceResult:
        """
        Scan for compliance with a specific framework.

        Args:
            framework: Compliance framework to scan against
            context: Context for the compliance scan

        Returns:
            ComplianceResult with scan results
        """
        ...

    def get_supported_frameworks(self) -> list[ComplianceFramework]:
        """
        Get list of supported compliance frameworks.

        Returns:
            List of supported frameworks
        """
        ...


@runtime_checkable
class ICacheManager(Protocol):
    """Interface for cache management."""

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        ...

    def set(
        self, key: str, value: Any, ttl: float | None = None, tags: set[str] | None = None
    ) -> bool:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Tags for cache invalidation

        Returns:
            True if successfully cached
        """
        ...

    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if successfully deleted
        """
        ...

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """
        Invalidate cache entries by tags.

        Args:
            tags: Tags to invalidate

        Returns:
            Number of entries invalidated
        """
        ...


@runtime_checkable
class ISessionManager(Protocol):
    """Interface for session management."""

    def create_session(
        self, principal: SecurityPrincipal, metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Create a new session for a principal.

        Args:
            principal: Security principal
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        ...

    def get_session(self, session_id: str) -> SecurityPrincipal | None:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SecurityPrincipal or None if not found
        """
        ...

    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if successfully invalidated
        """
        ...


@runtime_checkable
class IIdentityProvider(Protocol):
    """Interface for identity providers."""

    def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """
        Authenticate credentials with this provider.

        Args:
            credentials: Authentication credentials

        Returns:
            SecurityPrincipal if authenticated, None otherwise
        """
        ...

    def get_provider_type(self) -> IdentityProviderType:
        """
        Get the provider type.

        Returns:
            IdentityProviderType enum value
        """
        ...
