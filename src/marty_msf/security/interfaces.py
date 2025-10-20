"""
Security interfaces and protocols.

This module defines the core interfaces and protocols used throughout the security system
to avoid circular imports and provide clear contracts between components.
"""


from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


# --- Abstract base classes for DI factories ---
class ConsolidatedSecurityManager(ABC):
    """Abstract base class for consolidated security manager."""

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> 'SecurityPrincipal | None':
        """Authenticate user with credentials."""
        pass

    @abstractmethod
    async def authorize(self, principal: 'SecurityPrincipal', resource: str, action: str) -> bool:
        """Authorize principal for resource and action."""
        pass

    @abstractmethod
    def audit(self, event: dict[str, Any]) -> None:
        """Audit security event."""
        pass

class ConsolidatedSecurityManagerService(ABC):
    """Abstract base class for consolidated security manager service."""

    @abstractmethod
    def configure(self, config: dict[str, Any]) -> None:
        """Configure the security manager service."""
        pass

    @abstractmethod
    def get_security_manager(self) -> ConsolidatedSecurityManager:
        """Get the security manager instance."""
        pass

class ComplianceFramework(Enum):
    """Enumeration of supported compliance frameworks."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    NIST = "nist"


class IdentityProviderType(Enum):
    """Supported identity provider types"""
    OIDC = "oidc"
    OAUTH2 = "oauth2"
    SAML = "saml"
    LDAP = "ldap"
    LOCAL = "local"


@dataclass
class SecurityPrincipal:
    """Represents a security principal (user, service, device)"""
    id: str
    type: str  # user, service, device
    roles: set[str] = field(default_factory=set)
    attributes: dict[str, Any] = field(default_factory=dict)
    permissions: set[str] = field(default_factory=set)
    identity_provider: str | None = None
    session_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def get_effective_roles(self, role_hierarchy: dict[str, set[str]]) -> set[str]:
        """Get effective roles including inherited roles from hierarchy"""
        effective_roles = set(self.roles)

        def add_inherited_roles(role: str):
            if role in role_hierarchy:
                for inherited_role in role_hierarchy[role]:
                    if inherited_role not in effective_roles:
                        effective_roles.add(inherited_role)
                        add_inherited_roles(inherited_role)  # Recursive inheritance

        for role in self.roles:
            add_inherited_roles(role)

        return effective_roles

    def get_effective_permissions(self, role_hierarchy: dict[str, set[str]], role_permissions: dict[str, set[str]]) -> set[str]:
        """Get effective permissions from roles and hierarchy"""
        effective_permissions = set(self.permissions)  # Direct permissions
        effective_roles = self.get_effective_roles(role_hierarchy)

        # Add permissions from all effective roles
        for role in effective_roles:
            if role in role_permissions:
                effective_permissions.update(role_permissions[role])

        return effective_permissions


@dataclass
class SecurityContext:
    """Security context for policy evaluation"""
    principal: SecurityPrincipal
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SecurityDecision:
    """Result of security policy evaluation"""
    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    required_attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time_ms: float = 0.0


class PolicyEngine(ABC):
    """Abstract base class for policy engines"""

    @abstractmethod
    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """Evaluate security policy against context"""
        pass

    @abstractmethod
    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Load security policies"""
        pass

    @abstractmethod
    async def validate_policies(self) -> list[str]:
        """Validate loaded policies and return any errors"""
        pass


class ServiceMeshSecurityManager(ABC):
    """Abstract base class for service mesh security integration"""

    @abstractmethod
    async def apply_traffic_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Apply security policies to service mesh traffic"""
        pass

    @abstractmethod
    async def get_mesh_status(self) -> dict[str, Any]:
        """Get current service mesh security status"""
        pass

    @abstractmethod
    async def enforce_mTLS(self, services: list[str]) -> bool:
        """Enforce mutual TLS for specified services"""
        pass


class ComplianceScanner(ABC):
    """Abstract base class for compliance scanning"""

    @abstractmethod
    async def scan_compliance(
        self,
        framework: ComplianceFramework,
        scope: dict[str, Any]
    ) -> dict[str, Any]:
        """Scan for compliance violations"""
        pass

    @abstractmethod
    async def generate_compliance_report(
        self,
        scan_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate compliance report"""
        pass

    @abstractmethod
    async def get_supported_standards(self) -> list[str]:
        """Get supported compliance standards"""
        pass


class IdentityProvider(ABC):
    """Abstract base class for identity providers"""

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Authenticate user and return security principal"""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> SecurityPrincipal | None:
        """Validate token and return security principal"""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> str | None:
        """Refresh access token"""
        pass

    @abstractmethod
    async def get_user_attributes(self, principal_id: str) -> dict[str, Any]:
        """Get additional user attributes"""
        pass


class UnifiedSecurityFramework(Protocol):
    """Protocol for unified security framework implementations."""

    def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Authenticate user with credentials."""
        ...

    def authorize(self, principal: SecurityPrincipal, resource: str, action: str) -> bool:
        """Authorize principal for resource and action."""
        ...

    def audit(self, event: dict[str, Any]) -> None:
        """Audit security event."""
        ...


# Abstract base classes for concrete implementations
class BaseComplianceScanner(ABC):
    """Base class for compliance scanners."""

    @abstractmethod
    def scan(self, target: Any) -> dict[str, Any]:
        """Scan a target for compliance issues."""
        pass

    @abstractmethod
    def get_supported_standards(self) -> list[str]:
        """Get list of supported compliance standards."""
        pass


class BaseComplianceFramework(ABC):
    """Base class for compliance frameworks."""

    @abstractmethod
    def evaluate_compliance(self, data: dict[str, Any]) -> dict[str, Any]:
        """Evaluate compliance for given data."""
        pass

    @abstractmethod
    def get_framework_name(self) -> str:
        """Get the name of the compliance framework."""
        pass


class BaseSecurityPrincipal(ABC):
    """Base class for security principals."""

    @abstractmethod
    def identity(self) -> str:
        """Get the principal's identity."""
        pass

    @abstractmethod
    def roles(self) -> list[str]:
        """Get the principal's roles."""
        pass

    @abstractmethod
    def has_permission(self, permission: str) -> bool:
        """Check if principal has a specific permission."""
        pass


class BaseUnifiedSecurityFramework(ABC):
    """Base class for unified security frameworks."""

    @abstractmethod
    def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Authenticate user with credentials."""
        pass

    @abstractmethod
    def authorize(self, principal: SecurityPrincipal, resource: str, action: str) -> bool:
        """Authorize principal for resource and action."""
        pass

    @abstractmethod
    def audit(self, event: dict[str, Any]) -> None:
        """Audit security event."""
        pass
