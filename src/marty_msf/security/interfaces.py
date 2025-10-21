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

from .api import SecurityPrincipal

# --- Deprecated interfaces removed ---
# The ConsolidatedSecurityManager and ConsolidatedSecurityManagerService
# interfaces have been removed in favor of the new modular bootstrap system.

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


# SecurityPrincipal moved to api.py - import from there



@dataclass
class SecurityContext:
    """Security context for policy evaluation"""
    principal: 'SecurityPrincipal'
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

    @abstractmethod
    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Load security policies"""

    @abstractmethod
    async def validate_policies(self) -> list[str]:
        """Validate loaded policies and return any errors"""


class ServiceMeshSecurityManager(ABC):
    """Abstract base class for service mesh security integration"""

    @abstractmethod
    async def apply_traffic_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Apply security policies to service mesh traffic"""

    @abstractmethod
    async def get_mesh_status(self) -> dict[str, Any]:
        """Get current service mesh security status"""

    @abstractmethod
    async def enforce_mTLS(self, services: list[str]) -> bool:
        """Enforce mutual TLS for specified services"""


class ComplianceScanner(ABC):
    """Abstract base class for compliance scanning"""

    @abstractmethod
    async def scan_compliance(
        self,
        framework: ComplianceFramework,
        scope: dict[str, Any]
    ) -> dict[str, Any]:
        """Scan for compliance violations"""

    @abstractmethod
    async def generate_compliance_report(
        self,
        scan_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate compliance report"""

    @abstractmethod
    async def get_supported_standards(self) -> list[str]:
        """Get supported compliance standards"""


# Legacy IdentityProvider and UnifiedSecurityFramework removed - use api.py interfaces instead


# Legacy base classes removed - use the api.py interfaces and classes instead
