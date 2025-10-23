"""
Security Models and Data Structures

This module contains all the data models, enums, and data classes used
throughout the security framework components.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SecurityLevel(Enum):
    """Security levels for different operations."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class AuthenticationMethod(Enum):
    """Authentication methods supported."""

    PASSWORD = "password"
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"
    MULTI_FACTOR = "multi_factor"


class SecurityThreatLevel(Enum):
    """Security threat levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStandard(Enum):
    """Compliance standards."""

    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    NIST = "nist"


@dataclass
class SecurityPrincipal:
    """Security principal (user/service) representation."""

    id: str
    name: str
    type: str  # "user", "service", "system"
    roles: builtins.list[str] = field(default_factory=list)
    permissions: builtins.list[str] = field(default_factory=list)
    attributes: builtins.dict[str, Any] = field(default_factory=dict)
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_access: datetime | None = None
    is_active: bool = True


@dataclass
class SecurityToken:
    """Security token for authentication."""

    token_id: str
    principal_id: str
    token_type: AuthenticationMethod
    expires_at: datetime
    scopes: builtins.list[str] = field(default_factory=list)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    is_revoked: bool = False


@dataclass
class SecurityEvent:
    """Security event for audit logging."""

    event_id: str
    event_type: str
    principal_id: str | None
    resource: str
    action: str
    result: str  # "success", "failure", "blocked"
    threat_level: SecurityThreatLevel
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: builtins.dict[str, Any] = field(default_factory=dict)
    source_ip: str | None = None


@dataclass
class SecurityVulnerability:
    """Security vulnerability detected in scanning."""

    vulnerability_id: str
    title: str
    description: str
    severity: SecurityThreatLevel
    cve_id: str | None = None
    affected_component: str = ""
    remediation: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "open"  # "open", "investigating", "fixed", "accepted"
