"""
Security Framework for Marty Microservices Framework

Provides comprehensive security features following a clean level contract architecture:

Core Architecture:
- Level Contract principle: Clean layered dependencies (api -> implementations -> bootstrap)
- Dependency Inversion: Implementations depend on abstractions, not concrete classes
- No circular dependencies by design
- Pluggable authentication, authorization, and secret management

Modular Components:
- security.api: Core interfaces and contracts (foundation layer)
- security.auth_impl: Authentication implementations (BasicAuthenticator, JwtAuthenticator, etc.)
- security.authz_impl: Authorization implementations (RoleBasedAuthorizer, PermissionBasedAuthorizer, etc.)
- security.secrets_impl: Secret management implementations (EnvironmentSecretManager, FileSecretManager, etc.)
- security.bootstrap: Composition root for wiring components together

Additional Components:
- RBAC, ABAC, audit, and policy engine components
- Decorators and middleware for easy integration
- Compliance scanning and reporting
- Service mesh security integration

Usage:
- New applications should use the bootstrap module and interfaces
- Import components directly from this module for quick access
"""

import logging

# New modular security architecture
from . import policy_engines

# Core components
from .abac import (
    ABACContext,
    ABACManager,
    ABACPolicy,
    AttributeCondition,
    AttributeType,
    ConditionOperator,
    PolicyEffect,
    PolicyEvaluationResult,
)
from .api import (  # Core interfaces; Data models; Enums; Exceptions; Abstract base classes
    AbstractAuthenticator,
    AbstractAuthorizer,
    AbstractPolicyEngine,
    AbstractSecretManager,
    AbstractServiceMeshSecurityManager,
    AuthenticationError,
    AuthenticationMethod,
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationError,
    AuthorizationResult,
    ComplianceFramework,
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    IComplianceScanner,
    IPolicyEngine,
    ISecretManager,
    ISessionManager,
    PermissionAction,
    SecretManagerError,
    SecurityContext,
    SecurityDecision,
    SecurityError,
    SecurityPrincipal,
    User,
)
from .audit import (
    AuditLevel,
    AuditSink,
    DatabaseAuditSink,
    FileAuditSink,
    SecurityAuditEvent,
    SecurityAuditor,
    SecurityEventType,
    SyslogAuditSink,
)

# Audit implementations
from .audit_impl import (
    CompositeAuditor,
    FileAuditor,
    FilteringAuditor,
    NoOpAuditor,
    StructuredAuditor,
    create_default_auditor,
)

# Authentication implementations
from .auth_impl import BasicAuthenticator, EnvironmentAuthenticator, JwtAuthenticator
from .authentication import AuthenticationManager

# Authorization implementations
from .authz_impl import (
    AttributeBasedAuthorizer,
    PermissionBasedAuthorizer,
    RoleBasedAuthorizer,
)

# Bootstrap and composition root
from .bootstrap import (
    SecurityBootstrap,
    configure_security_in_container,
    create_default_security_system,
    create_development_security_system,
    create_production_security_system,
    create_testing_security_system,
    get_security_components_from_container,
)

# Caching implementations
from .caching import AdvancedCache, InMemoryCacheManager, SecurityCacheManager

# Import canonical functions from new implementation
from .canonical import (
    audit_security_event,
    authenticate_credentials,
    authorize_principal,
)
from .canonical import configure_security_system as configure_security_manager

# Import decorator implementations
from .decorators import (
    get_current_user,
    requires_abac,
    requires_any_role,
    requires_auth,
    requires_permission,
    requires_rbac,
    requires_role,
    verify_jwt_token,
)

# Enhanced security components (recovered functionality)
from .events import SecurityEventManager, create_event_manager
from .exceptions import (
    AccountLockedError,
    ClaimsVerificationError,
    ExternalProviderError,
    PermissionDeniedError,
    PolicyEvaluationError,
    RateLimitExceededError,
    RoleRequiredError,
    SecurityErrorType,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenMalformedError,
    handle_security_exception,
    require_authentication,
    require_permission,
    require_role,
)
from .framework import SecurityHardeningFramework, create_security_framework
from .policy_engines import (
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    configure_opa_service,
    configure_policy_service,
    create_policy_service_from_service_config,
    evaluate_policy,
    get_policy_service,
)
from .rbac import Permission, RBACManager, ResourceType, Role

# Secret management implementations
from .secrets_impl import (
    CompositeSecretManager,
    EnvironmentSecretManager,
    FileSecretManager,
    InMemorySecretManager,
)

# Session management implementations
from .sessions import InMemorySessionManager, NoOpSessionManager
from .status import SecurityStatusReporter, create_status_reporter

# SecurityPolicyType moved to api module - import from there if needed




logger = logging.getLogger(__name__)


__all__ = [
    # Core interfaces
    "IAuthenticator",
    "IAuthorizer",
    "ISecretManager",
    "IAuditor",
    "IPolicyEngine",
    "IComplianceScanner",
    "ISessionManager",

    # Data models
    "User",
    "AuthenticationResult",
    "AuthorizationContext",
    "AuthorizationResult",
    "SecurityContext",
    "SecurityDecision",
    "SecurityPrincipal",

    # Enums
    "AuthenticationMethod",
    "PermissionAction",
    "ComplianceFramework",

    # Bootstrap and composition root
    "SecurityBootstrap",
    "create_default_security_system",
    "create_development_security_system",
    "create_testing_security_system",
    "create_production_security_system",
    "configure_security_in_container",
    "get_security_components_from_container",

    # Authentication implementations
    "BasicAuthenticator",
    "JwtAuthenticator",
    "EnvironmentAuthenticator",

    # Authorization implementations
    "RoleBasedAuthorizer",
    "PermissionBasedAuthorizer",
    "AttributeBasedAuthorizer",

    # Secret management implementations
    "EnvironmentSecretManager",
    "FileSecretManager",
    "InMemorySecretManager",
    "CompositeSecretManager",

    # Abstract base classes
    "AbstractAuthenticator",
    "AbstractAuthorizer",
    "AbstractSecretManager",
    "AbstractPolicyEngine",
    "AbstractServiceMeshSecurityManager",

    # Core components
    # Authentication
    "configure_security_manager",
    # Canonical functions - single source of truth
    "authenticate_credentials",
    "authorize_principal",
    "audit_security_event",
    "SecurityContext",
    "requires_auth",
    "requires_role",
    "requires_permission",
    "requires_rbac",
    "requires_abac",
    "get_current_user",

    # Exceptions
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "PolicyEvaluationError",
    "ExternalProviderError",
    "SecretManagerError",

    # RBAC
    "Permission",
    "Role",
    "RBACManager",

    # ABAC
    "AttributeCondition",
    "ABACPolicy",
    "ABACManager",
    "ABACContext",
    "PolicyEffect",

    # Audit
    "SecurityAuditEvent",
    "SecurityAuditor",
    "AuditSink",
    "FileAuditSink",
    "SyslogAuditSink",

    # Policy Engine (OPA)
    "get_policy_service",
    "create_policy_service_from_service_config",
    "configure_policy_service",
    "configure_opa_service",
    "evaluate_policy",
    "PolicyEvaluationRequest",
    "PolicyEvaluationResponse",
    "policy_engines",

    # Enhanced Security Components (recovered functionality)
    "SecurityHardeningFramework",
    "create_security_framework",
    "SecurityEventManager",
    "create_event_manager",
    "SecurityStatusReporter",
    "create_status_reporter"
]
