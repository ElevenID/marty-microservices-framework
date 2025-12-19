"""
Security Enums

This module defines enumerations for security operations.
"""

from enum import Enum


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


class UserType(Enum):
    """
    User type classification for role-based access control.

    Distinguishes between users who manage travel documents (administrators)
    and users seeking to obtain travel documents (applicants).
    """

    ADMINISTRATOR = "administrator"
    APPLICANT = "applicant"
